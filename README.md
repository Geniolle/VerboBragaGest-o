# Orquestrador de Escala Automatica (Pastoreio)

Porte em Python do algoritmo `Algoritimo_Input_Escala_Automatico_v63` (Google Apps
Script) usado na spreadsheet "AppPastoreioGestao", para funcionar como um
orquestrador que procura solucoes de alocacao de colaboradores seguindo as
mesmas regras do script original.

## Regra de seguranca (inegociavel)

- **As abas originais nunca sao apagadas nem alteradas.** So sao lidas.
- Qualquer teste/simulacao que precise de escrever dados cria/usa uma
  **copia da aba com o prefixo `CLAUDE_`** (ex.: `CLAUDE_AppAnualGlobal`).
- O modulo `sheets_client.SpreadsheetGuard` bloqueia em codigo qualquer
  tentativa de escrita/delete numa aba sem o prefixo `CLAUDE_`
  (`TentativaDeAlteracaoOriginalError`).

## Configuracao do acesso ao Google Sheets (uma vez)

1. Aceda a https://console.cloud.google.com/ e crie/escolha um projeto.
2. Ative as APIs **Google Sheets API** e **Google Drive API**.
3. Crie uma **Service Account** (IAM & Admin -> Service Accounts) e gere
   uma chave em JSON. Guarde o ficheiro em `credentials/service_account.json`
   (esta pasta ja esta no `.gitignore`, a chave nunca e versionada).
4. Descubra o e-mail da service account:

   ```
   uv run python scripts/mostrar_email_service_account.py credentials/service_account.json
   ```

5. Abra a spreadsheet "AppPastoreioGestao" no Drive -> Partilhar -> cole
   esse e-mail com permissao de **Editor** (necessario para poder duplicar
   abas de teste; as abas originais continuam protegidas pelo codigo).
6. Copie `.env.example` para `.env` e preencha:
   - `GOOGLE_SERVICE_ACCOUNT_FILE=<caminho da chave JSON>`
   - `SPREADSHEET_ID=<id da spreadsheet, entre /d/ e /edit na URL>`

   Este projeto reaproveita a service account ja existente do projeto
   Tesouraria-SOMA (`C:/workspace/Tesouraria-SOMA/credentials/sheets-service-account.json`),
   nao é necessario criar uma nova.
7. Instale as dependencias e valide o acesso:

   ```
   uv sync
   uv run python scripts/verificar_acesso.py
   ```

## Estrutura do projeto

```
src/pastoreio_orquestrador/
  config.py           # carrega .env
  sheets_client.py     # acesso ao Sheets com a trava CLAUDE_
  columns.py           # nomes reais das colunas de cada aba
  models.py             # RegraColaborador, SlotAgenda, TemaClassificado, etc.
  parsing_utils.py       # parseBool, weekOfMonth, monthKey, isValidPreferredWeek...
  carregamento.py         # conversao das linhas cruas das sheets para os modelos
  motor.py                 # motor de regras: demanda, filtros, sorter, loop + resgate
  auditoria.py              # (proposta A) monta as linhas do log de auditoria (CLAUDE_LOG_AUDITORIA)
  diagnostico.py             # compara abas/colunas reais com o que columns.py espera
  sanity_regras.py            # (proposta E) sanity check de config: SINC invalido, quotas contraditorias
  zumbi_writeback.py           # (proposta B) calcula/aplica a recuperacao de zumbis em BP LOG
  alerta_sem_alocacao.py        # (proposta D) monta o alerta de SEM ALOCAÇÃO (nao envia e-mail)
  protocolo_validacao.py         # (proposta F) cruza BP ALGORITIMO com GRUPOS_VALIDADOS.md
scripts/
  mostrar_email_service_account.py
  verificar_acesso.py          # valida acesso + roda o diagnostico de estrutura
  checklist_pre_alocacao.py    # roda as propostas E + F contra a spreadsheet real (so leitura)
  testar_ministros_quarta.py   # teste de integracao end-to-end (so escreve em CLAUDE_*)
tests/
  test_parsing_utils.py
  test_motor.py
  test_fase0_temas.py
  test_auditoria.py
  test_diagnostico.py
  test_sanity_regras.py
  test_zumbi_writeback.py
  test_alerta_sem_alocacao.py
  test_protocolo_validacao.py
```

