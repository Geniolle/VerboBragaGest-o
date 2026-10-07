"""Watchdog do Colaborador: timer ativo e snapshot recente, sem historico."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pastoreio_orquestrador.ntfy_alertas import notificar_transicao
from pastoreio_orquestrador.saude_colaborador import ler_saude

ROOT_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT_DIR / "runtime"
HEALTH_FILE = RUNTIME_DIR / "colaborador_health.json"
NTFY_STATE_FILE = RUNTIME_DIR / "colaborador_ntfy_state.json"


def parse_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def avaliar_saude(timer_active: bool, health: dict, now: datetime, max_age_seconds: int) -> tuple[bool, str]:
    if not timer_active:
        return False, "timer inativo"
    state = health.get("state")
    if state == "FAILED":
        return False, f"ultima execucao falhou na etapa {health.get('failed_stage') or '(desconhecida)'}"
    reference = parse_datetime(health.get("updated_at"))
    if reference is None:
        return False, "snapshot de saude ausente ou invalido"
    age = (now - reference.astimezone(timezone.utc)).total_seconds()
    if age > max_age_seconds:
        return False, f"snapshot atrasado ha {int(age)} segundos"
    if state not in {"HEALTHY", "RUNNING"}:
        return False, f"estado inesperado: {state!r}"
    return True, f"estado {state}; snapshot ha {int(max(age, 0))} segundos"


def main() -> int:
    timer = subprocess.run(
        ["systemctl", "is-active", "pastoreio-colaborador.timer"],
        capture_output=True,
        text=True,
        check=False,
    )
    now = datetime.now(timezone.utc)
    healthy, detail = avaliar_saude(
        timer.returncode == 0 and timer.stdout.strip() == "active",
        ler_saude(HEALTH_FILE),
        now,
        int(os.environ.get("PASTOREIO_HEALTH_MAX_AGE_SECONDS", "900")),
    )
    result = notificar_transicao(
        exit_code=0 if healthy else 1,
        state_file=NTFY_STATE_FILE,
        timestamp=now.astimezone().isoformat(timespec="seconds"),
    )
    print(f"[HEALTH] {'OK' if healthy else 'FALHA'}: {detail}; ntfy={result}")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
