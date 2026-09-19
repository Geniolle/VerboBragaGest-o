# Conceito de Ciclo e Ciclo Completo

Este documento existe para que qualquer pessoa (ou agente) que trabalhe neste
codigo entenda exatamente o que significa "ciclo" e "ciclo completo" na
alocacao de escalas, sem precisar redescobrir isso de novo.

## Nomenclatura (definido em 2026-09-06, apontado pelo Clayton)

Para nao confundir com o numero de execucoes/iteracoes do processo, use os
termos assim:

- **Rotacao**: a quantidade de datas de um dia-da-semana dentro de UM
  mes-calendario (ex.: os domingos de outubro/2026 = 4 datas = 1 rotacao;
  os domingos de novembro/2026 = 5 datas = outra rotacao).
- **Gerar Ronda** (numerada: Ronda 1, Ronda 2, Ronda 3...): o processo de
  busca de colaboradores disponiveis para preencher as datas da rotacao
  mensal, avancando rotacao a rotacao (mes a mes) ate fechar um ciclo
  completo. **NAO chame isso de "Ciclo 1, 2, 3"** -- o numero identifica a
  Ronda, nao o ciclo.
- **Ciclo completo**: o ESTADO de uma Ronda quando todas as suas datas estao
  devidamente preenchidas (rotacao base `N` + fechamento do(s) mes(es)
  tocados + `ALOCAR TODOS OS MESES` satisfeito). Nao existe uma quantidade
  fixa de rotacoes (meses) dentro de um ciclo completo -- isso depende da
  quantidade de colaboradores ativos (`N`) em relacao a quantidade de datas
  por mes, e de precisar ou nao estender a Ronda por causa do
  `ALOCAR TODOS OS MESES` (ver secao propria abaixo).

## Ciclo (rotacao base)

Para um grupo definido pela chave `DEPARTAMENTO + FUNCAO + DIA DA SEMANA`
(ex.: `D. MINISTROS / MINISTRO / DOMINGO`), a rotacao base tem `N` datas,
onde `N` = quantidade de colaboradores **ativos** nesse grupo exato (linhas
de `RegraColaborador` em `BP ALGORITIMO`).

**Cuidado:** verifique se nao ha linha de regra duplicada para a mesma
pessoa no mesmo grupo antes de contar `N` -- uma duplicata infla `N`
artificialmente e quebra a distribuicao justa da rotacao (ja aconteceu:
"Clayton Lopes" tinha 2 linhas ativas em D. MINISTROS/MINISTRO/DOMINGO,
fazendo `N=8` em vez de `N=7`).

## Ciclo completo

Um **ciclo NAO e apenas as `N` datas da rotacao**. Um ciclo so e considerado
**completo** quando, alem de cobrir as `N` datas da rotacao, ele tambem
**fecha o(s) mes(es) calendario por inteiro** -- ou seja, nenhum mes pode
ficar dividido ("quebrado") entre um ciclo e o proximo.

Regra pratica: depois de contar as `N` datas da rotacao, se o mes da ultima
data ainda tiver mais ocorrencias daquele dia da semana sobrando, essas
datas extras entram no MESMO ciclo, estendendo-o alem de `N`, ate que o mes
termine por completo.

Esse recorte inicial tambem NAO e, sozinho, a condicao de encerramento da
Ronda. Depois de alocar o bloco, o motor precisa reavaliar o estado real das
obrigacoes:

- todos os colaboradores-base da Ronda ja participaram?
- as obrigacoes mensais de `REPETICAO MENSAL` aplicaveis aos meses tocados
  estao satisfeitas?
- quem tem `ALOCAR TODOS OS MESES=true` cumpriu sua cota em CADA mes que a
  Ronda efetivamente entrou?

Se uma participacao-base ainda estiver pendente no fecho do mes, a Ronda
continua para o mes seguinte. A partir do momento em que esse novo mes entra
na Ronda, ele passa a gerar tambem as obrigacoes mensais de todos os
colaboradores com `ALOCAR TODOS OS MESES=true`. Por exemplo, se um colaborador
tem `REPETICAO MENSAL=2` e `ALOCAR TODOS OS MESES=true`, e dezembro entrou na
Ronda porque outra pessoa ainda estava pendente, esse colaborador passa a
precisar de 2 alocacoes em dezembro.

