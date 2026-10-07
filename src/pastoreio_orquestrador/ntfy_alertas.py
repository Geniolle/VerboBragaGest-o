"""Alertas ntfy por transicao de estado do processo Colaborador."""

from __future__ import annotations

import json
import os
import socket
import urllib.request
from pathlib import Path
from typing import Callable

Sender = Callable[[urllib.request.Request, float], None]


def _estado_anterior(state_file: Path) -> str | None:
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    estado = payload.get("estado")
    return estado if estado in {"success", "failure"} else None


def _gravar_estado(state_file: Path, estado: str) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(state_file.suffix + ".tmp")
    tmp.write_text(json.dumps({"estado": estado}), encoding="utf-8")
    os.replace(tmp, state_file)


def _enviar(request: urllib.request.Request, timeout: float) -> None:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read(1)


def notificar_transicao(
    *,
    exit_code: int,
    state_file: Path,
    timestamp: str,
    url: str | None = None,
    token: str | None = None,
    hostname: str | None = None,
    timeout: float = 10.0,
    sender: Sender = _enviar,
) -> str:
    """Notifica apenas primeira falha e recuperacao; nunca gera spam por estado igual."""
    target = (url if url is not None else os.environ.get("NTFY_URL", "")).strip()
    if not target:
        return "desativado"

    atual = "success" if exit_code == 0 else "failure"
    anterior = _estado_anterior(state_file)

    if atual == anterior:
        return "sem mudanca"
    if atual == "success" and anterior != "failure":
        _gravar_estado(state_file, atual)
        return "estado inicial saudavel"

    host = hostname or socket.gethostname()
    if atual == "failure":
        title = "Pastoreio Orquestrador - FALHA"
        message = f"O processo Colaborador falhou em {host}. Exit code: {exit_code}. Data: {timestamp}."
        priority = "urgent"
        tags = "warning,rotating_light"
    else:
        title = "Pastoreio Orquestrador - RECUPERADO"
        message = f"O processo Colaborador voltou a executar com sucesso em {host}. Data: {timestamp}."
        priority = "default"
        tags = "white_check_mark"

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
        "Content-Type": "text/plain; charset=utf-8",
    }
    auth_token = (token if token is not None else os.environ.get("NTFY_TOKEN", "")).strip()
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    request = urllib.request.Request(
        target,
        data=message.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        sender(request, timeout)
    except Exception as exc:  # O alerta nunca mascara o exit code real do processo.
        return f"erro ao enviar: {type(exc).__name__}: {exc}"

    _gravar_estado(state_file, atual)
    return "falha notificada" if atual == "failure" else "recuperacao notificada"
