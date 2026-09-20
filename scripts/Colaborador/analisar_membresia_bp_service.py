"""Analisa linhas pendentes de Membresia para o processo Utilizador.

Read-only: nao escreve em nenhuma sheet.
"""

from __future__ import annotations

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


SHEET_MEMBRESIA = "Membresia"
COL_FLAG = "BP SERVICE"
COL_NOME = "Nome Próprio + Apelido"
COL_EMAIL = "Email"
COL_TELEFONE = "Contacto Telefónico"
COL_NASCIMENTO = "Data de Nascimento"


def _idx(header: list[str]) -> dict[str, int]:
    return {str(nome).strip(): i for i, nome in enumerate(header)}


def _get(row: list[str], idx: dict[str, int], col: str) -> str:
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def main() -> None:
    guard = SpreadsheetGuard(load_settings())
    valores = guard.read_worksheet(SHEET_MEMBRESIA)

    if not valores:
        raise RuntimeError(f'Sheet "{SHEET_MEMBRESIA}" vazia ou sem cabecalho.')

    header = valores[0]
    idx = _idx(header)
    if COL_FLAG not in idx:
        raise RuntimeError(f'Coluna "{COL_FLAG}" nao encontrada em "{SHEET_MEMBRESIA}".')

    pendentes: list[tuple[int, list[str]]] = []
    processados: list[tuple[int, list[str]]] = []
    outros: list[tuple[int, list[str], str]] = []

    for linha_sheet, row in enumerate(valores[1:], start=2):
        flag = _get(row, idx, COL_FLAG)
        if not flag:
            pendentes.append((linha_sheet, row))
        elif flag.upper() == "TRUE":
            processados.append((linha_sheet, row))
        else:
            outros.append((linha_sheet, row, flag))

    print("###############################################################################")
    print("[MEMBRESIA-BP] ANALISE READ-ONLY")
    print(f"Linhas de dados: {max(len(valores) - 1, 0)}")
    print(f"BP SERVICE vazio: {len(pendentes)}")
    print(f"BP SERVICE TRUE: {len(processados)}")
    print(f"BP SERVICE outros valores: {len(outros)}")
    print("###############################################################################")

    print("\nPENDENTES (BP SERVICE vazio)")
    if not pendentes:
        print("(nenhum)")
    for linha, row in pendentes:
        print(
            f"Linha {linha}: "
            f"Nome={_get(row, idx, COL_NOME)!r} | "
            f"Email={_get(row, idx, COL_EMAIL)!r} | "
            f"Telefone={_get(row, idx, COL_TELEFONE)!r} | "
            f"Nascimento={_get(row, idx, COL_NASCIMENTO)!r}"
        )

    print("\nOUTROS VALORES EM BP SERVICE")
    if not outros:
        print("(nenhum)")
    for linha, row, flag in outros:
        print(f"Linha {linha}: BP SERVICE={flag!r} | Nome={_get(row, idx, COL_NOME)!r}")


if __name__ == "__main__":
    main()
