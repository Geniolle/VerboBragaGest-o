# Production Runtime

The productive Colaborador process should run as a `systemd` timer/service on
the same server model used by Tesouraria-SOMA.

## Active Production

- Host: `opc@servidor-tesouraria-v2`
- Project directory: `/home/opc/pastoreio-orquestrador`
- Runtime: `systemd`
- Timer name: `pastoreio-colaborador.timer`
- Service name: `pastoreio-colaborador.service`
- Schedule: five minutes after the previous run finishes, via
  `OnUnitInactiveSec=5min`
- Lock: `runtime/colaborador.lock`
- Last consolidated log: `runtime/colaborador_ultimo.log`
- Current health snapshot: `runtime/colaborador_health.json`
- Health watchdog: `pastoreio-colaborador-health.timer`

## Service Files

- `scripts/Servidor/systemd/pastoreio-colaborador.service`
- `scripts/Servidor/systemd/pastoreio-colaborador.timer`
- `scripts/Servidor/systemd/pastoreio-colaborador-health.service`
- `scripts/Servidor/systemd/pastoreio-colaborador-health.timer`
- `scripts/Servidor/instalar_timer_colaborador_systemd.sh`

## Operational Rule

Do not run the productive Colaborador process from the local Windows Task
Scheduler. Local execution is allowed only for manual validation/dry-run or an
explicit one-off apply.

Both the consolidated log and the health JSON are single current-state files.
Each execution overwrites them; the application does not retain historical
execution logs.

If production runtime changes from `systemd`, update this file,
`SERVER_PATH.md`, `DEPLOYMENT.md`, and the `pastoreio-utilizador` skill in the
same change.
