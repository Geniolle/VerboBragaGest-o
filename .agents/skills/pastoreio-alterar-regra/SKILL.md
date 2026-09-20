---
name: pastoreio-alterar-regra
description: Modifica uma regra de negócio ou comportamento do motor de alocação (motor.py e módulos relacionados) — novos filtros, mudança de ordem de desempate, mudança de critério de elegibilidade, correção de bug de regra. Use quando a tarefa pede para mudar COMO o motor decide. Não use para só gerar uma Ronda com as regras atuais (pastoreio-executar-ronda) nem para explicar uma decisão já tomada (pastoreio-investigar-alocacao).
---

# Alterar uma regra de negócio do motor

Regras de negócio profundas estão documentadas em
[`../../../CONCEITO_CICLO.md`](../../../CONCEITO_CICLO.md),
[`../../../CONCEITO_PRIORIDADES.md`](../../../CONCEITO_PRIORIDADES.md) e
[`../../../CONCEITO_CEIA_ALTERNADA.md`](../../../CONCEITO_CEIA_ALTERNADA.md).
Leia o(s) relevante(s) antes de mexer em código — não assuma que esta skill
ou a sua memória da regra está atualizada; o código + testes atuais são a
fonte de verdade.

## Workflow obrigatório

1. **Identificar o comportamento atual** — leia o trecho relevante de
   `motor.py` (ou o módulo específico: `carregamento.py`,
   `sanity_regras.py`, etc.) e o(s) `CONCEITO_*.md` relacionados. Não
   assuma o comportamento a partir do nome da função.
2. **Localizar a implementação** — normalmente em
   `src/pastoreio_orquestrador/motor.py`. Filtros obrigatórios vivem em
   `avaliar_candidatos_para_slot`/`_avaliar_e_escolher`; desempate em
   `chave_ordenacao_candidato`; fases de CEIA em
   `_alocar_grupo_domingo_ceia_alternada`; cálculo de demanda em
   `calcular_demanda_onda_expansiva`; encerramento dinâmico da Ronda em
   `ronda_esta_completa`/`alocar_ronda_dinamica`.
3. **Localizar os testes existentes** — `tests/test_motor.py`,
   `tests/test_ceia_alternada.py`, `tests/test_excluse.py`,
   `tests/test_fase0_temas.py` costumam cobrir estas áreas. Rode-os antes
   de mudar nada, para saber o que já passa.
4. **Verificar os documentos de conceito relacionados** — a mudança
   contradiz algo já escrito em `CONCEITO_*.md`? Se sim, é preciso decidir
   (com o utilizador, se a regra vier de fora e não estiver clara) se o
   documento está desatualizado ou se a mudança pedida está incompleta.
5. **Determinar o escopo da mudança**: é global (afeta todo o motor e
   todos os grupos), por grupo (`DEPARTAMENTO###FUNÇÃO###DIA`), por
   função, ou por dia da semana? Isso decide onde o `if`/parâmetro entra —
   não espalhe uma condição que deveria ser global por vários pontos do
   código, nem torne global algo que só se aplica a um grupo específico
   (ex.: tema/nível já é explicitamente restrito a QUARTA-FEIRA — não
   generalize sem necessidade).
   Para DOMINGO, lembre que a hierarquia normal é contínua entre execuções:
   qualquer mudança nesse fluxo precisa preservar a reconstrução do cursor
   por histórico persistido (agenda + auditoria), nunca por variável global,
   cache local ou estado de processo.
   Também preserve a separação entre cursor e quota mensal: CEIA tem ciclo
   próprio e `CONSOME_HIERARQUIA=FALSE`, mas conta como ocorrência mensal
   para `REPETIÇÃO MENSAL` no contexto DOMINGO/MINISTRO.
   Para `D. MINISTROS / MINISTRO / DOMINGO` e
   `D. MINISTROS / MINISTRO / QUARTA-FEIRA`, respeite
   `PASTOREIO_DATA_CORTE_HISTORICO`: estado rotacional anterior ao corte é
   legado. Em DOMINGO, isso cobre cursor, CEIA, replay, lacunas,
   GAP_FILL/RESGATE e cotas; em QUARTA-FEIRA, cobre Rondas, replay, quotas e
   rodízios de tema/nível próprios da quarta. Não aplique esse corte a fatos
   reais de agenda usados por filtros temporais, como descanso cruzado,
   Excluse, aniversário ou indisponibilidades.
   Ao tocar reconstrução entre execuções, não recalcule decisões passadas
   quando o resultado real já existe: a CEIA histórica de DOMINGO deve ser
   carregada da agenda persistida confirmada por auditoria/intenção `CEIA`,
   e só depois comparada com o conjunto atual `CEIA ALTERNADA=true`.
   A fila normal deve usar o cursor normal atual; obrigações mensais
   (`REPETIÇÃO MENSAL` e `ALOCAR TODOS OS MESES`) não podem reposicionar esse
   cursor. Candidato só analisado/rejeitado também não é consumido.
   Antes de adicionar qualquer condição nova ao motor, identifique se a regra
   pertence a elegibilidade, obrigação, ranking/hierarquia, intenção da vaga,
   transição de estado ou auditoria. Para DOMINGO, prefira políticas pequenas
   em `src/pastoreio_orquestrador/domain/domingo/`; para QUARTA-FEIRA,
   preserve os conceitos próprios de tema/nível (P1/P2/P3 não são nomes da
   hierarquia de DOMINGO). Não leve reconstrução de CEIA, cursor normal de
   DOMINGO ou replay de Rondas de DOMINGO para QUARTA-FEIRA; se o fluxo de
   QUARTA-FEIRA precisar evoluir, modele-o como processo próprio, com dados,
   estado e testes próprios.
   Em DOMINGO, não confunda `TIPO_DIA` com motivo/intenção: um
   `DOMINGO_NORMAL` pode ser rotação normal, repetição mensal, obrigação de
   todos-os-meses ou lacuna. Se a intenção for `GAP_FILL`, defina também a
   política de seleção; lacuna não deve criar uma hierarquia paralela
   implícita.
