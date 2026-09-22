# Production Runtime

The productive Colaborador process should run as a `systemd` timer/service on
the same server model used by Tesouraria-SOMA.

## Active Production

- Host: `opc@servidor-tesouraria-v2`
- Project directory: `/home/opc/pastoreio-orquestrador`
- Runtime: `systemd`
- Timer name: `pastoreio-colaborador.timer`
- Service name: `pastoreio-colaborador.service`
- Schedule: every 60 seconds via `OnUnitActiveSec=1min`
- Lock: `runtime/colaborador.lock`
- Last consolidated log: `runtime/colaborador_ultimo.log`

## Service Files

- `scripts/Servidor/systemd/pastoreio-colaborador.service`
- `scripts/Servidor/systemd/pastoreio-colaborador.timer`
- `scripts/Servidor/instalar_timer_colaborador_systemd.sh`

## Operational Rule

Do not run the productive Colaborador process from the local Windows Task
Scheduler. Local execution is allowed only for manual validation/dry-run or an
explicit one-off apply.

If production runtime changes from `systemd`, update this file,
`SERVER_PATH.md`, `DEPLOYMENT.md`, and the `pastoreio-utilizador` skill in the
same change.

