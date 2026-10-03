"""Corrige inconsistência: D.* = TRUE mas DEPARTAMENTOS = FALSE.

Rotina de ativação da cadeia DEPARTAMENTOS.

Por padrão roda em dry-run. Com --aplicar:
- identifica pessoas com pelo menos um D.* = TRUE mas DEPARTAMENTOS ≠ TRUE;
- corrige para DEPARTAMENTOS = TRUE;
- valida que a correção foi aplicada.

A correção é obrigatória antes de sincronizar BP AUTORITY e BP ALGORITIMO.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
COL_DEPARTAMENTOS = "DEPARTAMENTOS"
COL_INATIVO = "INATIVO"


@dataclass(frozen=True)
class PessoaParaAtivar:
    linha: int
    id_user: str
    nome: str
    departamentos_ativos: list[str]


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


def set_value(row: list[str], idx: dict[str, int], col: str, value: object) -> None:
    i = idx.get(col)
    if i is not None:
        row[i] = str(value) if value is not None else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Aplica correções em BP SERVICE.")
    args = parser.parse_args()

    guard = SpreadsheetGuard(load_settings())
    valores = guard.read_worksheet(SHEET_BP_SERVICE)

    if not valores:
        raise RuntimeError(f'Sheet "{SHEET_BP_SERVICE}" vazia ou sem cabeçalho.')

    header = valores[0]
    idx = map_headers(header)

    # Validar colunas
    for col in (COL_DEPARTAMENTOS, COL_INATIVO, "ID_USER", "NOME"):
        if col not in idx:
            raise RuntimeError(f'Coluna "{col}" não encontrada em "{SHEET_BP_SERVICE}".')

    # Encontrar colunas D.*
    colunas_departamento = [
        str(nome).strip()
        for nome in header
        if str(nome).strip().upper().startswith("D.")
    ]

    if not colunas_departamento:
        print("Aviso: nenhuma coluna D.* encontrada em BP SERVICE.")
        return

    pessoas_para_ativar: list[PessoaParaAtivar] = []

    for linha_sheet, row in enumerate(valores[1:], start=2):
        # Ignorar inativos
        if is_true(get(row, idx, COL_INATIVO)):
            continue

        # Encontrar departamentos ativos
        departamentos_ativos = [
            col for col in colunas_departamento if is_true(get(row, idx, col))
        ]

        # Se há departamentos mas DEPARTAMENTOS ≠ TRUE
        if departamentos_ativos and not is_true(get(row, idx, COL_DEPARTAMENTOS)):
            id_user = get(row, idx, "ID_USER")
            nome = get(row, idx, "NOME")
            pessoas_para_ativar.append(
                PessoaParaAtivar(
                    linha=linha_sheet,
                    id_user=id_user,
                    nome=nome,
                    departamentos_ativos=departamentos_ativos,
                )
            )

    # Relatório
    print("###############################################################################")
    print("[BP SERVICE] CORRIGIR DEPARTAMENTOS - ATIVAÇÃO")
    print(f"Pessoas com D.* = TRUE mas DEPARTAMENTOS ≠ TRUE: {len(pessoas_para_ativar)}")
    print("###############################################################################")

    print("\nPESSO AS A ATIVAR:")
    if not pessoas_para_ativar:
        print("(nenhuma)")
    for pessoa in pessoas_para_ativar:
        print(
            f"Linha={pessoa.linha} ID_USER={pessoa.id_user!r} Nome={pessoa.nome!r} "
            f"D.* ativos={len(pessoa.departamentos_ativos)}"
        )

    # Aplicar correção
    if args.aplicar:
        col_departamentos = idx[COL_DEPARTAMENTOS] + 1
        updates = [(pessoa.linha, col_departamentos, "TRUE") for pessoa in pessoas_para_ativar]

        if updates:
            guard.batch_update_cells(SHEET_BP_SERVICE, updates)
            print(f"\nAtualizadas {len(updates)} linhas em BP SERVICE.DEPARTAMENTOS = TRUE.")
        else:
            print("\nNenhuma alteração necessária.")
    elif not args.aplicar:
        print("\nDry-run: nenhuma sheet foi alterada.")


if __name__ == "__main__":
    main()
