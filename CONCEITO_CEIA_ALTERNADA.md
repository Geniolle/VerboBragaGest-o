# Conceito de CEIA ALTERNADA

Este documento existe para que qualquer pessoa (ou agente) que trabalhe neste
codigo entenda a regra de `CEIA ALTERNADA` sem precisar redescobrir isso de
novo.

## O que e

`CEIA ALTERNADA` e uma regra de **elegibilidade e rodizio prioritario** para o
**1o domingo do mes** (`slot.semana_do_mes == 1`) de um grupo
`DEPARTAMENTO + FUNCAO + DOMINGO` (ex.: `D. MINISTROS / MINISTRO / DOMINGO`),
data em que ocorre a Ceia do Senhor.

### Ordem de decisao em DOMINGO:

1. **CEIA ALTERNADA**, quando aplicavel (1o domingo do mes com membros `ceia_alternada == True`);
2. **SEMANA PREFERENCIAL** (nos demais casos);
3. **PRIORIDADE NA ALOCACAO** (menor numero = maior prioridade).

No primeiro domingo com CEIA ALTERNADA, a precedencia e absoluta:

$$\text{CEIA ALTERNADA no primeiro domingo} > \text{SEMANA PREFERENCIAL} > \text{PRIORIDADE}$$

Ou seja: um colaborador **NAO** pode ficar automaticamente com todos os
primeiros domingos apenas porque tem `SEMANA PREFERENCIAL = 1`. Quem manda
primeiro e o rodizio/ciclo da CEIA. Da mesma forma, colaboradores com
`CEIA ALTERNADA = TRUE` e `SEMANA PREFERENCIAL != 1` (ex.: semana 2) **NAO** sao
descartados no 1o domingo: eles participam normalmente do ciclo da CEIA.

## Como funciona o rodizio da CEIA

Considere todos os colaboradores elegiveis do grupo que tenham `CEIA ALTERNADA = TRUE`.
Se o grupo tem $N$ colaboradores com CEIA ativa:

1. **Ciclo completo**: cada colaborador elegivel deve participar exatamente uma vez
   antes de qualquer repeticao.
2. **Sem repeticao prematura**: enquanto existirem colaboradores desse ciclo que
   ainda nao participaram, ninguem que ja participou pode repetir.
3. **Novo ciclo**: somente depois que todos os colaboradores elegiveis tiverem
   participado uma vez e que um novo ciclo de CEIA pode comecar.
4. **Historico persistente**: o algoritmo olha para tras (historico das Rondas/meses
   anteriores via `estado.historico_vencedores_ceia` e a funcao
   `calcular_participantes_ciclo_ceia`) para descobrir quem ja participou no
   ciclo atual e quem ainda falta. Entre execucoes, esse historico vem dos
   vencedores reais ja persistidos em agenda, confirmados por auditoria/
   intencao `CEIA`; nao e recalculado pelo motor atual como se o passado
   ainda estivesse aberto. Nao e necessario preencher todos os meses de uma
   vez.
5. **Filtros continuam obrigatorios**: impedimentos reais (Excluse, aniversario,
   descanso cruzado, vizinhanca) continuam eliminando candidatos no dia da vaga.
   Se a pessoa da vez estiver impedida, o motor busca o proximo elegivel dentro
   do ciclo. A pessoa impedida **nao** e considerada como tendo cumprido a sua
   vez: ela continua pendente no ciclo para o proximo 1o domingo.
6. **Desempate no ciclo**: entre os candidatos elegiveis do ciclo que ainda nao
   participaram, a ordem de escolha segue a `PRIORIDADE NA ALOCACAO` (menor
   numero = maior prioridade).

Quando todos os participantes vigentes com `CEIA ALTERNADA=true` ja aparecem
no ciclo atual, esse ciclo fecha imediatamente. A proxima CEIA inicia um novo
ciclo do inicio da ordem vigente; o ultimo participante do ciclo anterior nao
vira ancora nem tem preferencia para repetir. Se o primeiro da ordem estiver
bloqueado por impedimento real naquela data, o motor avalia o proximo
elegivel, e o bloqueado continua pendente.

O ciclo e sempre calculado contra o conjunto vigente de participantes com
`CEIA ALTERNADA=true`, sem reescrever o passado:

- se um novo participante entra no cadastro, ele fica pendente ate participar;
- se um participante historico deixou de ter `CEIA ALTERNADA=true`, seu nome
  continua no historico real, mas deixa de contar como pendencia do conjunto
  atual.

## Onde vive no codigo

