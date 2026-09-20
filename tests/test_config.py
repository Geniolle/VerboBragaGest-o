from datetime import date

import pytest

from pastoreio_orquestrador.config import load_settings


def test_load_settings_carrega_data_corte_historico(tmp_path, monkeypatch):
    credenciais = tmp_path / "service_account.json"
    credenciais.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"GOOGLE_SERVICE_ACCOUNT_FILE={credenciais}",
                "SPREADSHEET_ID=spreadsheet-teste",
                "PASTOREIO_DATA_CORTE_HISTORICO=2026-10-01",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("PASTOREIO_DATA_CORTE_HISTORICO", raising=False)

    settings = load_settings(env_file)

    assert settings.data_corte_historico == date(2026, 10, 1)


def test_load_settings_falha_sem_data_corte_historico(tmp_path, monkeypatch):
    credenciais = tmp_path / "service_account.json"
    credenciais.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"GOOGLE_SERVICE_ACCOUNT_FILE={credenciais}\nSPREADSHEET_ID=spreadsheet-teste\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("PASTOREIO_DATA_CORTE_HISTORICO", raising=False)

    with pytest.raises(RuntimeError, match="PASTOREIO_DATA_CORTE_HISTORICO"):
        load_settings(env_file)
