---
name: pastoreio-utilizador
description: Implementa e opera processos de Utilizador que sincronizam ou criam cadastro de pessoas entre sheets de origem operacional, como Membresia, e BP SERVICE. Use para subprocessos de cadastro de utilizador, criação/identificação de pessoas, normalização de dados pessoais e flags de processamento. Não use para BP SERVICE -> BP ALGORITIMO, execução de Ronda, investigação de alocação ou mudança de regra do motor de escala.
---

# Processo Utilizador

Processos de Utilizador tratam cadastro de pessoas antes de qualquer regra de
alocação. Eles são separados do fluxo `BP SERVICE -> BP ALGORITIMO` e não
devem mexer em departamentos, funções, prioridades ou regras do motor.

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