6. **Alterar o menor número possível de componentes.** Prefira estender
   uma função existente a duplicá-la. Se a mudança precisar de um novo
   parâmetro em `avaliar_candidatos_para_slot`/`_avaliar_e_escolher`/
   `alocar_grupo`/`_alocar_grupo_domingo_ceia_alternada`, siga o padrão já
   usado para `excluse_header`/`excluse_rows`/`aniversarios` (thread por
   todas as funções da cadeia, com default `None`/comportamento anterior
   quando não fornecido).
7. **Adicionar ou alterar teste de regressão.** Toda mudança de regra
   precisa de pelo menos um teste novo ou atualizado que comprove o
   comportamento novo E, quando aplicável, um teste que comprove que o
   caso antigo continua a funcionar (a menos que a mudança seja
   explicitamente uma correção que invalida o comportamento antigo — nesse
   caso, atualize/renomeie o teste antigo para refletir o comportamento
   correto, não o apague silenciosamente).
   Se a mudança toca DOMINGO, inclua cobertura de `CONSOME_HIERARQUIA`
   quando a decisão pode ser CEIA, repetição mensal, ATM, resgate, lacuna
   ou alocação normal. Se a regra toca `REPETIÇÃO MENSAL`, cubra também a
   contagem conjunta CEIA + MINISTRO no mês.
8. **Rodar a suite completa** (`uv run pytest`) — nunca considere a tarefa
   terminada só porque o código compila ou porque o teste novo passa
   isoladamente. Investigue qualquer falha, mesmo em teste aparentemente
   não relacionado.
9. **Atualizar a documentação relevante** — se a mudança altera uma regra
   descrita num `CONCEITO_*.md`, atualize esse documento no mesmo commit
   lógico da mudança de código. Não deixe o documento desatualizado "para
   depois".
10. **Executar a avaliação de manutenção de skills** — ver
    `pastoreio-manter-agents-skills`: esta mudança torna
    `pastoreio-executar-ronda` ou `pastoreio-investigar-alocacao`
    desatualizada? Torna-se uma regra global (`AGENTS.md`)? Aplique a
    atualização como parte da mesma tarefa.

## Validação contra dados reais (quando aplicável)

Regras de negócio deste projeto historicamente esconderam bugs sutis que
só apareceram ao validar contra dados reais da spreadsheet (ex.: cotas
tratadas como pool total em vez de por mês, exceção de tema comparando o
campo errado, "reorganização de lacuna" inicialmente permitindo puxar um
outsider). Depois de os testes unitários passarem, quando a mudança afeta
um grupo já validado (ver `GRUPOS_VALIDADOS.md`), prefira reexecutar (ou
simular) o cálculo contra uma cópia `CLAUDE_*` real e comparar o resultado
com o esperado antes de dar a mudança como concluída. Escrita produtiva só
pode ocorrer quando aquele processo específico já foi promovido pelo
utilizador e o script declara a allowlist produtiva no `SpreadsheetGuard`.

## Se a mudança for descrita em prosa por alguém, não em código

Para uma mudança de algoritmo não trivial descrita em linguagem natural,
reformule-a como uma tabela estruturada contra um caso real (nomes, datas,
resultado esperado) e peça confirmação explícita antes de escrever código.
Isto já preveniu implementações erradas de regras ambíguas neste projeto
(ver histórico de correções da fase CEIA ALTERNADA). Nunca considere a
tarefa terminada só porque o código compila — só porque os testes passam e
a regra foi confirmada é que está pronta.
