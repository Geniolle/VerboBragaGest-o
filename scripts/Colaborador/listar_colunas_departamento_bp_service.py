"""Lista colunas de BP SERVICE cujo cabecalho comeca com D.

Read-only: nao escreve em nenhuma sheet. Apoio ao processo
"Atualizar BP AUTORITY".
"""

from __future__ import annotations

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"


def main() -> None:
    guard = SpreadsheetGuard(load_settings())
    valores = guard.read_worksheet(SHEET_BP_SERVICE)
    header = valores[0] if valores else []

    colunas = [
        (indice + 1, str(nome).strip())
        for indice, nome in enumerate(header)
        if str(nome).strip().upper().startswith("D.")
    ]

    print("###############################################################################")
    print("[BP SERVICE] COLUNAS COM PREFIXO D.")
    print(f"Total: {len(colunas)}")
    print("###############################################################################")
    for numero, nome in colunas:
        print(f"{numero}: {nome}")


if __name__ == "__main__":
    main()