- `RegraColaborador.ceia_alternada: bool` (campo de cadastro, aba `BP ALGORITIMO`)
  -- ver `src/pastoreio_orquestrador/models.py`.
- `EstadoExecucaoGrupo.historico_vencedores_ceia: list[str]` -- guarda a lista
  cronologica de quem venceu a CEIA. Atualizado em `_registrar_vencedor` sempre
  que `eh_slot_ceia(slot)`.
- `calcular_participantes_ciclo_ceia(nomes_ceia, historico_ceia)` em
  `src/pastoreio_orquestrador/motor.py`: percorre o historico cronologico,
  detectando os ciclos completos e devolvendo o conjunto de quem ja participou
  no ciclo atual incompleto.
- `carregar_historico_ceia_persistido(...)` em
  `src/pastoreio_orquestrador/carregamento.py`: reconstrói, entre execucoes,
  a sequencia cronologica da CEIA a partir do vencedor persistido em agenda
  confirmado por auditoria/intencao `CEIA`. Esta funcao existe para evitar
  que replay de Rondas antigas com uma versao nova do algoritmo altere o
  significado de uma CEIA que ja aconteceu.
- `eh_slot_ceia(slot: SlotAgenda) -> bool`: verifica se `slot.semana_do_mes == 1`
  e dia e `DOMINGO`.
- `avaliar_candidatos_para_slot` em `motor.py`:
  - No 1o domingo com CEIA: so concorrem quem tem `ceia_alternada == True` e
    ainda nao participou no ciclo atual. `semana_preferencial` nao filtra
    esses candidatos.
  - Nos demais domingos: `semana_preferencial` filtra normalmente quem pediu
    outra semana.
- `chave_ordenacao_candidato` em `motor.py`:
  - No 1o domingo de CEIA, `rank_semana_preferencial` e neutralizado (0 para todos
    os candidatos da CEIA), permitindo que a `prioridade` ordene os elegiveis
    do ciclo.
  - Fora do 1o domingo de CEIA, `rank_semana_preferencial` tem precedencia total
    sobre `prioridade` (rank 0 > rank 1 > rank 2).

## CEIA, hierarquia normal e REPETICAO MENSAL

CEIA tem ciclo proprio e nao move a hierarquia normal de MINISTRO. Em auditoria,
uma decisao de CEIA deve aparecer conceitualmente como `CONSOME_HIERARQUIA=false`.

Isso nao significa que CEIA seja invisivel para a contagem mensal. Para DOMINGO,
uma participacao na CEIA conta como ocorrencia mensal do colaborador para
`REPETICAO MENSAL`.

Exemplos:

- `REPETICAO MENSAL=1` + CEIA no primeiro domingo: a quota mensal ja esta
  satisfeita. Se a hierarquia normal chegar nessa pessoa mais tarde no mesmo
  mes, ela deve ser pulada e nao consome o cursor normal.
- `REPETICAO MENSAL=2` + CEIA: falta uma ocorrencia naquele mes, respeitando
  todos os demais filtros.
- `ALOCAR TODOS OS MESES=true` nao muda essa aritmetica: em cada mes abrangido,
  a necessidade e de `R` ocorrencias totais, contando CEIA quando houver.

Arquiteturalmente, isto sao duas propriedades diferentes da mesma decisao:

- CEIA tem `CONSOME_HIERARQUIA=false`.
- CEIA tem `CONTA_REPETICAO_MENSAL=true`.

Nunca use o facto de uma pessoa ter participado na CEIA para atualizar o
cursor normal de DOMINGO. Da mesma forma, nunca ignore a CEIA ao calcular
quantas ocorrencias mensais essa pessoa ja possui.

## Nao confundir com `reserva_ceia_penalizada`

Existe outro mecanismo, mais antigo, em `chave_ordenacao_candidato`
(`ContextoDesempate.funcao_tem_restricao_ceia` / `slot_e_ceia`): ele
**penaliza no desempate** (empurra para o fim da fila) quem tem
`ceia_alternada == True` em slots que NAO sao CEIA, quando a funcao tem
"restricao de ceia" -- ou seja, reserva essas pessoas para a vaga de CEIA
em vez de gasta-las nos domingos comuns. Esse e um criterio de ORDENACAO
entre candidatos ja elegiveis, diferente do filtro de ELEGIBILIDADE descrito
acima. Os dois mecanismos coexistem e resolvem problemas diferentes:

- `reserva_ceia_penalizada`: evita "gastar" quem serve para CEIA em domingos
  comuns.
- Filtro de ciclo de CEIA: decide quem de fato ocupa a vaga da CEIA, forcando
  alternancia justa entre todos os membros do grupo.

