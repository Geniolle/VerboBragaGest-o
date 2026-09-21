"""Lista linhas de BP SERVICE onde INATIVO nao e verdadeiro.

Read-only: nao escreve em nenhuma sheet. Primeira leitura exploratoria do
processo "Atualizar BP AUTORITY".
"""

from __future__ import annotations

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
COL_INATIVO = "INATIVO"
COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_EMAIL = "EMAIL"
COL_TELEFONE = "TELEFONE"


def map_headers(header: list[str]) -> dict[str, int]:
    return {str(nome).strip(): i for i, nome in enumerate(header) if str(nome).strip()}


def get(row: list[str], idx: dict[str, int], col: str) -> str:
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def is_true(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"


def main() -> None:
    guard = SpreadsheetGuard(load_settings())
    valores = guard.read_worksheet(SHEET_BP_SERVICE)

    if not valores:
        raise RuntimeError(f'Sheet "{SHEET_BP_SERVICE}" vazia ou sem cabecalho.')

    idx = map_headers(valores[0])
    if COL_INATIVO not in idx:
        raise RuntimeError(f'Coluna "{COL_INATIVO}" nao encontrada em "{SHEET_BP_SERVICE}".')

    linhas = []
    for linha_sheet, row in enumerate(valores[1:], start=2):
        inativo = get(row, idx, COL_INATIVO)
        if not is_true(inativo):
            linhas.append((linha_sheet, row, inativo))

    print("###############################################################################")
    print("[BP SERVICE] LINHAS COM INATIVO DIFERENTE DE TRUE")
    print(f"Total de linhas de dados: {max(len(valores) - 1, 0)}")
    print(f"Linhas encontradas: {len(linhas)}")
    print("###############################################################################")

    for linha, row, inativo in linhas:
        print(
            f"Linha {linha}: "
            f"ID_USER={get(row, idx, COL_ID_USER)!r} | "
            f"Nome={get(row, idx, COL_NOME)!r} | "
            f"Email={get(row, idx, COL_EMAIL)!r} | "
            f"Telefone={get(row, idx, COL_TELEFONE)!r} | "
            f"INATIVO={inativo!r}"
        )


if __name__ == "__main__":
    main()