Essa extensao nao pode virar um loop infinito: se, ao fechar um mes, restarem
apenas obrigacoes mensais daquele proprio mes e nenhuma participacao-base
pendente que justifique abrir outro mes, o motor deve diagnosticar a situacao
como incompleta/impossivel pelas datas ou filtros disponiveis, em vez de
avancar indefinidamente para meses futuros criando novas obrigacoes.

## Exemplo real (D. MINISTROS / MINISTRO / DOMINGO, N = 7)

Colaboradores ativos: Ana Lima, Andre Luiz, Caio Lima, Clayton Lopes,
Davi Fenner, Patricia Lopes, Suzana Fonseca (7 pessoas).

Comecando em outubro/2026:

| # | Data | Motivo |
|---|------------|--------------------------------------------|
| 1 | 04/10/2026 | rotacao (1o colaborador) |
| 2 | 11/10/2026 | rotacao (2o colaborador) |
| 3 | 18/10/2026 | rotacao (3o colaborador) |
| 4 | 25/10/2026 | rotacao (4o colaborador) |
| 5 | 01/11/2026 | rotacao (5o colaborador) |
| 6 | 08/11/2026 | rotacao (6o colaborador) |
| 7 | 15/11/2026 | rotacao (7o colaborador) -- fecha as 7 datas da rotacao, mas novembro ainda tem domingos sobrando |
| 8 | 22/11/2026 | data extra, so para fechar novembro por completo |
| 9 | 29/11/2026 | data extra, so para fechar novembro por completo |

**Resultado: o Ronda 1 completo tem 9 datas** (04/10/2026 -> 29/11/2026),
porque so assim outubro (4 domingos) E novembro (5 domingos) fecham
inteiros, sem nenhum dos dois mes ficar dividido entre dois ciclos.

O Ronda 2 comeca limpo no primeiro domingo de dezembro/2026 e teria a
mesma logica: 7 datas de rotacao (06/12 a 17/01) + 2 datas extras para
fechar janeiro (24/01 e 31/01) = 9 datas completas.

## Campos REPETIÇÃO MENSAL e ALOCAR TODOS OS MESES

A combinação de `REPETIÇÃO MENSAL` ($R$) e `ALOCAR TODOS OS MESES` (ATM) define
a quantidade exata de alocações necessárias dentro de uma Ronda (ciclo completo)
de DOMINGO:

1. **`REPETIÇÃO MENSAL` ($R$)**:
   - Quantidade **TOTAL** de vezes que o colaborador deve aparecer no mês
     aplicável (ex.: `repeticao_mensal = 2` significa 2 alocações totais no mês,
     e NÃO 2 adicionais).

2. **`ALOCAR TODOS OS MESES = FALSE`**:
   - O colaborador deve aparecer $R$ vezes **APENAS no mês onde cai a sua vez
     natural na Ronda**.
   - **NÃO deve aparecer em outros meses** abrangidos pela mesma Ronda.
   - Demanda gerada: $R \times 1 = R$ alocações no período da Ronda.
   - *Exemplo:* 8 colaboradores em 2 meses (4 domingos cada). Colaborador X tem
     `repeticao = 2, ATM = False`. Vez natural no Mês A.
     Demanda = 8 base + 1 adicional = 9 alocações. X aparece 2x no Mês A e 0x no Mês B.

3. **`ALOCAR TODOS OS MESES = TRUE`**:
   - O colaborador deve aparecer em **TODOS os meses** abrangidos pela Ronda.
   - Em **CADA mês**, deve aparecer $R$ vezes.
   - Demanda gerada: $R \times \text{meses\_tocados}$ alocações no período da Ronda.
   - *Exemplo:* 8 colaboradores em 2 meses (4 domingos cada). Colaborador X tem
     `repeticao = 2, ATM = True`.
     Demanda = 8 base + 3 adicionais = 11 alocações. X aparece 2x no Mês A e 2x no Mês B (4 alocações no total).

4. **Demanda vs Datas da Ronda**:
   - A demanda (ex.: 9 ou 11) ajuda a calcular tetos/cotas para o bloco em
     processamento, mas NAO encerra a Ronda por si so.
   - As datas do calendario da Ronda comecam pela rotacao base de $N$
     colaboradores ativos + extensao para fechamento completo do mes
     (`delimitar_uma_ronda`), sem quebrar meses ao meio.
   - Depois da alocacao, `ronda_esta_completa` reavalia as obrigacoes reais.
     Se houver participacao-base pendente, a Ronda entra no proximo mes inteiro
     e as cotas de `ALOCAR TODOS OS MESES=true` desse novo mes passam a existir.

