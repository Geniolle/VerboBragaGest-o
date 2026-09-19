---
name: pastoreio-investigar-alocacao
description: Investiga decisões de alocação do Pastoreio Orquestrador, incluindo candidatos rejeitados, SEM ALOCAÇÃO, resgate, quotas, Excluse, aniversário, descanso, vizinhança de datas, tema/nível e rodízio. Use para explicar por que alguém foi/não foi escalado, apareceu repetido, ficou fora, entrou por resgate, ou por que um slot deu SEM ALOCAÇÃO. Não use para alterar regras (pastoreio-alterar-regra) nem para gerar uma Ronda nova (pastoreio-executar-ronda).
---

# Investigar uma decisão de alocação

Investigação **read-only**: nunca escreva, apague ou altere nenhuma aba
(nem original nem `CLAUDE_*`) só para investigar. Ler é sempre permitido em
qualquer aba (`guard.read_worksheet`).

Ver [`../../../CONCEITO_PRIORIDADES.md`](../../../CONCEITO_PRIORIDADES.md)
para a ordem exata de filtros obrigatórios e critérios de desempate, e
[`../../../CONCEITO_CEIA_ALTERNADA.md`](../../../CONCEITO_CEIA_ALTERNADA.md)
para as 4 fases de alocação de grupos DOMINGO com CEIA ALTERNADA — não
reescreva essas regras aqui, use-as como checklist de onde procurar
evidência.

## Princípio: não adivinhar, produzir evidência concreta

Toda explicação deve apontar para um dado real (linha da sheet, valor de
campo, resultado de uma chamada de função) — nunca uma suposição sobre "o
que provavelmente aconteceu". Se a causa não está clara a partir dos dados,
diga isso explicitamente em vez de inventar uma explicação plausível.

## Onde procurar evidência, por categoria

Percorra estes pontos na ordem em que `motor.py` os aplica (etapa 1 =
filtros obrigatórios, etapa 2 = desempate — ver `CONCEITO_PRIORIDADES.md`):

1. **Grupo/slot**: confirme `DEPARTAMENTO + FUNÇÃO + DIA DA SEMANA` e a
   data exata do slot em questão. Erros de investigação começam quase
   sempre por comparar o grupo errado.
2. **Cota mensal/local**: `demanda.mapa_limites_locais` /
   `estado.uso_no_mes` / `estado.uso_por_mes` /
   `estado.ocorrencias_mensais_externas` — o candidato já usou a cota do
   mês? Em DOMINGO, conte CEIA + MINISTRO para `REPETIÇÃO MENSAL`: uma CEIA
   já satisfaz uma ocorrência mensal, embora não mova o cursor normal.
3. **Excluse**: `esta_bloqueado_por_excluse` — o nome do candidato aparece
   em `slot.papeis` ou `slot.assiduidade` sob alguma função declarada em
   `ID_<DEPARTAMENTO>` naquela data? (ler a aba `Excluse` real, coluna
   `ID_<DEPARTAMENTO>`, e a linha correspondente de `AppAnualGlobal`).
4. **Aniversário**: `esta_bloqueado_por_aniversario` — a data de
   nascimento em `BP SERVICE` (coluna `DATA NASCIMENTO`) bate dia+mês com
   o slot?
5. **Descanso cruzado / descanso mínimo**:
   `esta_bloqueado_por_descanso_cruzado` / `respeita_descanso_minimo` — o
   candidato serviu recentemente (7 dias) no mesmo grupo ou no dia cruzado
   (domingo↔quarta)? Verifique se há `sinc_colaborador` a isentar.
6. **Tema/nível (só QUARTA-FEIRA)**: `is_tema_compativel` — o `TEMA`
   cadastrado do colaborador bate com o requisito calculado pelo slot
   (SENIOR/PLENO/JUNIOR)?
7. **Rodízio por nível**: `chave_rodizio_nivel` — o candidato já venceu
   recentemente dentro da mesma janela de nível?
8. **Semana preferencial**: `semana_preferencial != 0` e não bate com
   `slot.semana_do_mes`? Filtro obrigatório (etapa 1.8) — não apenas
   desempate.
9. **Vizinhança de datas**: `viola_vizinhanca_de_datas` — o candidato
   já venceu a data imediatamente anterior ou seguinte na sequência
   cronológica do grupo?
10. **CEIA ALTERNADA** (1º domingo do mês): `ceia_alternada == True`
    obrigatório para concorrer; ciclo completo entre todos os membros com
    CEIA ALTERNADA via `calcular_participantes_ciclo_ceia` /
    `estado.historico_vencedores_ceia`; sobrepõe semana preferencial e
    prioridade. Ver `CONCEITO_CEIA_ALTERNADA.md`.
