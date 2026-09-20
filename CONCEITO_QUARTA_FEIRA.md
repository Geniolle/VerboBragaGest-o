# QUARTA-FEIRA: rodizio normal e FIXO_RECORRENTE

Este documento descreve regras especificas de
`D. MINISTROS / MINISTRO / QUARTA-FEIRA`.

DOMINGO e QUARTA-FEIRA sao processos separados. A quarta nao usa CEIA,
cursor normal de domingo nem reconstrução de CEIA. Ela usa tema/nível,
rodizio proprio e a data de corte historica do novo motor para o seu estado
rotacional.

## NORMAL

Uma regra sem `TIPO ALOCAÇÃO` participa do fluxo normal:

- disputa vagas em aberto;
- passa pelos filtros obrigatorios do motor;
- usa `TEMA` da agenda e classificação P1/P2/P3 dos livros para chegar ao
  nivel exigido;
- participa do rodizio por nivel/tema;
- pode cumprir `REPETIÇÃO MENSAL`, `ALOCAR TODOS OS MESES`, resgate ou
  lacuna conforme as regras gerais.

Neste modo, `SEMANA PREFERENCIAL` continua sendo uma restrição/preferência
do candidato normal: fora da semana configurada, ele nao concorre na passada
normal.

## FIXO_RECORRENTE

`TIPO ALOCAÇÃO = FIXO_RECORRENTE` define uma reserva de data. Nao e uma
prioridade alta.

Quando uma regra fixa aplica a uma data:

- a vaga e reservada antes do rodizio normal;
- o vencedor esperado e o nome da propria regra;
- o ranking P1/P2/P3 nao decide a vaga;
- filtros humanos pessoais, como aniversario, descanso pessoal e Excluse de
  pessoa, nao sao aplicados cegamente a reserva;
- a decisão nao consome rodizio normal nem rodizio por nivel;
- a reserva nao conta como participação-base de colaborador normal na Ronda.

Em datas em que a recorrência nao aplica, a regra `FIXO_RECORRENTE` fica fora
do pool normal. Isso impede que uma entidade de evento, mesmo com prioridade
1, vença uma quarta comum.

## Recorrência

A recorrência e mensal, baseada em âncora e intervalo:

```text
delta_meses = (ano_slot - ano_inicio) * 12 + (mes_slot - mes_inicio)
```

O mês e valido quando:

```text
delta_meses >= 0
delta_meses % INTERVALO MESES == 0
```

Depois disso, a data tambem precisa estar na semana fixa:

```text
week_of_month(data_slot) == SEMANA PREFERENCIAL
```

Para `FIXO_RECORRENTE`, `SEMANA PREFERENCIAL` deixa de ser preferência e vira
requisito obrigatorio da reserva. Nao se exige que o dia do mês seja igual ao
da âncora: `16/09/2026` e `18/11/2026` sao ambas terceiras quartas-feiras.

## Data De Corte

`PASTOREIO_DATA_CORTE_HISTORICO=2026-10-01` filtra o estado rotacional da
quarta, mas nao altera a âncora da recorrência.

Exemplo: uma regra com âncora em `16/09/2026` e intervalo de 2 meses continua
com meses validos setembro, novembro, janeiro, março. Como setembro esta
antes do corte, a primeira ocorrência relevante do novo motor e novembro.

## Conflitos

Se mais de uma regra `FIXO_RECORRENTE` aplicar a mesma data, isso e erro de
configuração. O motor deve diagnosticar explicitamente o conflito e nao usar
`PRIORIDADE` para desempatar.

Se a data reservada ja estiver preenchida por outro valor na agenda, o script
nao sobrescreve. O diagnostico deve mostrar:

- reserva fixa esperada;
- valor persistido;
- nenhuma escrita automatica.

## Produtivo

O script `scripts/preencher_claude_appanualglobal_quarta.py` roda em
`CLAUDE_AppAnualGlobal` por padrao. Quando executado com `--produtivo`, pode
escrever em `AppAnualGlobal` via allowlist explicita do `SpreadsheetGuard`.
Essa promoção e exclusiva da quarta-feira e nao altera DOMINGO, CEIA,
auxiliares ou sincronizações.
