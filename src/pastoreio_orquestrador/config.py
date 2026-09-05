"""Configuracao do orquestrador, carregada de variaveis de ambiente / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    service_account_file: Path
    spreadsheet_id: str


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or PROJECT_ROOT / ".env")

    raw_sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()

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

    return Settings(service_account_file=sa_path, spreadsheet_id=spreadsheet_id)
