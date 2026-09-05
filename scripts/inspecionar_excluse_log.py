"""Leitura (somente leitura, nunca escreve) das abas Excluse, CONF_ALGORITIMO,
BP LOG e LOG ALGORITIMO para validar a logica de esta_bloqueado_por_excluse e
planejar a ligacao do historico ao motor.

Uso:
    uv run python scripts/inspecionar_excluse_log.py
"""
from __future__ import annotations

import json
from pathlib import Path

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

OUT = Path(__file__).resolve().parent.parent / "scratch" / "amostras" / "excluse_log_conf.json"


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)

    dados = {}
    for aba in ["Excluse", "CONF_ALGORITIMO", "BP LOG", "LOG ALGORITIMO", "AppAnualGlobal"]:
        valores = guard.read_worksheet(aba)
        header = valores[0] if valores else []
        amostra = valores[1:6]
        dados[aba] = {
            "header": header,
            "num_linhas": len(valores) - 1 if valores else 0,
            "amostra": amostra,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito em {OUT}")


if __name__ == "__main__":
    main()
