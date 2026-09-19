# AGENTS.md — Pastoreio Orquestrador

Leitura obrigatória antes de qualquer trabalho neste repositório. Este
ficheiro contém só regras permanentes e universais. Workflows específicos
(executar uma Ronda, investigar uma alocação, alterar uma regra, validar um
grupo) vivem em `.agents/skills/` — ver secção "Skills" abaixo.

## Visão geral do projeto

- Projeto Python (`uv`, `pyproject.toml`), porte do algoritmo Google Apps
  Script `Algoritimo_Input_Escala_Automatico_v63` usado na spreadsheet
  "AppPastoreioGestão".
- Pacote principal: `src/pastoreio_orquestrador/`. O motor de regras e
  alocação está centralizado em `motor.py` — é a fonte de verdade do
  algoritmo; nunca duplique a lógica dele em documentação ou em skills,
  apenas referencie.
- `scripts/` contém os processos operacionais executáveis (sincronização,
  preenchimento de Ronda por grupo, checklist de validação, scripts
  utilitários pontuais).
- `tests/` é a prova executável do comportamento — qualquer alteração de
  regra de negócio deve vir acompanhada de teste.
- Google Sheets é a origem e o destino operacional dos dados (não há banco
  de dados local). Acesso via `gspread`, credenciais fora do versionamento
  (`credentials/`, `.env`, ambos no `.gitignore`).
- Documentos `CONCEITO_*.md` na raiz explicam em profundidade regras de
  negócio específicas (ciclo/rotação, prioridades, CEIA alternada). Leia-os
  quando a tarefa tocar nesses conceitos — não copie o conteúdo deles para
  outro lugar, referencie.
- A continuidade da hierarquia normal de DOMINGO entre execuções mensais é
  reconstruída a partir de histórico persistido: agenda real
  (`AppAnualGlobal`/`CLAUDE_AppAnualGlobal`) + auditoria
  (`LOG_AUDITORIA`/`CLAUDE_LOG_AUDITORIA`) com `CONSOME_HIERARQUIA=TRUE`.
  Não implemente cursor mensal baseado em variável global, cache local ou
  estado de processo.
- Em DOMINGO, CEIA e MINISTRO compartilham a contagem de participação mensal
  para `REPETIÇÃO MENSAL`: uma CEIA já conta como uma ocorrência do mês.
  Isso não altera a regra anterior de cursor: CEIA continua com ciclo próprio
  e `CONSOME_HIERARQUIA=FALSE`.
- Em DOMINGO, só alocação NORMAL efetivamente escolhida pela hierarquia move
  o cursor normal. Repetição mensal, obrigação de `ALOCAR TODOS OS MESES`,
  CEIA, resgate, lacuna e candidatos apenas analisados/rejeitados não movem
  esse cursor.
- Regras novas não devem ser implementadas como um `if` solto no motor antes
  de identificar a que conceito do domínio pertencem: elegibilidade,
  obrigação, ranking/hierarquia, intenção da vaga, transição de estado ou
  auditoria. Quando tocar DOMINGO, prefira políticas em
  `domain/domingo/`; quando tocar QUARTA-FEIRA, preserve os conceitos de
  tema/nível próprios daquele contexto.
- DOMINGO e QUARTA-FEIRA são contextos distintos. P1/P2/P3 pertencem ao
  domínio de QUARTA-FEIRA (tema/nível/classificação) e não devem ser usados
  como nome para a hierarquia numérica de DOMINGO, que é prioridade/ordem.
- `GRUPOS_VALIDADOS.md` é o registo oficial de quais combinações
  `DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA` já tiveram pelo menos um teste de
  integração real revisado por humano.

## Regra de segurança máxima (inegociável)

**As abas originais da spreadsheet são somente leitura.** Nunca escrever,
limpar, apagar ou sobrescrever uma aba original. Qualquer escrita de
desenvolvimento/teste ocorre exclusivamente em abas com prefixo `CLAUDE_`
(ex.: `CLAUDE_AppAnualGlobal`, `CLAUDE_BP ALGORITIMO`).

Toda nova escrita **deve** passar por `sheets_client.SpreadsheetGuard`
(`update_worksheet`, `update_cell`, `batch_update_cells`, `append_row`,
`append_rows`, `create_worksheet`, `ensure_worksheet_with_header`,
`delete_worksheet`) — cada um desses métodos valida o prefixo `CLAUDE_` e
levanta `TentativaDeAlteracaoOriginalError` caso contrário. Código novo
**não deve** chamar métodos de escrita/delete diretamente num objeto
`gspread.Worksheet` (`ws.update_cell(...)`, `ws.update(...)`,
`ws.append_row(...)`, `spreadsheet.del_worksheet(...)`, etc.) — isso
contorna a trava do Guard mesmo que, no caso concreto, o `Worksheet` em
questão já seja uma cópia `CLAUDE_`.

Todos os scripts de produção atuais (`preencher_claude_appanualglobal_*.py`,
`limpar_*.py`) e scripts de teste tocados recentemente devem usar o Guard
para escrita. Se encontrar escrita direta em `gspread.Worksheet`, trate
como dívida a corrigir quando tocar no arquivo.

