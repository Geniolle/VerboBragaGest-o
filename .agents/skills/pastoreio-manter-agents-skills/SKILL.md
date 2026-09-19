---
name: pastoreio-manter-agents-skills
description: Avalia e mantém AGENTS.md e as skills do Pastoreio Orquestrador quando novos processos, workflows, regras operacionais ou mudanças arquiteturais são introduzidos. Use antes e depois de alterações significativas para decidir se deve criar, atualizar, fundir ou manter skills e instruções do projeto. Não use para executar o trabalho em si (Ronda, investigação, alteração de regra, validação de grupo) — só para decidir onde/como documentar o conhecimento gerado por esse trabalho.
---

# Manter AGENTS.md e skills

Meta-skill: não executa trabalho de negócio, decide como o conhecimento
gerado por uma tarefa deve (ou não) ficar registado na estrutura de
agente/skills deste repositório.

Use sempre que:

- surgir um processo novo;
- houver mudança significativa de workflow;
- uma regra operacional for alterada;
- uma funcionalidade nova for criada;
- uma skill existente aparentar estar desatualizada face ao código atual;
- houver dúvida sobre onde documentar conhecimento novo.

## Árvore de decisão

```text
Mudança nova
   |
   +-- É regra válida para praticamente todo trabalho no projeto?
   |      |
   |      +-- SIM -> AGENTS.md
   |
   +-- É workflow repetível e especializado?
   |      |
   |      +-- SIM
   |          |
   |          +-- Já existe skill correspondente?
   |                 |
   |                 +-- SIM -> atualizar skill existente
   |                 |
   |                 +-- NÃO -> criar nova skill
   |
   +-- É conhecimento detalhado que uma skill consulta?
   |      |
   |      +-- SIM -> references/ da skill, ou documento CONCEITO_*.md
   |
   +-- É comportamento executável/determinístico?
   |      |
   |      +-- SIM -> Python em src/pastoreio_orquestrador/, scripts/, tests/
   |
   +-- É apenas alteração local/pontual?
          |
          +-- SIM -> não criar skill, não alterar AGENTS.md
```

## Como aplicar cada ramo

- **AGENTS.md**: só regras transversais — segurança, padrão obrigatório de
  testes, arquitetura, política de configuração. Mantenha-o curto.
- **Skill existente**: se o workflow já é coberto por
  `pastoreio-executar-ronda`, `pastoreio-investigar-alocacao`,
  `pastoreio-alterar-regra` ou `pastoreio-validar-grupo` e a mudança é só
  uma nova etapa/validação/caso dentro desse mesmo processo, edite o
  `SKILL.md` correspondente. Não crie uma skill nova para uma variação de
  parâmetro (ex.: um novo grupo `DEPARTAMENTO###FUNÇÃO###DIA` que segue o
  mesmo processo de Ronda de sempre não é motivo para nova skill).
- **Nova skill**: só quando o processo é genuinamente diferente de todos
  os existentes — comportamento/fronteiras diferentes, não apenas
  parâmetros diferentes. Nomeie com o prefixo `pastoreio-` e um verbo claro
  (`pastoreio-<verbo>-<objeto>`). Frontmatter obrigatório:

  ```yaml
  ---
  name: nome-da-skill
  description: Explique claramente quando esta skill deve e não deve ser usada.
  ---
  ```

  A `description` precisa permitir identificar a skill certa só pelos
  metadados — evite descriptions vagas ("ajuda no Pastoreio"); prefira
  específicas (o que cobre, quando usar, quando NÃO usar).

- **references/CONCEITO_*.md**: conhecimento de negócio aprofundado que
  uma skill só precisa consultar (não reescrever) vai em
  `CONCEITO_<tema>.md` na raiz, ou em `references/` dentro da própria
  skill se for conhecimento específico daquele workflow e não pertencer ao
  README nem a um `CONCEITO_*.md` existente. Nunca copie blocos grandes de
  um `CONCEITO_*.md` para dentro de uma skill — aponte para o ficheiro com
  caminho relativo correto (skills ficam em
  `.agents/skills/<nome>/SKILL.md`, então a raiz do repo é `../../../`).
- **Código/scripts/tests**: qualquer coisa executável/determinística
  (algoritmo de alocação, geração de relatório, escrita na spreadsheet)
  é código Python, nunca texto duplicado dentro de uma skill. A skill só
  descreve o workflow em torno do código e referencia o módulo/script
  responsável.
- **Nenhuma alteração**: correções pontuais, ajustes de parâmetro, e
  qualquer mudança que não crie conhecimento reutilizável não geram
  alteração de `AGENTS.md` nem de skill.

## Reorganizar skills

Se duas ou mais skills começarem a sobrepor responsabilidade: funda,
divida corretamente, renomeie, mova referências ou remova duplicação.
Nunca mantenha duas skills concorrentes cobrindo o mesmo workflow sem
motivo justificado — isso é decidido aqui, não silenciosamente durante
outra tarefa.

## Checklist antes de terminar qualquer tarefa significativa

1. Reler a lista de skills existentes (`.agents/skills/*/SKILL.md`,
   `name` + `description`).
2. Decidir, usando a árvore acima: nenhuma alteração / atualizar skill /
   criar skill / atualizar `AGENTS.md` / reorganizar skills.
3. Se algo mudou, aplicar a alteração como parte da mesma tarefa (não é
   preciso pedir autorização extra para manutenção de documentação agente
   que seja consequência direta do que foi pedido).
4. Confirmar que nenhuma skill ficou duplicando outra, e que nenhuma skill
   duplica o `motor.py` ou um `CONCEITO_*.md`.
5. Confirmar que `AGENTS.md` continua curto e só com regras universais.

## O que NÃO fazer

- Não criar uma skill por script Python, função, departamento, colaborador
  ou coluna.
- Não registar histórico de sessão, números de teste, nomes de commit ou
  valores temporários em nenhum `SKILL.md` — isso é para o Git.
- Não assumir que uma skill está correta só porque existe: se o código e a
  skill divergirem, o código + testes são a fonte de verdade; corrija a
  skill.
