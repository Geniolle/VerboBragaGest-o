"""Valida consistencia entre DEPARTAMENTOS, BP AUTORITY e colunas D.*.

Read-only: nao escreve em nenhuma sheet. Apoio ao processo
"Atualizar BP AUTORITY".
"""

from __future__ import annotations

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
COL_DEPARTAMENTOS = "DEPARTAMENTOS"
COL_BP_AUTORITY = "BP AUTORITY"
COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_INATIVO = "INATIVO"


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

    header = valores[0]
    idx = map_headers(header)
    for coluna in (COL_DEPARTAMENTOS, COL_BP_AUTORITY, COL_INATIVO):
        if coluna not in idx:
            raise RuntimeError(f'Coluna "{coluna}" nao encontrada em "{SHEET_BP_SERVICE}".')

    colunas_departamento = [
        str(nome).strip()
        for nome in header
        if str(nome).strip().upper().startswith("D.")
    ]

    faltando_flag_geral = []
    flag_geral_sem_departamento = []
    bp_autority_sem_departamento = []
    consistentes = 0
    fora_escopo_inativos = 0

    for linha_sheet, row in enumerate(valores[1:], start=2):
        if is_true(get(row, idx, COL_INATIVO)):
            fora_escopo_inativos += 1
            continue

        departamentos_marcados = [
            col for col in colunas_departamento if is_true(get(row, idx, col))
        ]
        flag_geral = is_true(get(row, idx, COL_DEPARTAMENTOS))
        bp_autority = get(row, idx, COL_BP_AUTORITY)
        bp_autority_preenchido = bool(bp_autority)

        if departamentos_marcados and not flag_geral:
            faltando_flag_geral.append((linha_sheet, row, departamentos_marcados))
        elif not departamentos_marcados and flag_geral:
            flag_geral_sem_departamento.append((linha_sheet, row))
        elif not departamentos_marcados and bp_autority_preenchido:
            bp_autority_sem_departamento.append((linha_sheet, row))
        else:
            consistentes += 1

    print("###############################################################################")
    print("[BP SERVICE] VALIDACAO DEPARTAMENTOS x D.*")
    print(f"Total de linhas de dados: {max(len(valores) - 1, 0)}")
    print(f"Linhas fora do escopo por INATIVO=true: {fora_escopo_inativos}")
    print(f"Colunas D.* analisadas: {len(colunas_departamento)}")
    print(f"Linhas consistentes: {consistentes}")
    print(f"D.* true mas DEPARTAMENTOS nao true: {len(faltando_flag_geral)}")
    print(
        "DEPARTAMENTOS true sem nenhum D.* true "
        f"(limpar DEPARTAMENTOS e BP AUTORITY): {len(flag_geral_sem_departamento)}"
    )
    print(f"BP AUTORITY preenchido sem nenhum D.* true: {len(bp_autority_sem_departamento)}")
    print("###############################################################################")

    print("\nD.* TRUE MAS DEPARTAMENTOS NAO TRUE")
    if not faltando_flag_geral:
        print("(nenhum)")
    for linha, row, departamentos_marcados in faltando_flag_geral:
        print(
            f"Linha {linha}: "
            f"ID_USER={get(row, idx, COL_ID_USER)!r} | "
            f"Nome={get(row, idx, COL_NOME)!r} | "
            f"INATIVO={get(row, idx, COL_INATIVO)!r} | "
            f"DEPARTAMENTOS={get(row, idx, COL_DEPARTAMENTOS)!r} | "
            f"BP AUTORITY={get(row, idx, COL_BP_AUTORITY)!r} | "
            f"D.*={', '.join(departamentos_marcados)}"
        )

    print("\nDEPARTAMENTOS TRUE SEM NENHUM D.* TRUE")
    if not flag_geral_sem_departamento:
        print("(nenhum)")
    for linha, row in flag_geral_sem_departamento:
        print(
            f"Linha {linha}: "
            f"ID_USER={get(row, idx, COL_ID_USER)!r} | "
            f"Nome={get(row, idx, COL_NOME)!r} | "
            f"INATIVO={get(row, idx, COL_INATIVO)!r} | "
            f"DEPARTAMENTOS={get(row, idx, COL_DEPARTAMENTOS)!r} | "
            f"BP AUTORITY={get(row, idx, COL_BP_AUTORITY)!r} | "
            "Acao prevista=limpar DEPARTAMENTOS e BP AUTORITY"
        )

    print("\nBP AUTORITY PREENCHIDO SEM NENHUM D.* TRUE")
    if not bp_autority_sem_departamento:
        print("(nenhum)")
    for linha, row in bp_autority_sem_departamento:
        print(
            f"Linha {linha}: "
            f"ID_USER={get(row, idx, COL_ID_USER)!r} | "
            f"Nome={get(row, idx, COL_NOME)!r} | "
            f"INATIVO={get(row, idx, COL_INATIVO)!r} | "
            f"DEPARTAMENTOS={get(row, idx, COL_DEPARTAMENTOS)!r} | "
            f"BP AUTORITY={get(row, idx, COL_BP_AUTORITY)!r} | "
            "Acao prevista=limpar BP AUTORITY"
        )


if __name__ == "__main__":
    main()