## Propostas de melhoria (A–F) e seu status

| # | Proposta | Risco | Status |
|---|----------|-------|--------|
| A | Log de auditoria de decisão | Baixo | Feito — `auditoria.py`, gravado em `CLAUDE_LOG_AUDITORIA` |
| B | Fechar ciclo dos "zumbis" em `BP LOG` | Médio | Lógica pura pronta e testada (`zumbi_writeback.py`); escrita real só foi exercitada contra copia `CLAUDE_BP LOG`, nunca contra `BP LOG` original |
| C | Redesenhar `Excluse` para tabela explícita | Alto | **Não implementado** — mexe na fonte de verdade; precisa aprovação explícita antes de qualquer trabalho, com plano de migração com leitura dupla (antigo + novo) |
| D | Alerta automático de "SEM ALOCAÇÃO" por e-mail | Baixo (mas envio é ação externa) | Só a lógica de deteccao/composição do alerta está pronta (`alerta_sem_alocacao.py`); **envio real de e-mail não foi implementado** — não há serviço de e-mail configurado, e isso exige aprovação explícita antes de ligar |
| E | Sanity check de configuração (SINC inválido, quotas contraditórias) | Baixo | Feito — `sanity_regras.py`. Validado contra dados reais: revelou um SINC genuinamente quebrado (`Jonathan Dias` → `Letícia Benedicto`, que não existe em nenhuma regra ativa de domingo) |
| F | Protocolo de validação por grupo | Nenhum | Feito — `GRUPOS_VALIDADOS.md` + `protocolo_validacao.py`, rodado via `scripts/checklist_pre_alocacao.py` |

Rode `uv run python scripts/checklist_pre_alocacao.py` para ver as propostas E+F contra os dados reais (só leitura).

## Estado atual

- Acesso a spreadsheet real validado (todas as 7 abas usadas pelo algoritmo
  original foram encontradas).
- Motor de regras implementado e testado: agregacao por grupo, demanda por
  "onda expansiva", filtros obrigatorios (quota mensal, tema, exclusao por
  colaborador/data via `Excluse`, vizinhanca, descanso minimo com override
  de sincronizacao), sorter de desempate por ordem de precedencia, e logica
  de resgate.
- Fase 0 (forca-tarefa de tema P1/P2/P3 para D. MINISTROS/QUARTA-FEIRA)
  implementada (`montar_requisito_tema_por_slot`).
- `esta_bloqueado_por_excluse` **validado contra a estrutura real** da aba
  `Excluse` (ver nota no topo de `motor.py`): o bloqueio e por colaborador
  especifico numa data especifica (nome numa das 30 colunas genericas
  ASSIDUIDADE1..30 de `AppAnualGlobal`), nao por departamento inteiro como
  a suposicao inicial presumia.
- Historico real ligado ao motor: `historico_total` vem de
  `LOG ALGORITIMO` (contagem de alocacoes passadas por colaborador, so
  execucoes com Status="Ativo") e `zumbis_prioritarios` vem de `BP LOG`
  (colaboradores com DISPONIBILIDADE=TRUE, ou seja, ainda pendentes de
  recuperacao prioritaria).
- Log de auditoria: cada decisao do motor (`DecisaoAlocacao`) pode ser
  transformada em linha de auditoria (`auditoria.construir_linhas_auditoria`)
  com motivo, runner-up e ordem completa de desempate, e gravada de forma
  cumulativa (nunca apagando execucoes anteriores) na aba `CLAUDE_LOG_AUDITORIA`
  via `SpreadsheetGuard.ensure_worksheet_with_header` + `append_row`.
  `scripts/testar_ministros_quarta.py` ja grava essa auditoria a cada execucao.
