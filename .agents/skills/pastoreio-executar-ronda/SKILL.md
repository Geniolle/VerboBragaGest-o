---
name: pastoreio-executar-ronda
description: Executa ou prepara uma Ronda de alocação (gerar próxima Ronda, preencher MINISTRO/AUXILIAR/CEIA, rodar o motor para um grupo DEPARTAMENTO###FUNÇÃO###DIA). Use para pedidos de "gerar próxima Ronda", "executar escala", "preencher ministros/auxiliares/CEIA", "rodar alocação". Não use para explicar uma decisão já tomada (isso é pastoreio-investigar-alocacao) nem para mudar regra de negócio do motor (isso é pastoreio-alterar-regra).
---

# Executar uma Ronda

Ver [`../../../CONCEITO_CICLO.md`](../../../CONCEITO_CICLO.md) (o que é
Rotação/Ronda/Ciclo completo) e
[`../../../CONCEITO_PRIORIDADES.md`](../../../CONCEITO_PRIORIDADES.md) (ordem
exata de filtros e desempate) antes de mexer em qualquer lógica de Ronda —
não redescreva essas regras aqui, só o workflow operacional.

## Workflow

```text
BP SERVICE
   ↓ scripts/passo1_sincronizar_bp_service.py
sincronização (BP SERVICE -> CLAUDE_BP ALGORITIMO)
   ↓ scripts/checklist_pre_alocacao.py
checklist / sanity (propostas E + F, só leitura)
   ↓
identificar grupo (DEPARTAMENTO + FUNÇÃO + DIA DA SEMANA)
   ↓
identificar Ronda/rotação/ciclo (ver CONCEITO_CICLO.md)
   ↓
carregar dados e históricos (BP ALGORITIMO, AppAnualGlobal, Excluse,
   BP LOG, LOG ALGORITIMO, BP SERVICE, LOG_AUDITORIA)
   ↓
reconstruir cursor de hierarquia de DOMINGO a partir de agenda + auditoria
   ↓
motor.py (alocar_grupo / _alocar_grupo_domingo_ceia_alternada)
   ↓
decisões (DecisaoAlocacao por slot)
   ↓ script preencher_claude_appanualglobal_<grupo>.py
AppAnualGlobal ou CLAUDE_AppAnualGlobal (sempre via SpreadsheetGuard;
produtivo só para processo explicitamente promovido)
   ↓ auditoria.py -> CLAUDE_LOG_AUDITORIA ou LOG_AUDITORIA
auditoria
   ↓
validação (revisão humana do resultado escrito)
```

Não duplique aqui as regras internas de `motor.py` (filtros, desempate,
fases de CEIA, resgate) — isso é o trabalho do motor e está documentado em
`CONCEITO_PRIORIDADES.md` / `CONCEITO_CEIA_ALTERNADA.md`. Esta skill só
cobre a orquestração ao redor dele.

## 1. Sincronizar BP SERVICE -> BP ALGORITIMO

```
uv run python scripts/passo1_sincronizar_bp_service.py
```

Roda em modo dry-run por padrão (não escreve nada); passe `--aplicar` para
gravar de facto, e sempre contra uma cópia `CLAUDE_*` (nunca contra
`BP ALGORITIMO` original). Rode isto antes de qualquer preenchimento de
Ronda, para o cadastro de colaboradores estar em dia.

## 2. Checklist de pré-alocação (só leitura)

```
uv run python scripts/checklist_pre_alocacao.py
```

Roda o sanity check de configuração (SINC inválido, quotas contraditórias)
e o protocolo de validação por grupo (compara `BP ALGORITIMO` com
`GRUPOS_VALIDADOS.md`, ver `pastoreio-validar-grupo`). Investigue qualquer
aviso antes de prosseguir — não ignore.

## 3. Identificar o grupo e reutilizar (ou criar) o script de preenchimento

Cada grupo já validado (ver `../../../GRUPOS_VALIDADOS.md`) tem um script
dedicado em `scripts/`:

- `preencher_claude_appanualglobal_domingo.py` — D. MINISTROS/MINISTRO/DOMINGO
- `preencher_claude_appanualglobal_quarta.py` — D. MINISTROS/MINISTRO/QUARTA-FEIRA
- `preencher_claude_appanualglobal_auxiliar_domingo.py`
- `preencher_claude_appanualglobal_auxiliar_quarta.py`
- `preencher_claude_appanualglobal_ceia.py`

DOMINGO e QUARTA-FEIRA devem continuar como processos separados. Não
transporte estado de CEIA, cursor normal de DOMINGO, intenção `CEIA`, nem
replay/histórico de DOMINGO para o fluxo de QUARTA-FEIRA. QUARTA-FEIRA tem
tema/nível/rodízio próprios e qualquer reconstrução histórica desse fluxo
precisa ser desenhada e testada separadamente.

`scripts/cockpit_preencher_claude.py` executa todos em sequência (aceita
`--simular` para só mostrar a ordem, e `--continuar-em-erro`).

Se o grupo pedido é uma combinação nova de `DEPARTAMENTO###FUNÇÃO###DIA`
mas o **processo** é o mesmo (mesmo tipo de workflow, só parâmetros
diferentes), reutilize o padrão de um script `preencher_claude_*`
existente mais parecido em vez de inventar um processo novo — ver a skill
`pastoreio-manter-agents-skills` para o critério de quando algo realmente
justifica algo novo. Depois de o grupo funcionar ponta a ponta, registe-o
em `GRUPOS_VALIDADOS.md` via `pastoreio-validar-grupo`.

Cada script de preenchimento, na prática:

1. Reconstrói os blocos de Ronda já existentes na sheet a partir das datas
   preenchidas, e reexecuta (sem escrever) os blocos já fechados através de
   um único `EstadoExecucaoGrupo` contínuo, para reconstituir estados
   transitórios que ainda dependem do replay (ex.: lacuna/quota/descanso).
   Não use replay para descobrir vencedor histórico de CEIA quando o dado
   real já está persistido.
2. Para DOMINGO, reconstrói a âncora da hierarquia normal lendo
   `AppAnualGlobal`/`CLAUDE_AppAnualGlobal` + `LOG_AUDITORIA`/
   `CLAUDE_LOG_AUDITORIA`. Use somente decisões com
   `CONSOME_HIERARQUIA=TRUE` confirmadas pela agenda real; CEIA, repetição
   mensal, ATM, resgate e lacuna não movem o cursor. Depois do replay,
   restaure essa âncora persistida antes de calcular a Ronda aberta.
   Para o ciclo próprio da CEIA, carregue
   `estado.historico_vencedores_ceia` pelos vencedores reais persistidos
   (agenda confirmada por auditoria/intenção `CEIA`) antes da primeira data
   vazia; não recalcule CEIAs passadas com a versão atual do motor e não
   duplique o histórico com o replay.
   Ainda em DOMINGO, carregue as ocorrências de CEIA já persistidas na agenda
   para a contagem mensal de `REPETIÇÃO MENSAL`: CEIA não consome hierarquia,
   mas conta como participação mensal do colaborador.
   Só alocações NORMAIS avançam esse cursor. Repetição mensal, obrigação de
   `ALOCAR TODOS OS MESES`, CEIA, resgate e lacuna aparecem na escala quando
   elegíveis, mas não reposicionam a hierarquia normal.
   O diagnóstico/auditoria deve preservar a intenção da vaga
   (`NORMAL_ROTATION`, `MONTHLY_REPEAT`, `EVERY_MONTH_OBLIGATION`, `CEIA`,
   etc.) para que não seja necessário inferir posteriormente por que a pessoa
   entrou.
   Preserve também a separação entre `TIPO_DIA`, intenção e política de
   seleção: um `DOMINGO_NORMAL` pode ser rotação normal ou obrigação mensal.
   `GAP_FILL` explica a lacuna, mas não escolhe por uma fila implícita; use a
   política de seleção registrada/implementada para aquele tipo de decisão.
   Ao reportar ou auditar o resultado, não rotule como `ALOCAÇÃO NORMAL` uma
   ocorrência que entrou para cumprir `REPETIÇÃO MENSAL` ou
   `ALOCAR TODOS OS MESES`; a pessoa/data podem ser as mesmas, mas o motivo
   semântico precisa ficar correto para auditoria e investigações futuras.
3. Calcula **apenas a próxima Ronda ainda vazia**, começando pelo recorte
   base (`N` colaboradores ativos + fecho do mês), mas só a encerra depois de
   `ronda_esta_completa` confirmar que todas as participações-base e
   obrigações mensais reais foram satisfeitas.
4. Se a Ronda aberta precisa entrar num novo mês por haver participação-base
   pendente, esse mês passa a fazer parte da Ronda e cria as obrigações de
   `ALOCAR TODOS OS MESES=true` desse mês; se as obrigações forem
   matematicamente impossíveis pelas datas/filtros, o motor deve gerar
   diagnóstico controlado em vez de avançar indefinidamente.
5. Nunca sobrescreve uma célula já preenchida.
6. Escreve `"SEM ALOCAÇÃO"` (texto literal) quando genuinamente não há
   candidato possível — nunca deixa a célula em branco por omissão.

## 4. Escrita — sempre via SpreadsheetGuard

Nenhum script novo deve chamar métodos de escrita diretamente num objeto
`gspread.Worksheet` — use sempre `guard.update_cell` / `guard.append_row` /
`guard.batch_update_cells`. Por padrão, escreva em `CLAUDE_*`. Quando o
utilizador promover um processo para produtivo, declare a allowlist de abas
produtivas no `SpreadsheetGuard` daquele script e documente essa promoção no
próprio processo; não promova outros dias/grupos por arrasto. Ver a secção
"Regra de segurança máxima" em `../../../AGENTS.md`.

Estado atual: o processo `D. MINISTROS / MINISTRO / DOMINGO` está habilitado
para produtivo quando executado com `--produtivo` (`AppAnualGlobal` +
`LOG_AUDITORIA`). Sem essa flag, continua em `CLAUDE_*`. QUARTA-FEIRA, CEIA,
auxiliares, sincronização e limpezas continuam processos separados e não
herdam essa autorização.

## 5. Auditoria

`auditoria.construir_linhas_auditoria` converte cada `DecisaoAlocacao` em
linha de log (RUN_ID, motivo, intenção, obrigação satisfeita, prioridade,
`CONSOME_HIERARQUIA`, runner-up, ordem completa de desempate), gravada de
forma cumulativa (nunca apaga execuções anteriores) em
`CLAUDE_LOG_AUDITORIA` ou `LOG_AUDITORIA` via
`guard.ensure_worksheet_with_header` + `guard.append_rows`, conforme o modo
do processo. Os scripts de preenchimento já fazem isto — não suprima essa
etapa ao criar/adaptar um script novo.

## 6. Validação humana

Depois de escrever, reporte o resultado (datas, vencedores, motivos,
qualquer `SEM ALOCAÇÃO`) para revisão humana antes de considerar a Ronda
definitiva — nenhuma escrita em `CLAUDE_*` é automaticamente "validada" só
por ter sido executada sem erro (ver `pastoreio-validar-grupo` para o que
"validado" realmente exige).
