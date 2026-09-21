"""Lista o cabecalho de uma sheet.

Read-only: nao escreve em nenhuma sheet.
"""

from __future__ import annotations

import argparse

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet", nargs="+")
    args = parser.parse_args()
    sheet = " ".join(args.sheet)

    guard = SpreadsheetGuard(load_settings())
    valores = guard.read_worksheet(sheet)
    header = valores[0] if valores else []

    print(f"--- {sheet} ---")
    print(f"Total de colunas: {len(header)}")
    for i, nome in enumerate(header, start=1):
        print(f"{i}: {nome}")


if __name__ == "__main__":
    main()
