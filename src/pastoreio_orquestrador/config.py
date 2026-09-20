"""Configuracao do orquestrador, carregada de variaveis de ambiente / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    service_account_file: Path
    spreadsheet_id: str
    data_corte_historico: date


def _parse_data_corte_historico(valor: str) -> date:
    valor = valor.strip()
    if not valor:
        raise RuntimeError(
            "PASTOREIO_DATA_CORTE_HISTORICO nao definido. Configure o ficheiro .env "
            "(ex.: PASTOREIO_DATA_CORTE_HISTORICO=2026-10-01)."
        )
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise RuntimeError(
            "PASTOREIO_DATA_CORTE_HISTORICO invalido. Use o formato ISO YYYY-MM-DD "
            "(ex.: 2026-10-01)."
        ) from exc


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or PROJECT_ROOT / ".env")

    raw_sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
    data_corte_historico = _parse_data_corte_historico(
        os.environ.get("PASTOREIO_DATA_CORTE_HISTORICO", "")
    )

    if not raw_sa_path:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_FILE nao definido. Configure o ficheiro .env "
            "(veja .env.example)."
        )
    if not spreadsheet_id:
        raise RuntimeError(
            "SPREADSHEET_ID nao definido. Configure o ficheiro .env (veja .env.example)."
        )

    sa_path = Path(raw_sa_path)
    if not sa_path.is_absolute():
        sa_path = PROJECT_ROOT / sa_path

    if not sa_path.exists():
        raise RuntimeError(f"Ficheiro de credenciais nao encontrado em: {sa_path}")

    return Settings(
        service_account_file=sa_path,
        spreadsheet_id=spreadsheet_id,
        data_corte_historico=data_corte_historico,
    )