11. **Resgate**: se ninguém sobreviveu à passada normal, o motor tenta de
    novo com `ignorar_vizinhanca_e_descanso=True` — só quem tem
    `ALOCAR TODOS OS MESES=false` **e** `ALOCAÇÃO EXTRA=true` participa, e
    aí Excluse/aniversário/vizinhança continuam bloqueando. Em DOMINGO,
    se a quota de `REPETIÇÃO MENSAL` já foi satisfeita por CEIA naquele mês,
    isso também bloqueia nova vaga normal; CEIA conta para quota mesmo sem
    consumir cursor.
12. **SEM ALOCAÇÃO**: confirme que é genuinamente impossível — todo o pool
    elegível (normal + resgate + reorganização de lacuna, se o grupo usa
    CEIA ALTERNADA) foi eliminado por algum filtro da lista acima. Não
    aceite "SEM ALOCAÇÃO" como resposta final sem verificar isso.
13. **Histórico**: `historico_total` (de `LOG ALGORITIMO`, Status="Ativo")
    e `zumbis_prioritarios` (de `BP LOG`, `DISPONIBILIDADE=TRUE`) — afetam
    prioridade efetiva e podem explicar uma alocação aparentemente "fora de
    ordem".
14. **Auditoria já gravada**: `CLAUDE_LOG_AUDITORIA` (se a Ronda já foi
    executada com auditoria ativa) já contém motivo, runner-up e ordem
    completa de desempate para cada decisão — confira ali antes de
    recalcular tudo manualmente. Para DOMINGO, confira também
    `CONSOME_HIERARQUIA`: somente linhas `TRUE`, confirmadas contra a
    alocação real em `AppAnualGlobal`/`CLAUDE_AppAnualGlobal`, movem o
    cursor da hierarquia normal entre execuções. CEIA, repetição mensal,
    ATM, resgate e lacuna não movem esse cursor. Para explicar repetição
    mensal, confira também `CONTA_REPETICAO_MENSAL`,
    `OCORRENCIAS_MES_ANTES`, `OCORRENCIAS_MES_DEPOIS` e `LIMITE_MENSAL`
    quando existirem.

## Investigar continuidade da hierarquia de DOMINGO

Quando alguém parece ter sido "pulando" ou "reiniciado" entre execuções
mensais, não procure uma variável em memória. Reproduza a reconstrução:

1. leia a agenda persistida e a auditoria;
2. filtre as decisões do mesmo departamento/função/dia com
   `CONSOME_HIERARQUIA=TRUE`;
3. confirme que cada decisão existe na agenda real na mesma data;
4. pegue a última âncora válida em ordem cronológica;
5. localize essa pessoa na hierarquia atual de `BP ALGORITIMO`;
6. avance circularmente para o próximo elemento elegível.

Se auditoria e agenda divergirem, reporte inconsistência em vez de inferir
o cursor por nome ou prioridade.

Para diagnosticar uma Ronda de DOMINGO sem escrever, use
`scripts/diagnosticar_cursor_domingo.py`: ele mostra data, tipo de decisão,
intenção da vaga, obrigação satisfeita, `CONSOME_HIERARQUIA`, cursor
antes/depois e candidatos avaliados. Lembre que candidato analisado e
rejeitado não consome cursor; repetição mensal, obrigação de
`ALOCAR TODOS OS MESES`, CEIA, resgate e lacuna também não avançam a
hierarquia normal.

Ao investigar domingos, separe sempre `TIPO_DIA`, intenção e política de
seleção. `DOMINGO_NORMAL` não significa automaticamente `NORMAL_ROTATION`:
pode ser `MONTHLY_REPEAT`, `EVERY_MONTH_OBLIGATION` ou `GAP_FILL`. Uma lacuna
explica por que a data precisa ser preenchida, mas a pessoa deve vir da
política registrada para aquela intenção, não de uma fila implícita. Para
comparar a ordem real carregada do BP com a ordem percorrida pelo motor, use
também `scripts/diagnosticar_domingo_hierarquia.py`.

## Como reproduzir uma decisão sem escrever nada

Para confirmar uma hipótese, é válido (e preferível) chamar as funções
puras de `motor.py`/`carregamento.py` diretamente num script/REPL
descartável, lendo dados via `guard.read_worksheet` (sempre permitido) e
sem nunca chamar nenhum método de escrita do Guard. Ex.: reconstruir
`SlotAgenda`, `EstadoExecucaoGrupo` e chamar
`esta_bloqueado_por_excluse(...)` ou `avaliar_candidatos_para_slot(...)`
diretamente para o caso em questão, como já foi feito para casos reais
documentados no histórico do projeto.

## Reportar o resultado

Estruture a resposta como: slot investigado → filtro(s) que decidiram o
resultado → evidência concreta (valor da célula, nome do campo, linha da
sheet) → conclusão. Se a investigação revelar um bug real no motor (não
apenas um resultado correto mas surpreendente), pare e sinalize — corrigir
o motor é trabalho da skill `pastoreio-alterar-regra`, não desta.
