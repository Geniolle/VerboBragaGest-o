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
   BP LOG, LOG ALGORITIMO, BP SERVICE)
   ↓
motor.py (alocar_grupo / _alocar_grupo_domingo_ceia_alternada)
   ↓
decisões (DecisaoAlocacao por slot)
   ↓ script preencher_claude_appanualglobal_<grupo>.py
CLAUDE_AppAnualGlobal (escrita via SpreadsheetGuard)
   ↓ auditoria.py -> CLAUDE_LOG_AUDITORIA
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
   um único `EstadoExecucaoGrupo` contínuo, para reconstituir o histórico
   de rodízio/quota/descanso.
2. Calcula **apenas a próxima Ronda ainda vazia**, começando pelo recorte
   base (`N` colaboradores ativos + fecho do mês), mas só a encerra depois de
   `ronda_esta_completa` confirmar que todas as participações-base e
   obrigações mensais reais foram satisfeitas.
3. Se a Ronda aberta precisa entrar num novo mês por haver participação-base
   pendente, esse mês passa a fazer parte da Ronda e cria as obrigações de
   `ALOCAR TODOS OS MESES=true` desse mês; se as obrigações forem
   matematicamente impossíveis pelas datas/filtros, o motor deve gerar
   diagnóstico controlado em vez de avançar indefinidamente.
4. Nunca sobrescreve uma célula já preenchida.
5. Escreve `"SEM ALOCAÇÃO"` (texto literal) quando genuinamente não há
   candidato possível — nunca deixa a célula em branco por omissão.

## 4. Escrita — sempre via SpreadsheetGuard, sempre em CLAUDE_*

Nenhum script novo deve chamar métodos de escrita diretamente num objeto
`gspread.Worksheet` — use sempre `guard.update_cell` / `guard.append_row` /
`guard.batch_update_cells`. Ver a secção "Regra de segurança máxima" em
`../../../AGENTS.md` (inclui a dívida técnica conhecida em
`testar_ministros_quarta.py`, a não repetir).

## 5. Auditoria

`auditoria.construir_linhas_auditoria` converte cada `DecisaoAlocacao` em
linha de log (motivo, runner-up, ordem completa de desempate), gravada de
forma cumulativa (nunca apaga execuções anteriores) em
`CLAUDE_LOG_AUDITORIA` via `guard.ensure_worksheet_with_header` +
`guard.append_row`. Os scripts de preenchimento já fazem isto — não
suprima essa etapa ao criar/adaptar um script novo.

## 6. Validação humana

Depois de escrever, reporte o resultado (datas, vencedores, motivos,
qualquer `SEM ALOCAÇÃO`) para revisão humana antes de considerar a Ronda
definitiva — nenhuma escrita em `CLAUDE_*` é automaticamente "validada" só
por ter sido executada sem erro (ver `pastoreio-validar-grupo` para o que
"validado" realmente exige).