## Algoritmo em fases (definido com o Clayton em 2026-09-06)

Para um grupo `DEPARTAMENTO + FUNCAO + DOMINGO` que tenha pelo menos um
colaborador com `ceia_alternada == True`, `alocar_grupo` NAO processa os
slots simplesmente em ordem cronologica do inicio ao fim. Em vez disso,
roda em 4 fases (implementado em `_alocar_grupo_domingo_ceia_alternada` em
`motor.py`):

- **Fase 1 -- CEIA primeiro, ciclo completo inteiro**: preenche TODOS os
  slots de 1o domingo do mes (CEIA) do ciclo completo, em ordem
  cronologica, antes de tocar em qualquer slot normal. Usa o filtro de
  elegibilidade (`ceia_alternada=True` + nao repetir `ultimo_vencedor_ceia`)
  e registra a CEIA como uma ocorrencia mensal para `REPETICAO MENSAL`.
- **Fase 2 -- mantém a hierarquia normal completa**: CEIA não cria exclusão
  global para todas as datas normais da Ronda. A elegibilidade é reavaliada
  data a data. Se a pessoa fez CEIA no mesmo mês e já atingiu
  `REPETICAO MENSAL`, ela fica inelegível naquele mês; uma CEIA futura de
  novembro/dezembro não remove essa pessoa da rotação normal de outubro.
- **Fase 3 -- uma unica passada pelas datas restantes**: processa as datas
  normais (nao-CEIA) em ordem cronologica, escolhendo por prioridade dentro
  do pool remanescente da Fase 2, respeitando a cota mensal normalmente.
  Quem **nao** tem `ALOCAR TODOS OS MESES=true` sai do pool assim que e
  escalado (nao repete dentro desta fase -- e uma passada unica). Quem
  **tem** `ALOCAR TODOS OS MESES=true` continua disponivel para os proximos
  meses (ainda preso a cota mensal, entao nao dobra no mesmo mes).
- **Fase 4 -- preenchimento de lacunas**: datas que sobrarem sem fechar na
  Fase 3 (nenhum candidato -- nem via resgate -- sobrevive no pool
  remanescente daquele slot) sao preenchidas recorrendo a hierarquia de
  colaboradores com `ALOCAR TODOS OS MESES = false` **E**
  `ALOCAÇÃO EXTRA` marcado (corrigido em 2026-09-07, pedido do Clayton: so
  quem esta explicitamente disponivel para cota extra pode ser considerado
  para lacunas -- nao vale pegar qualquer um so pela prioridade). Mesmo nessa
  fase, um domingo normal nao deve recolocar alguem que ja satisfez
  `REPETICAO MENSAL` por causa de CEIA no mesmo mes. Colaboradores com
  `ALOCAR TODOS OS MESES=true` nunca entram nesse preenchimento de lacunas.

  **Atencao -- interacao com o resgate (2026-09-07):** o resgate flexibiliza
  a cota local/capacidade do periodo, mas nao deve recolocar como MINISTRO
  normal quem ja completou `REPETICAO MENSAL` por CEIA no mesmo mes. A Fase
  4 so entra em jogo quando o pool da Fase 3 fica **totalmente vazio** para
  aquele slot (nenhum candidato remanescente, nem para resgate).

## Resgate (dentro de qualquer fase) -- corrigido em 2026-09-07

Sempre que a avaliacao normal de um slot (`avaliar_candidatos_para_slot`
com `ignorar_vizinhanca_e_descanso=False`) nao deixa ninguem elegivel, o
motor tenta de novo com `ignorar_vizinhanca_e_descanso=True`. Esse modo de
resgate flexibiliza:

- conflito de vizinhanca (mesmo colaborador numa linha vizinha);
- descanso minimo de 7 dias;
- cota local/capacidade do periodo.

Mas, em DOMINGO, se a pessoa ja atingiu `REPETICAO MENSAL` por uma ocorrencia
de CEIA, o resgate nao deve recoloca-la como MINISTRO normal no mesmo mes
apenas por causa de `ALOCAÇÃO EXTRA`.

O resgate continua respeitando `Excluse`, aniversario (ver secao abaixo) e
compatibilidade de tema. So marca `SEM ALOCAÇÃO` se, mesmo ignorando
vizinhanca/descanso/cota, **nenhum** candidato sobrar (ex.: pool vazio,
todos bloqueados por `Excluse`/aniversario, ou tema incompativel).

## Aniversario -- novo filtro obrigatorio, 2026-09-07

