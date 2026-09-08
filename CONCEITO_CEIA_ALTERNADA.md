# Conceito de CEIA ALTERNADA

Este documento existe para que qualquer pessoa (ou agente) que trabalhe neste
codigo entenda a regra de `CEIA ALTERNADA` sem precisar redescobrir isso de
novo.

## O que e (definido em 2026-09-06, apontado pelo Clayton)

`CEIA ALTERNADA` e uma regra de **elegibilidade**, nao de desempate: ela
decide QUEM PODE concorrer a uma vaga especifica, antes de qualquer
hierarquia de prioridade entrar em jogo.

A vaga afetada e sempre o **1o domingo do mes** (`slot.semana_do_mes == 1`)
de um grupo `DEPARTAMENTO + FUNCAO + DOMINGO` (ex.: `D. MINISTROS /
MINISTRO / DOMINGO`) -- essa e a data em que ocorre a Ceia do Senhor.

Regras:

1. **Filtro de elegibilidade**: no 1o domingo do mes, so concorrem
   candidatos com `RegraColaborador.ceia_alternada == True`. Quem tem
   `ceia_alternada == False` e descartado da lista de candidatos daquele
   slot, mesmo que fosse o proximo na prioridade normal.
2. **Sem repeticao sequencial**: quem venceu o slot do 1o domingo na
   rotacao (mes) imediatamente anterior fica bloqueado de vencer o mesmo
   slot na rotacao seguinte, mesmo sendo `ceia_alternada == True`. Isso
   forca alternancia entre pelo menos 2 pessoas elegiveis a cada rotacao.
3. Nos demais domingos do mes (`semana_do_mes != 1`), a regra nao se aplica
   -- todos os candidatos normais concorrem, elegiveis ou nao para CEIA.

## Onde vive no codigo

- `RegraColaborador.ceia_alternada: bool` (campo de cadastro, aba `BP
  ALGORITIMO`) -- ver `src/pastoreio_orquestrador/models.py`.
- `EstadoExecucaoGrupo.ultimo_vencedor_ceia: str | None` -- guarda o nome de
  quem venceu o ultimo slot de 1o domingo do mes processado. Atualizado no
  fim do loop principal sempre que `slot.semana_do_mes == 1`.
- Filtro aplicado em `avaliar_candidatos_para_slot`, em
  `src/pastoreio_orquestrador/motor.py`: quando `slot.semana_do_mes == 1`,
  descarta quem tem `ceia_alternada == False` e quem tem
  `regra.nome == estado.ultimo_vencedor_ceia`.

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
- Filtro de `semana_do_mes == 1` + `ultimo_vencedor_ceia`: decide quem de
  fato ocupa a vaga da CEIA, forcando alternancia.

## Como aplicar isso no codigo (filtro de elegibilidade, dentro de UM slot)

Ao avaliar candidatos para UM slot:

1. Verifique `slot.semana_do_mes` E `slot.dia_da_semana` (o filtro so vale
   para DOMINGO -- "semana_do_mes==1" tambem ocorre em outros dias, ex.: a
   1a quarta-feira do mes, onde CEIA nao se aplica).
2. Se for `1` e DOMINGO (1o domingo do mes = data da CEIA): filtre os
   candidatos para so os com `ceia_alternada == True`, excluindo tambem
   quem esta em `estado.ultimo_vencedor_ceia`. So depois aplique a cascata
   normal de desempate (SEMANA PREFERENCIAL, SEMANA ALTERNADA, PRIORIDADE)
   sobre o que sobrar.
3. Ao registrar o vencedor desse slot, atualize
   `estado.ultimo_vencedor_ceia = vencedor.nome` para bloquear a repeticao
   na proxima rotacao.
4. Nos demais domingos do mes, nao aplique esse filtro -- so a cascata
   normal (que ainda pode penalizar `ceia_alternada == True` via
   `reserva_ceia_penalizada`, se essa funcao tiver restricao de ceia).

Isso e o que `avaliar_candidatos_para_slot` faz, slot a slot. Mas dentro de
um grupo `DOMINGO` que usa CEIA ALTERNADA, a ORDEM em que os slots do ciclo
completo sao processados tambem importa -- ver a proxima secao.

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
  e a cota mensal normalmente.