Escrita permitida/proibida, resumido:

| Ação | Aba original | `CLAUDE_*` |
|---|---|---|
| Ler | Permitido | Permitido |
| Duplicar (`duplicate_sheet_for_testing`) | Permitido (fonte) | — |
| Escrever/atualizar | **Proibido** | Permitido, via Guard |
| Apagar | **Proibido** | Permitido, via Guard, quando o workflow justificar |

## Testes

Depois de qualquer alteração de código, rode:

```
uv run pytest
```

Todos os testes existentes devem passar. Não hardcode a quantidade de
testes em nenhum documento (o número muda com o tempo) — use linguagem
como "toda a suite de testes deve passar". Se algo falhar: investigue a
causa raiz, não ignore, não esconda, e não altere o teste só para ficar
verde sem entender por que falhou.

## Skills

Workflows especializados e repetíveis vivem em `.agents/skills/`, cada um
com o seu `SKILL.md`. Não duplique a lógica do `motor.py` nem o conteúdo
dos `CONCEITO_*.md` dentro de uma skill — referencie.

Skills atuais:

- `pastoreio-manter-agents-skills` — meta-skill de governança desta própria
  estrutura (ver secção seguinte).
- `pastoreio-executar-ronda` — gerar/preparar uma Ronda de alocação para um
  grupo.
- `pastoreio-investigar-alocacao` — explicar (read-only) por que alguém foi
  ou não foi alocado.
- `pastoreio-alterar-regra` — modificar regra de negócio/comportamento do
  motor.
- `pastoreio-validar-grupo` — introduzir e validar uma combinação
  `DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA` em `GRUPOS_VALIDADOS.md`.

## Agent/Skill Maintenance (governança permanente)

Esta regra é permanente e faz parte do workflow normal de qualquer tarefa
significativa neste repositório — não é opcional nem precisa ser pedida
explicitamente pelo utilizador.

### Antes de iniciar uma tarefa significativa

Avalie:

1. Qual é o tipo de processo solicitado?
2. Existe uma skill que já cobre esse workflow?
3. A skill ainda representa o comportamento atual do código?
4. A tarefa introduz conhecimento ou procedimento reutilizável?
5. A mudança afeta uma regra universal do projeto?

Se houver dúvida sobre como classificar a mudança, use a skill
`pastoreio-manter-agents-skills` — ela contém a árvore de decisão completa.

### Antes de finalizar qualquer tarefa significativa

Repita a avaliação e escolha uma destas ações:

- **A. Nenhuma alteração** — tarefa pontual, correção local, ou mudança de
  parâmetro sem novo procedimento reutilizável.
- **B. Atualizar uma skill existente** — o processo já existe mas ganhou
  nova etapa, validação, regra, script ou caso suportado.
- **C. Criar nova skill** — só quando existir um workflow realmente novo,
  distinto e reutilizável. Nunca crie uma skill por script, função,
  departamento, colaborador, coluna ou ajuste pequeno. Um novo grupo
  `DEPARTAMENTO###FUNÇÃO###DIA` que segue o mesmo processo de sempre reusa
  `pastoreio-executar-ronda`/`pastoreio-validar-grupo` — não vira skill
  nova.
- **D. Atualizar `AGENTS.md`** — quando a mudança é uma regra transversal a
  todo o projeto (nova regra de segurança, novo padrão obrigatório de
  testes, nova arquitetura obrigatória, nova política de configuração).
- **E. Reorganizar skills** — quando duas ou mais skills começam a
  sobrepor responsabilidade: fundir, dividir, renomear ou remover
  duplicação. Nunca manter duas skills concorrentes para o mesmo workflow
  sem motivo justificado.

Manutenções de documentação agente/skill que sejam consequência direta da
mudança pedida (ex.: alterar o processo de Ronda torna
`pastoreio-executar-ronda` desatualizada) fazem parte da mesma tarefa — não
é preciso pedir autorização à parte para isso.

### Agent/Skill impact check (obrigatório ao final de alteração significativa)

Antes de considerar uma tarefa concluída, pergunte:

- Introduzi um workflow novo?
- Alterei um workflow existente?
- Introduzi uma regra global?
- Alguma skill agora está desatualizada?
- Existe duplicação entre skills?

Se a resposta a qualquer uma for sim, atualize a estrutura (`AGENTS.md`
e/ou `.agents/skills/`) antes de terminar a tarefa.

### Processo totalmente novo, sem skill correspondente

Não comece a programar de imediato. Primeiro: compreenda o processo,
procure implementação e skill semelhantes, e decida se é uma extensão de
algo existente, uma variação, ou um processo genuinamente novo. Só depois
de decidir isso, implemente o código/testes e crie ou atualize a
documentação agente/skill conforme a árvore de decisão de
`pastoreio-manter-agents-skills`.

### O que as skills não são

Skills descrevem o procedimento operacional **atual**. Não são diário de
alterações — não coloque nelas números de testes, nomes de commits, datas
de sessão antiga ou valores temporários. Isso pertence ao Git. Sempre que
código e skill divergirem, investigue e corrija a divergência — o código +
testes + regras de negócio atuais são a fonte principal de verdade; a
skill só descreve o procedimento em torno deles.