Mesmo estatuto do `Excluse` (bloqueia em toda passada, normal e resgate, e
tambem dentro do swap de `_tentar_reorganizar_lacuna`), mas a fonte e outra
sheet: a aba `BP SERVICE`, coluna `DATA NASCIMENTO`, casada por `NOME`.
Ninguem pode ser alocado no proprio dia de aniversario (dia+mes; o ano e
ignorado, pois aniversario e recorrente). `carregar_aniversarios()`
(`carregamento.py`) le a aba uma vez e devolve `{NOME: data_de_nascimento}`;
`esta_bloqueado_por_aniversario()` (`motor.py`) faz a comparacao.

Caso real que motivou a regra: Patricia Lopes nasceu em 25/10 e havia sido
alocada em 25/10/2026 (Ronda 1) antes desta regra existir -- apos a
correcao, essa data passou a Davi Fenner e Patricia foi realocada para
15/11/2026.

## Compatibilidade de tema (`is_tema_compativel`) -- corrigido em 2026-09-07

A checagem de tema (P1/P2/P3, Fase 0 do bloco de licoes) so se aplica a
slots de **QUARTA-FEIRA**. Em qualquer outro dia da semana -- em particular
**DOMINGO** -- o tema nunca bloqueia um candidato, mesmo que exista um
`requisito_tema` calculado para aquele slot.

Antes da correcao, a funcao tentava fazer essa mesma excecao comparando
`regra.funcao` (que para este grupo vale sempre `"MINISTRO"`) contra o
literal `"D. MINISTROS"` (que e o `DEPARTAMENTO`, um campo diferente). Essa
comparacao nunca dava verdadeira, entao a excecao nunca disparava de fato,
e o tema podia acabar bloqueando candidatos tambem aos domingos. O criterio
certo depende so do dia da semana, nao da funcao/departamento.

### Exemplo historico da ordem em fases

O exemplo abaixo documenta a motivacao original da ordem em fases: preencher
CEIA primeiro, depois as datas normais, depois lacunas. Ele nao deve ser lido
como autorizacao para ultrapassar `REPETICAO MENSAL`. Na regra atual, se uma
pessoa tem `REPETICAO MENSAL=1` e ja fez CEIA naquele mes, ela fica inelegivel
para nova vaga normal de MINISTRO no mesmo mes.

Grupo: Clayton Lopes (prioridade 1, `ALOCAR TODOS OS MESES=true`), Patricia
Lopes (prioridade 2), Caio Lima (prioridade 3), Ana Lima (prioridade 4),
Andre Luiz (prioridade 5), Suzana Fonseca (prioridade 6), Davi Fenner
(prioridade 7) -- todos com `ceia_alternada=true`.

| Data | Slot | Vencedor | Fase / motivo |
|---|---|---|---|
| 04/10 | CEIA | Clayton Lopes (prioridade 1) | Fase 1, sem vencedor anterior |
| 11/10 | normal | Patricia Lopes (prioridade 2) | Fase 3; Clayton pulado porque a CEIA ja satisfez sua 1a ocorrencia de outubro |
| 18/10 | normal | Clayton Lopes (prioridade 1, ATM) | Obrigacao mensal: segunda ocorrencia de outubro; nao move cursor |
| 25/10 | normal | Caio Lima (prioridade 3) | Retoma a hierarquia depois de Patricia |
| 01/11 | CEIA | Patricia Lopes (prioridade 2) | Fase 1, Clayton bloqueado (repeticao) |
| 08/11 | normal | Clayton Lopes (prioridade 1, ATM) | Fase 3; volta pq novembro ainda nao usado por ele |
| 15/11 | normal | Ana Lima (P4) | Retoma a hierarquia depois de Caio |
| 22/11 | normal | Clayton Lopes (prioridade 1, ATM) | Obrigacao mensal: segunda ocorrencia de novembro; nao move cursor |
| 29/11 | normal | Andre Luiz (prioridade 5) | Retoma a hierarquia depois de Ana |

Resultado conceitual: todos os 7 colaboradores aparecem na Ronda, respeitando
o ciclo de CEIA e a quota mensal vigente. Antes deste algoritmo em fases, um
processamento puramente cronologico com desempate so por prioridade deixava
Suzana e Davi (as prioridades mais baixas) de fora para sempre, porque
sempre sobrava alguem de prioridade menor com cota livre antes deles em
qualquer mes (ver historico de correcao no `MEMORY.md`/memoria do projeto).

Ver tambem [[CONCEITO_CICLO.md]] para o conceito de rotacao/ciclo em que
essa regra se encaixa.
