# Protocolo de validação por grupo (proposta F)

Nenhum grupo (combinação `DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA`) deve ser
considerado pronto para uso real até ter pelo menos **um teste de
integração real** contra a spreadsheet, escrevendo apenas em cópias
`CLAUDE_*`, com o resultado revisado por um humano.

Este ficheiro é a lista de grupos validados. `scripts/listar_grupos.py` lê
os grupos ativos em `BP ALGORITIMO` e cruza com esta lista, mostrando o que
ainda está pendente.

Formato: uma linha por grupo validado, no formato
`DEPARTAMENTO###FUNÇÃO###DIA DA SEMANA`. Linhas começadas por `#` são
comentário.

## Validados

D. MINISTROS###MINISTRO###QUARTA-FEIRA
