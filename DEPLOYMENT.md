# Deployment Guide

This project should run the productive Colaborador process on the server
through `systemd`, following the same operational model used by
Tesouraria-SOMA.

## Active Production Runtime

- Host: `opc@servidor-tesouraria-v2`
- Project directory: `/home/opc/pastoreio-orquestrador`
- Runtime: `systemd`
- Timer: `pastoreio-colaborador.timer`
- Service: `pastoreio-colaborador.service`
- Runner: `scripts/Servidor/executar_colaborador_agendado.py --aplicar`

## Remote Update Steps

```bash
ssh opc@servidor-tesouraria-v2
cd /home/opc/pastoreio-orquestrador
git pull origin master
uv sync
sudo scripts/Servidor/instalar_timer_colaborador_systemd.sh
systemctl list-timers pastoreio-colaborador.timer --no-pager
sudo systemctl status pastoreio-colaborador.timer --no-pager
sudo systemctl status pastoreio-colaborador.service --no-pager
sudo journalctl -u pastoreio-colaborador.service -n 100 --no-pager
```

If the `servidor-tesouraria-v2` alias is not available in the current client
machine, restore the same SSH configuration used for Tesouraria-SOMA before
deploying.

## Pre-Deploy Checks

1. Confirm `git status --short` only contains expected changes.
2. Confirm no `.env`, credentials, runtime logs, caches, or virtual
   environments are staged.
3. Run syntax/tests locally where the environment permits.
4. Confirm production is still `systemd`, not Docker or Windows Task Scheduler.

## Operational Checks

```bash
cd /home/opc/pastoreio-orquestrador
uv --cache-dir .uv-cache run python scripts/Colaborador/analisar_membresia_bp_service.py
systemctl list-timers pastoreio-colaborador.timer --no-pager
sudo journalctl -u pastoreio-colaborador.service --since "10 minutes ago" --no-pager
tail -n 120 runtime/colaborador_ultimo.log
```

