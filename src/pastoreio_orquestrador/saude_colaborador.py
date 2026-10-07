"""Snapshot unico de saude do processo Colaborador (sem historico)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def agora_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ler_saude(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def gravar_saude(path: Path, **changes: object) -> dict:
    """Atualiza e sobrescreve um unico snapshot JSON de forma atomica."""
    payload = ler_saude(path)
    payload.update(changes)
    payload["updated_at"] = agora_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return payload
