"""Diagnostica um colaborador em BP SERVICE, BP AUTORITY e BP ALGORITIMO.

Read-only: nao escreve em nenhuma sheet.
"""

from __future__ import annotations

import argparse
import re
import unicodedata

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


SHEETS = ("BP SERVICE", "BP AUTORITY", "BP ALGORITIMO")
COLS_INTERESSE = (
    "ID_USER",
    "NOME",
    "DEPARTAMENTO",
    "ATIVO",
    "INATIVO",
    "DEPARTAMENTOS",
    "BP AUTORITY",
    "TYPE",
)


def map_headers(header: list[str]) -> dict[str, int]:
    return {str(nome).strip(): i for i, nome in enumerate(header) if str(nome).strip()}


def get(row: list[str], idx: dict[str, int], col: str) -> str:
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def normalize_text(value: object) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text)


def is_true(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"


def print_row(sheet: str, linha: int, row: list[str], idx: dict[str, int], header: list[str]) -> None:
    print(f"Linha {linha}:")
    for col in COLS_INTERESSE:
        if col in idx:
            print(f"  {col}: {get(row, idx, col)!r}")

    dept_cols = [
        col for col in header if str(col).strip().upper().startswith("D.") and is_true(get(row, idx, str(col).strip()))
    ]
    authority_cols = [
        col for col in header if str(col).strip().upper().startswith("COLABORADOR_") and is_true(get(row, idx, str(col).strip()))
    ]
    if dept_cols:
        print(f"  D.* true: {', '.join(str(c).strip() for c in dept_cols)}")
    if authority_cols:
        print(f"  COLABORADOR_* true: {', '.join(str(c).strip() for c in authority_cols)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("nome", nargs="+")
    args = parser.parse_args()
    nome_alvo = normalize_text(" ".join(args.nome))

    guard = SpreadsheetGuard(load_settings())

    for sheet in SHEETS:
        valores = guard.read_worksheet(sheet)
        if not valores:
            print(f"\n=== {sheet}: vazio ===")
            continue
        header = [str(h).strip() for h in valores[0]]
        idx = map_headers(header)
        print("")
        print("=" * 79)
        print(sheet)
        print("=" * 79)
        if "NOME" not in idx:
            print("Sem coluna NOME.")
            continue

        encontrados = []
        for linha, row in enumerate(valores[1:], start=2):
            if normalize_text(get(row, idx, "NOME")) == nome_alvo:
                encontrados.append((linha, row))

        print(f"Ocorrencias exatas por nome normalizado: {len(encontrados)}")
        for linha, row in encontrados:
            print_row(sheet, linha, row, idx, header)

    print("")
    print("=" * 79)
    print("FIM")
    print("=" * 79)


if __name__ == "__main__":
    main()
