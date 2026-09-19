---
name: pastoreio-validar-grupo
description: Introduz e valida uma combinação DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA em GRUPOS_VALIDADOS.md — o registo oficial de quais grupos já têm cobertura de teste de integração real revisada por humano. Use quando um grupo/função/dia novo (ou uma variação de um existente) precisa ser marcado como pronto para uso real, ou para checar o que ainda está pendente. Não use para gerar Rondas de um grupo já validado (pastoreio-executar-ronda).
---

# Validar um grupo (DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA)

`GRUPOS_VALIDADOS.md` (raiz do repositório) é o registo oficial. Formato:
uma linha por grupo validado, `DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA`;
linhas começadas por `#` são comentário.

`protocolo_validacao.avaliar_grupos` (em
`src/pastoreio_orquestrador/protocolo_validacao.py`) compara os grupos
ativos em `BP ALGORITIMO` (`RegraColaborador.chave_grupo`, só
`ATIVO=true`) com este registo, e `scripts/checklist_pre_alocacao.py`
já roda essa comparação (só leitura) como parte do checklist
pré-alocação — ver `pastoreio-executar-ronda`.

**Nota**: `GRUPOS_VALIDADOS.md` menciona um `scripts/listar_grupos.py` que
não existe atualmente em `scripts/` — a mesma comparação já é feita por
`scripts/checklist_pre_alocacao.py`. Se for criar um script dedicado
`listar_grupos.py`, é uma extensão pequena e determinística (reusa
`protocolo_validacao.avaliar_grupos`), não uma skill nova.

## O que "validado" exige de facto

Um grupo só pode ser considerado validado quando **todos** os pontos
abaixo foram verificados — não marque um grupo como validado
automaticamente só porque um script terminou sem lançar exceção:

1. **Estrutura carregada corretamente** — `carregar_regras_colaboradores`
   encontrou as linhas ativas certas do grupo (confira `N` = colaboradores
   ativos, sem duplicata de pessoa inflando a contagem — ver
   `CONCEITO_CICLO.md`).
2. **Regras avaliadas** — o motor rodou (`alocar_grupo` ou
   `_alocar_grupo_domingo_ceia_alternada`, conforme o grupo seja
   DOMINGO+CEIA ALTERNADA ou não) contra um ciclo completo real ou
   representativo, sem exceção.
3. **Integração executada** — o script de preenchimento correspondente
   (ver `pastoreio-executar-ronda`) rodou ponta a ponta contra dados reais
   da spreadsheet, não apenas dados sintéticos de teste unitário.
4. **Qualquer escrita ocorreu apenas em `CLAUDE_*`** — confirme que
   nenhuma aba original foi tocada (releia a aba original depois da
   execução e compare, se houver dúvida).
5. **Resultado verificado** — as decisões escritas (nomes, datas, motivos)
   fazem sentido face à hierarquia de prioridade, quotas, Excluse,
   aniversário e vizinhança daquele grupo especificamente. Casos de
   `SEM ALOCAÇÃO` foram confirmados como genuinamente impossíveis (ver
   `pastoreio-investigar-alocacao`), não como bug.
6. **Testes relevantes passaram** — `uv run pytest`, incluindo qualquer
   teste específico desse grupo/regra (ex.: `test_fase0_temas.py` para
   grupos QUARTA-FEIRA com tema, `test_ceia_alternada.py` para grupos
   DOMINGO com CEIA ALTERNADA).
7. **Validação humana identificada quando necessária** — se o resultado
   depende de uma interpretação de regra ambígua ou de um caso real
   incomum, isso foi reportado e confirmado por um humano antes de marcar
   o grupo como validado (não só "o script rodou sem erro").

## Workflow para um grupo novo

1. Identifique a chave exata: `DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA`
   (confira grafia contra `BP ALGORITIMO` real — espaços e acentuação
   importam para o match em `chave_grupo`).
2. Verifique se o **processo** de alocação desse grupo é igual a algum já
   validado (mesmo tipo de workflow — Ronda normal cronológica, ou
   DOMINGO+CEIA ALTERNADA). Se for igual, reuse o script
   `preencher_claude_*` mais parecido como base (ver
   `pastoreio-executar-ronda`) — não invente um processo novo só porque o
   grupo é novo.
3. Rode a integração real contra `CLAUDE_*` (nunca contra a aba original)
   e percorra os 7 pontos da secção anterior.
4. Só depois de todos os pontos confirmados, adicione a linha
   `DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA` em `GRUPOS_VALIDADOS.md`.
5. Rode `uv run python scripts/checklist_pre_alocacao.py` para confirmar
   que o grupo agora aparece como validado no relatório.
6. Aplique a avaliação de manutenção de skills
   (`pastoreio-manter-agents-skills`) — normalmente nenhuma skill nova é
   necessária aqui, só a entrada em `GRUPOS_VALIDADOS.md` e, se o processo
   era genuinamente novo (não apenas um novo grupo com o processo já
   conhecido), a atualização do script/skill correspondente.