- Diagnostico de estrutura: `diagnostico.diagnosticar` le (sem alterar nada)
  as abas e cabecalhos reais da spreadsheet e compara com o que `columns.py`
  espera, reportando abas/colunas em falta. `scripts/verificar_acesso.py`
  roda esse diagnostico e termina com codigo de saida 1 se houver divergencia.
- Sanity check de regras (proposta E): `sanity_regras.diagnosticar_regras`
  confere SINC_COLABORADOR invalido e quotas contraditorias. Nota importante
  validada com dados reais: a sincronizacao (`SINC_COLABORADOR`) e por
  linha/data de `AppAnualGlobal`, entao cruza departamento/funcao livremente
  — so precisa ser o mesmo `DIA DA SEMANA` (confirmado com o par real
  Jadson Felipe/Rosa Cunha, que sincronizam entre funcoes diferentes aos
  domingos). Rodar contra dados reais revelou um SINC genuinamente quebrado.
- Fecho do ciclo de zumbis (proposta B): `zumbi_writeback.py` calcula quais
  registros de `BP LOG` devem ser marcados como recuperados
  (`DISPONIBILIDADE=FALSE` + timestamp) apos o motor alocar um zumbi. A
  escrita de fato (`aplicar_atualizacoes_em_copia_teste`) so foi ligada
  contra copias `CLAUDE_BP LOG`; nunca contra o `BP LOG` original.
- Alerta de "SEM ALOCAÇÃO" (proposta D): `alerta_sem_alocacao.py` monta
  assunto/corpo do alerta a partir de `EMAIL LIDER`, mas **nao envia
  nada** — nao ha servico de e-mail configurado neste projeto.
- 46 testes unitarios passando (`uv run pytest`).
- Teste de integracao real executado com sucesso via
  `scripts/testar_ministros_quarta.py` (reexecutado apos ligar Excluse e o
  historico real): duplicou `BP ALGORITIMO` e `AppAnualGlobal` para
  `CLAUDE_BP ALGORITIMO` / `CLAUDE_AppAnualGlobal`, alocou 26 de 29 cultos
  de quarta-feira futuros e vazios entre os 15 ministros ativos — com os
  4 zumbis reais de `BP LOG` (Edna Souza, Elizabette Gomes, Gonçala Silva,
  Josimar Lima) recebendo prioridade nas primeiras vagas, como esperado — e
  escreveu o resultado somente na copia de teste. Abas originais
  verificadas intactas apos a execucao.

### Pendente / a validar

- Fase 0 (P1/P2/P3) ainda nao foi testada com dados reais porque as datas
  futuras da aba `AppAnualGlobal` ainda nao tem "TEMA DA MINISTRAÇÃO"
  preenchido (por isso o teste de integracao rodou sem exigir tema).
- O motor ainda nao escreve de volta em `BP LOG` (marcar um zumbi como
  recuperado, DISPONIBILIDADE=FALSE) nem em `LOG ALGORITIMO` (novo registro
  de execucao) — hoje so le esses historicos e escreve o resultado da
  alocacao em `AppAnualGlobal` (copia `CLAUDE_`).
- Testado apenas para o grupo D. MINISTROS / MINISTRO / QUARTA-FEIRA; outros
  departamentos/funcoes (AUXILIAR, CEIA, RECADOS, etc.) usam o mesmo motor
  mas ainda nao foram exercitados ponta a ponta.
- As copias `CLAUDE_BP ALGORITIMO` e `CLAUDE_AppAnualGlobal` ficaram na
  spreadsheet apos o teste, para voce revisar o resultado. Nao serao
  apagadas sem pedido explicito.
