---
name: pastoreio-utilizador
description: Implementa e opera processos de Utilizador que sincronizam ou criam cadastro de pessoas entre sheets de origem operacional, como Membresia, e BP SERVICE. Use para subprocessos de cadastro de utilizador, criação/identificação de pessoas, normalização de dados pessoais e flags de processamento. Não use para BP SERVICE -> BP ALGORITIMO, execução de Ronda, investigação de alocação ou mudança de regra do motor de escala.
---

# Processo Utilizador

Processos de Utilizador/Colaborador tratam cadastro de pessoas e projeções
operacionais derivadas de `BP SERVICE` antes de qualquer regra de alocação.
Eles não devem mexer em prioridades, calendários ou regras do motor.

## Cockpit operacional

Ponto de entrada:
`../../../scripts/Colaborador/cockpit_colaborador.py`.

Ordem oficial de execução dos subprocessos:

1. analisar pendentes `Membresia -> BP SERVICE`;
2. marcar `Membresia.BP SERVICE=TRUE` para pessoas já existentes;
3. validar `BP SERVICE.DEPARTAMENTOS` contra colunas `D.*`;
4. atualizar `BP COLABORADOR` a partir de `BP SERVICE`;
5. atualizar `BP AUTORITY` a partir de `BP SERVICE`;
6. reconciliar/remover lixo de `BP AUTORITY` contra `BP SERVICE`;
7. sincronizar `BP AUTORITY -> BP ALGORITIMO`.

O cockpit roda em dry-run por padrão:

```text
uv run python scripts/Colaborador/cockpit_colaborador.py
```

Para aplicar escritas controladas nos subprocessos que suportam `--aplicar`:

```text
uv run python scripts/Colaborador/cockpit_colaborador.py --aplicar
```

## Execução produtiva no servidor

O Colaborador produtivo deve correr no servidor, seguindo o padrão dos
processos Python operacionais: `systemd`, usuário `opc`, diretório de trabalho
do projeto e `uv` global reutilizado. Não instale Windows Task Scheduler na
máquina local para este processo.

Unidades versionadas:

- `../../../scripts/Servidor/systemd/pastoreio-colaborador.service`
- `../../../scripts/Servidor/systemd/pastoreio-colaborador.timer`

O timer chama o runner:

```text
uv --cache-dir /home/opc/pastoreio-orquestrador/.uv-cache run python scripts/Servidor/executar_colaborador_agendado.py --aplicar
```

O runner mantém lock em `runtime/colaborador.lock`, grava somente o último log
consolidado em `runtime/colaborador_ultimo.log` e ignora execuções
concorrentes. Para instalar no servidor:

```text
sudo scripts/Servidor/instalar_timer_colaborador_systemd.sh
```

Verificações úteis no servidor:

```text
systemctl list-timers pastoreio-colaborador.timer
systemctl status pastoreio-colaborador.timer
systemctl status pastoreio-colaborador.service
journalctl -u pastoreio-colaborador.service -n 100 --no-pager
```

## Subprocesso: Criar no utilizador Membresia

Implementação versionada em
`../../../google_apps_script/Utilizador_Membresia_BPService.gs`.

Objetivo: garantir que toda linha pendente da sheet `Membresia` exista em
`BP SERVICE`, usando `Membresia.BP SERVICE` como flag de controlo.

Scripts auxiliares read/write controlados:

- `../../../scripts/Colaborador/analisar_membresia_bp_service.py` —
  read-only, lista linhas pendentes com `BP SERVICE` vazio.
- `../../../scripts/Colaborador/marcar_membresia_bp_service_existentes.py` —
  por padrão dry-run; com `--aplicar`, marca
  `Membresia.BP SERVICE=TRUE` somente quando a pessoa já existe em
  `BP SERVICE` por match inequívoco. Não cria pessoas e não altera
  `BP SERVICE`.

Regras centrais:

- `Membresia.BP SERVICE` vazio: analisar.
- `Membresia.BP SERVICE = TRUE`: ignorar.
- Só marcar `TRUE` depois de encontrar pessoa inequívoca em `BP SERVICE` ou
  criar e validar novo registo.
