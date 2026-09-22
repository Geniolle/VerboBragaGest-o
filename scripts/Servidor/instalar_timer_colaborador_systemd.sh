#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="pastoreio-colaborador.service"
TIMER_NAME="pastoreio-colaborador.timer"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

install -m 0644 "$SOURCE_DIR/scripts/Servidor/systemd/$SERVICE_NAME" "/etc/systemd/system/$SERVICE_NAME"
install -m 0644 "$SOURCE_DIR/scripts/Servidor/systemd/$TIMER_NAME" "/etc/systemd/system/$TIMER_NAME"

systemctl daemon-reload
systemctl enable --now "$TIMER_NAME"
systemctl list-timers "$TIMER_NAME" --no-pager