- **Fase 2 -- remove do pool quem ja ganhou CEIA**: quem venceu um slot de
  CEIA na Fase 1 sai do pool das datas restantes deste ciclo, **exceto**
  quem tem `ALOCAR TODOS OS MESES = true` -- esse continua disponivel
  (ainda precisa aparecer nos outros meses que o ciclo toca).
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
  quem esta explicitamente disponivel para cota extra pode ser puxado alem
  da cota mensal normal -- nao vale pegar qualquer um so pela prioridade).
  Isso inclui gente que a Fase 2 tinha removido (ex.: quem ganhou CEIA),
  desde que tenha `ALOCAÇÃO EXTRA`. Ignora a cota mensal e a cota total do
  periodo (na implementacao: passa `mapa_limites_mensais=None` e um teto
  artificialmente alto para `mapa_limites_locais` nesta fase). Colaboradores
  com `ALOCAR TODOS OS MESES=true` nunca entram nesse preenchimento de
  lacunas.

  **Atencao -- interacao com o resgate (2026-09-07):** como o resgate
  (`ignorar_vizinhanca_e_descanso=True`, ver secao "Resgate" abaixo) agora
  tambem ignora a cota mensal, a propria Fase 3 pode fechar um buraco
  sozinha (usando quem ainda sobra no pool reduzido, mesmo com a cota
  daquele mes ja estourada) ANTES de a Fase 4 ser sequer consultada. A Fase
  4 so entra em jogo quando o pool da Fase 3 fica **totalmente vazio** para
  aquele slot (nenhum candidato remanescente, nem para resgate) -- nao
  quando so a cota estava impedindo.

## Resgate (dentro de qualquer fase) -- corrigido em 2026-09-07

Sempre que a avaliacao normal de um slot (`avaliar_candidatos_para_slot`
com `ignorar_vizinhanca_e_descanso=False`) nao deixa ninguem elegivel, o
motor tenta de novo com `ignorar_vizinhanca_e_descanso=True`. Esse modo de
resgate ignora:

- conflito de vizinhanca (mesmo colaborador numa linha vizinha);
- descanso minimo de 7 dias;
- **cota mensal** (correcao de 2026-09-07, pedido do Clayton -- antes o
  resgate ainda respeitava a cota, o que podia deixar um slot `SEM
  ALOCAÇÃO` mesmo quando so havia UM candidato possivel, so que com a cota
  do mes ja usada).

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

### Exemplo real validado (Ronda 1, D. MINISTROS/MINISTRO/DOMINGO, 04/10/2026 a 29/11/2026)

Grupo: Clayton Lopes (P1, `ALOCAR TODOS OS MESES=true`), Patricia Lopes
(P2), Caio Lima (P3), Ana Lima (P4), Andre Luiz (P5), Suzana Fonseca (P6),
Davi Fenner (P7) -- todos com `ceia_alternada=true`, cota de 1/mes cada.

| Data | Slot | Vencedor | Fase / motivo |
|---|---|---|---|
| 04/10 | CEIA | Clayton Lopes (P1) | Fase 1, sem vencedor anterior |
| 11/10 | normal | Caio Lima (P3) | Fase 3; Clayton pulado (out. ja usado na CEIA) |
| 18/10 | normal | Ana Lima (P4) | Fase 3, proximo na fila |
| 25/10 | normal | Andre Luiz (P5) | Fase 3, proximo na fila |
| 01/11 | CEIA | Patricia Lopes (P2) | Fase 1, Clayton bloqueado (repeticao) |
| 08/11 | normal | Clayton Lopes (P1, ATM) | Fase 3; volta pq novembro ainda nao usado por ele |
| 15/11 | normal | Suzana Fonseca (P6) | Fase 3, proximo na fila |
| 22/11 | normal | Davi Fenner (P7) | Fase 3, esvazia a fila |
| 29/11 | normal | Patricia Lopes (P2) | fila da Fase 3 esgotada -> Fase 4 (hierarquia ATM=false, ignora cota mensal) |

Resultado: todos os 7 colaboradores aparecem (Clayton 2x, Patricia 2x,
Caio/Ana/Andre/Suzana/Davi 1x cada). Antes deste algoritmo em fases, um
processamento puramente cronologico com desempate so por prioridade deixava
Suzana e Davi (as prioridades mais baixas) de fora para sempre, porque
sempre sobrava alguem de prioridade menor com cota livre antes deles em
qualquer mes (ver historico de correcao no `MEMORY.md`/memoria do projeto).

Ver tambem [[CONCEITO_CICLO.md]] para o conceito de rotacao/ciclo em que
essa regra se encaixa.
