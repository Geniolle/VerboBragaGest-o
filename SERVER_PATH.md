# Server Path

Reference for the intended production server and deployment location.

## Server Details

- SSH host: `opc@servidor-tesouraria-v2`
- Legacy SSH host in older Tesouraria docs: `opc@servidor-tesouraria`
- Remote project directory: `/home/opc/pastoreio-orquestrador`
- Production runtime: `systemd`
- Timer: `pastoreio-colaborador.timer`
- Service: `pastoreio-colaborador.service`
- Start command:
  `/usr/bin/env uv --cache-dir /home/opc/pastoreio-orquestrador/.uv-cache run python scripts/Servidor/executar_colaborador_agendado.py --aplicar`

## Source

This follows the production pattern documented in the Tesouraria project:

- `C:/workspace/Tesouraria-SOMA/SERVER_PATH.md`
- `C:/workspace/Tesouraria-SOMA/DEPLOYMENT.md`
- `C:/workspace/Tesouraria-SOMA/PRODUCTION_RUNTIME.md`

Tesouraria currently documents production as `systemd` on
`opc@servidor-tesouraria-v2`, with older docs also mentioning
`opc@servidor-tesouraria`.

## Notes

- The local Windows Task Scheduler must not be used for the productive
  Colaborador process.
- If the SSH alias or remote directory changes in the real environment,
  update this file, `DEPLOYMENT.md`, `PRODUCTION_RUNTIME.md`, and the
  `pastoreio-utilizador` skill together.