No grupo D. MINISTROS/MINISTRO/DOMINGO, **Clayton Lopes** e o unico com
`ALOCAR TODOS OS MESES = TRUE` (prioridade 1). No Ronda 1 (9 datas,
outubro+novembro), a rotacao pura por prioridade -- 1-Clayton, 3-Patricia,
4-Caio, 5-Ana, 6-Andre, 7-Suzana, 8-Davi (pula a prioridade 2, que e a
linha duplicada do proprio Clayton) -- com wraparound apos a 7a data ja
coloca Clayton de volta na 8a data, que cai em novembro. Ou seja, **nao e
preciso nenhuma insercao forcada**: a rotacao natural ja cobre outubro
(1a data) e novembro (8a data) sozinha.

### Alocando o Ronda 1 completo (9 datas)

Fila de prioridade (unica, com wraparound): Clayton Lopes (1), Patricia
Lopes (3), Caio Lima (4), Ana Lima (5), Andre Luiz (6), Suzana Fonseca (7),
Davi Fenner (8) -- e volta para Clayton Lopes (1).

| # | Data | Colaborador | Motivo |
|---|------------|-----------------|--------------------------------------------------|
| 1 | 04/10/2026 | Clayton Lopes   | prioridade 1 |
| 2 | 11/10/2026 | Patricia Lopes  | prioridade 3 (pula a 2, duplicata do Clayton) |
| 3 | 18/10/2026 | Caio Lima       | prioridade 4 |
| 4 | 25/10/2026 | Ana Lima        | prioridade 5 |
| 5 | 01/11/2026 | Andre Luiz      | prioridade 6 |
| 6 | 08/11/2026 | Suzana Fonseca  | prioridade 7 |
| 7 | 15/11/2026 | Davi Fenner     | prioridade 8 |
| 8 | 22/11/2026 | Clayton Lopes   | volta ao topo da fila (rotacao natural) -- de quebra ja satisfaz ALOCAR TODOS OS MESES para novembro |
| 9 | 29/11/2026 | Patricia Lopes  | vaga extra do ciclo -- proxima na fila apos Clayton |

Resultado: Clayton Lopes 2x e Patricia Lopes 2x, mas **por consequencia da
rotacao natural com wraparound**, nao por insercao forcada. Os outros 4
(Caio, Ana, Andre, Suzana, Davi) 1x cada.

## Ciclo quebrado

Um ciclo e considerado **quebrado** quando:
- o calendario/capacidade acaba no meio das `N` datas da rotacao (nem todos
  os colaboradores chegam a ter sua vez), ou
- a rotacao termina mas o ultimo mes fica sem fechar (situacao que este
  documento resolve, estendendo o ciclo ate o fim do mes).

## Como aplicar isso no codigo

Ao montar/analisar um ciclo para um grupo:
1. Conte `N` = colaboradores ativos unicos nesse grupo exato (cuidado com
   duplicatas de regra para a mesma pessoa).
2. Gere as primeiras `N` datas da rotacao a partir da data de inicio.
3. Verifique se o mes da `N`-esima data tem mais ocorrencias daquele dia da
   semana depois dela. Se tiver, inclua essas datas extras no mesmo ciclo.
4. So chame o ciclo de "completo" depois desse ajuste.
5. Ao alocar os colaboradores dentro das datas do ciclo completo: rode a
   rotacao pura por ordem de `PRIORIDADE NA ALOCAÇÃO` em todas as datas,
   com wraparound (volta ao topo da fila) quando a fila se esgota antes das
   datas acabarem. So depois disso confira se cada colaborador com
   `ALOCAR TODOS OS MESES=true` caiu em pelo menos 1 data de cada mes que o
   ciclo toca. Se a rotacao natural ja resolveu isso sozinha (comum quando
   esse colaborador tem prioridade 1 e o ciclo tem mais de `N` datas), nao
   force nada. Se faltar, ai sim insira-o na vaga que falta naquele mes,
   empurrando quem a rotacao pura colocaria ali para a proxima vaga livre.