- Em erro ou ambiguidade, deixar a flag vazia.
- A execução deve ser idempotente; não pode criar duplicados em execuções
  repetidas.
- O arquivo Apps Script deve ficar com `DRY_RUN: true` até o relatório do
  Logger ser validado por humano.

## Matching

A identificação não usa apenas nome nem apenas email. O subprocesso compara
em camadas:

1. email normalizado;
2. telefone e `NUMBER_WHATSAPP`;
3. nome + data de nascimento.

Se email existir em múltiplos registos, desempata por telefone,
`NUMBER_WHATSAPP` e nome + data de nascimento. Se continuar ambíguo, não cria
novo registo e não marca a flag.

## Escrita

Este processo escreve somente:

- novas linhas em `BP SERVICE`;
- flag `Membresia.BP SERVICE = TRUE` para linhas confirmadas.

Não preencher nem alterar departamentos (`DEPARTAMENTOS`, `D. *`) e não
interpretar `Formação Bíblica`. Essas regras pertencem a subprocessos futuros.

## Validação

Antes de qualquer execução real:

1. executar em dry-run;
2. conferir Logger: encontrados, criados, ambiguidades, erros e alterações
   previstas;
3. confirmar manualmente ambiguidades;
4. só então alterar `DRY_RUN` para `false`.

Depois de qualquer alteração no subprocesso, volte a avaliar se esta skill
continua atualizada e rode a suite do projeto quando houver código Python
alterado.

## Subprocesso: Atualizar BP AUTORITY

Implementação:
`../../../scripts/Colaborador/atualizar_bp_autority.py`.

Objetivo: sincronizar permissões de colaborador na sheet `BP AUTORITY` a
partir dos departamentos marcados em `BP SERVICE`.

Escopo de entrada:

- `BP SERVICE.INATIVO != true`;
- `BP SERVICE.DEPARTAMENTOS = true`;
- `BP SERVICE.BP AUTORITY` vazio.

Regras:

- localizar a pessoa em `BP AUTORITY` por `ID_USER`;
- se existir, marcar como `TRUE` as colunas `COLABORADOR_*` correspondentes
  aos departamentos `D.*=true` em `BP SERVICE`;
- se não existir, criar uma nova linha em `BP AUTORITY` com `ID_USER`,
  `NOME`, `TELEFONE`, `EMAIL`, `FOTO DO PERFIL` e as colunas
  `COLABORADOR_*` existentes correspondentes;
- se uma coluna `COLABORADOR_*` não existir no cabeçalho da `BP AUTORITY`,
  ignorar esse departamento, sem tratar como divergência;
- só marcar `BP SERVICE.BP AUTORITY=TRUE` depois que o registo em
  `BP AUTORITY` existir ou tiver sido criado e validado.

O script roda em dry-run por padrão. Use `--aplicar` somente depois de
validar o plano:

```text
uv run python scripts/Colaborador/atualizar_bp_autority.py
uv run python scripts/Colaborador/atualizar_bp_autority.py --aplicar
```

## Subprocesso: Atualizar BP COLABORADOR

Implementação:
`../../../scripts/Colaborador/atualizar_bp_colaborador.py`.

Auditoria read-only:
`../../../scripts/Colaborador/analisar_bp_colaborador.py`.

Objetivo: sincronizar a matriz `BP COLABORADOR` a partir das colunas
`D.*` da `BP SERVICE`.

Regras:

- `BP SERVICE` é a fonte da verdade;
- processa apenas colaboradores com `INATIVO != true`, `TYPE` vazio e
  `NOME` preenchido;
- cada coluna `FUNC_*` de `BP COLABORADOR` é preenchida com os nomes de
  `BP SERVICE` cujo departamento `D.*` correspondente esteja `TRUE`;
- colunas `FUNC_*` sem origem `D.*` correspondente são preservadas. Exemplo
  atual: `FUNC_CEIA`;
- o subprocesso limpa nomes a mais e inclui nomes em falta, reescrevendo as
  colunas geridas de forma idempotente.

O script roda em dry-run por padrão:

```text
uv run python scripts/Colaborador/atualizar_bp_colaborador.py
uv run python scripts/Colaborador/atualizar_bp_colaborador.py --aplicar
```

## Subprocesso: Reconciliar BP AUTORITY

Implementação:
`../../../scripts/Colaborador/reconciliar_bp_autority.py`.

Objetivo: remover lixo da `BP AUTORITY` quando um líder remove um
colaborador de um departamento em `BP SERVICE`.

Regra: `BP SERVICE` é a fonte da verdade. Qualquer permissão
`COLABORADOR_*` existente em `BP AUTORITY` precisa continuar existindo como
departamento `D.*=true` em `BP SERVICE`.

O subprocesso:

- limpa `COLABORADOR_*` em `BP AUTORITY` quando o departamento
  correspondente não está mais marcado em `BP SERVICE`;
- limpa todos os `COLABORADOR_*` quando o `ID_USER` não existe em
  `BP SERVICE`, está `INATIVO=true`, ou não tem `DEPARTAMENTOS=true`;
- elimina a linha da `BP AUTORITY` quando, depois da limpeza, não resta
  nenhum campo de permissão preenchido;
- limpa `BP SERVICE.BP AUTORITY` quando a linha correspondente da
  `BP AUTORITY` for eliminada.

Campos de identidade (`ID_USER`, `NOME`, `TELEFONE`, `EMAIL`,
`FOTO DO PERFIL`, `USEREMAIL`, `TIMESTAMP`) não contam como permissão para
decidir se a linha deve continuar existindo. Campos de permissão são
`USER_ALL`, `DEPARTAMENTOS_*`, `GERAL_DEPARTAMENTOS`, `MANAGER_*`,
`COORDENADOR_*` e `COLABORADOR_*`.

O script roda em dry-run por padrão. Use `--aplicar` somente depois de
validar o plano:

```text
uv run python scripts/Colaborador/reconciliar_bp_autority.py
uv run python scripts/Colaborador/reconciliar_bp_autority.py --aplicar
```

## Subprocesso: Sincronizar BP AUTORITY -> BP ALGORITIMO

Implementação:
`../../../scripts/Colaborador/sincronizar_bp_autority_bp_algoritimo.py`.

Objetivo: garantir que vínculos de colaborador/departamento existentes em
`BP AUTORITY` também existam como vínculos ativos em `BP ALGORITIMO`, e que
vínculos ativos em `BP ALGORITIMO` não continuem ativos quando não existem
mais em `BP AUTORITY`.

Regras:

- cada `COLABORADOR_* = TRUE` em `BP AUTORITY` vira um vínculo
  `ID_USER + NOME + DEPARTAMENTO` em `BP ALGORITIMO`;
- o vínculo só é considerado quando o mesmo `ID_USER` em `BP SERVICE` tem
  `TYPE` vazio; contas de sistema/placeholders com `TYPE` preenchido não
  entram no `BP ALGORITIMO`;
- a coluna de autoridade só é considerada quando existe um departamento
  `D.*` correspondente no cabeçalho de `BP SERVICE`;
- se o vínculo já existe em `BP ALGORITIMO` e está inativo, ele é reativado;
- se o vínculo não existe, uma linha nova é inserida com `ID_USER`, `NOME`,
  `DEPARTAMENTO` e `ATIVO=TRUE`;
- se um vínculo ativo de `BP ALGORITIMO`, para departamento gerido pela
  `BP AUTORITY`, não existe mais em `BP AUTORITY`, ele é marcado
  `ATIVO=FALSE`.
- se houver duplicados ativos do mesmo `NOME + DEPARTAMENTO`, o subprocesso
  mantém uma linha principal e elimina fisicamente as linhas duplicadas;
- `BP ALGORITIMO.ID_USER` deve sempre ser igual ao `BP SERVICE.ID_USER`;
  o script corrige divergências mesmo em linhas inativas/legadas quando o
  nome existe de forma inequívoca em `BP SERVICE`.

Auditoria read-only para ID_USER:
`../../../scripts/Colaborador/auditar_id_user_bp_algoritimo.py`.

O script roda em dry-run por padrão:

```text
uv run python scripts/Colaborador/sincronizar_bp_autority_bp_algoritimo.py
uv run python scripts/Colaborador/sincronizar_bp_autority_bp_algoritimo.py --aplicar
```
