"""Valida BP SERVICE x BP AUTORITY por ID_USER e departamentos.

Processo: Atualizar BP AUTORITY.

Read-only: nao escreve em nenhuma sheet.

Regra validada:
- considerar BP SERVICE com INATIVO != true;
- considerar apenas linhas de BP SERVICE onde BP AUTORITY esta vazio;
- procurar ID_USER na sheet BP AUTORITY;
- para cada coluna D.* true em BP SERVICE, esperar uma coluna equivalente
  COLABORADOR_* true em BP AUTORITY.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_AUTORITY = "BP AUTORITY"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_INATIVO = "INATIVO"
COL_DEPARTAMENTOS = "DEPARTAMENTOS"
COL_BP_AUTORITY = "BP AUTORITY"


@dataclass(frozen=True)
class Divergencia:
    linha_service: int
    linha_autority: int | None
    id_user: str
    nome: str
    departamento_service: str
    coluna_autority_esperada: str
    valor_autority: str
    motivo: str


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


def normalize_token(value: str) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def authority_col_for_department(department_col: str) -> str:
    name = str(department_col).strip()
    if name.upper().startswith("D."):
        name = name[2:].strip()
    return f"COLABORADOR_{normalize_token(name)}"


def main() -> None:
    guard = SpreadsheetGuard(load_settings())
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)

    if not bp_service:
        raise RuntimeError(f'Sheet "{SHEET_BP_SERVICE}" vazia ou sem cabecalho.')
    if not bp_autority:
        raise RuntimeError(f'Sheet "{SHEET_BP_AUTORITY}" vazia ou sem cabecalho.')

    idx_service = map_headers(bp_service[0])
    idx_autority = map_headers(bp_autority[0])

    for col in (COL_ID_USER, COL_NOME, COL_INATIVO, COL_DEPARTAMENTOS, COL_BP_AUTORITY):
        if col not in idx_service:
            raise RuntimeError(f'Coluna "{col}" nao encontrada em "{SHEET_BP_SERVICE}".')
    if COL_ID_USER not in idx_autority:
        raise RuntimeError(f'Coluna "{COL_ID_USER}" nao encontrada em "{SHEET_BP_AUTORITY}".')

    dept_cols = [
        str(col).strip()
        for col in bp_service[0]
        if str(col).strip().upper().startswith("D.")
    ]

    authority_by_id: dict[str, tuple[int, list[str]]] = {}
    duplicate_ids: dict[str, list[int]] = {}
    for linha_autority, row in enumerate(bp_autority[1:], start=2):
        id_user = get(row, idx_autority, COL_ID_USER)
        if not id_user:
            continue
        if id_user in authority_by_id:
            duplicate_ids.setdefault(id_user, [authority_by_id[id_user][0]]).append(linha_autority)
            continue
        authority_by_id[id_user] = (linha_autority, row)

    analisadas = 0
    fora_escopo_inativo = 0
    fora_escopo_sem_departamentos = 0
    fora_escopo_bp_autority_preenchido = 0
    bp_autority_preenchido: list[tuple[int, str, str, str, list[str]]] = []
    sem_id = 0
    sem_registro_autority: list[tuple[int, str, str, str, list[str]]] = []
    divergencias: list[Divergencia] = []
    matches_ok = 0
    colunas_autority_ausentes_ignoradas: set[str] = set()
    vinculos_ignorados_por_coluna_ausente = 0

    for linha_service, row_service in enumerate(bp_service[1:], start=2):
        if is_true(get(row_service, idx_service, COL_INATIVO)):
            fora_escopo_inativo += 1
            continue

        departamentos_marcados = [
            col for col in dept_cols if is_true(get(row_service, idx_service, col))
        ]

        if not is_true(get(row_service, idx_service, COL_DEPARTAMENTOS)):
            fora_escopo_sem_departamentos += 1
            continue

        if get(row_service, idx_service, COL_BP_AUTORITY):
            fora_escopo_bp_autority_preenchido += 1
            bp_autority_preenchido.append(
                (
                    linha_service,
                    get(row_service, idx_service, COL_ID_USER),
                    get(row_service, idx_service, COL_NOME),
                    get(row_service, idx_service, COL_BP_AUTORITY),
                    departamentos_marcados,
                )
            )
            continue

        analisadas += 1
        id_user = get(row_service, idx_service, COL_ID_USER)
        nome = get(row_service, idx_service, COL_NOME)
        if not id_user:
            sem_id += 1
            continue

        authority_item = authority_by_id.get(id_user)
        if authority_item is None:
            sem_registro_autority.append((linha_service, id_user, nome, get(row_service, idx_service, COL_DEPARTAMENTOS), departamentos_marcados))
            continue

        linha_autority, row_autority = authority_item
        for dept_col in departamentos_marcados:
            expected_col = authority_col_for_department(dept_col)
            if expected_col not in idx_autority:
                colunas_autority_ausentes_ignoradas.add(expected_col)
                vinculos_ignorados_por_coluna_ausente += 1
                continue

            valor = get(row_autority, idx_autority, expected_col)
            if is_true(valor):
                matches_ok += 1
            else:
                divergencias.append(
                    Divergencia(
                        linha_service=linha_service,
                        linha_autority=linha_autority,
                        id_user=id_user,
                        nome=nome,
                        departamento_service=dept_col,
                        coluna_autority_esperada=expected_col,
                        valor_autority=valor,
                        motivo="BP SERVICE D.* true mas BP AUTORITY nao true",
                    )
                )

    print("###############################################################################")
    print("[BP AUTORITY] VALIDACAO BP SERVICE x BP AUTORITY")
    print(f"Linhas BP SERVICE fora do escopo por INATIVO=true: {fora_escopo_inativo}")
    print(f"Linhas BP SERVICE fora do escopo por DEPARTAMENTOS nao true: {fora_escopo_sem_departamentos}")
    print(f"Linhas BP SERVICE fora do escopo por BP AUTORITY preenchido: {fora_escopo_bp_autority_preenchido}")
    print(f"Linhas BP SERVICE analisadas (INATIVO!=true, DEPARTAMENTOS=true e BP AUTORITY vazio): {analisadas}")
    print(f"Linhas analisadas sem ID_USER: {sem_id}")
    print(f"ID_USER nao encontrados em BP AUTORITY: {len(sem_registro_autority)}")
    print(f"IDs duplicados em BP AUTORITY: {len(duplicate_ids)}")
    print(f"Vinculos departamento OK: {matches_ok}")
    print(f"Vinculos ignorados por coluna ausente em BP AUTORITY: {vinculos_ignorados_por_coluna_ausente}")
    print(f"Divergencias: {len(divergencias)}")
    print("###############################################################################")

    print("\nID_USER NAO ENCONTRADOS EM BP AUTORITY")
    if not sem_registro_autority:
        print("(nenhum)")
    for linha, id_user, nome, departamentos, dept_cols_marcadas in sem_registro_autority:
        print(
            f"Linha BP SERVICE {linha}: ID_USER={id_user!r} | Nome={nome!r} | "
            f"DEPARTAMENTOS={departamentos!r} | D.*={', '.join(dept_cols_marcadas) or '(nenhum)'}"
        )

    print("\nFORA DO ESCOPO POR BP AUTORITY PREENCHIDO")
    if not bp_autority_preenchido:
        print("(nenhum)")
    for linha, id_user, nome, bp_autority, dept_cols_marcadas in bp_autority_preenchido:
        print(
            f"Linha BP SERVICE {linha}: ID_USER={id_user!r} | Nome={nome!r} | "
            f"BP AUTORITY={bp_autority!r} | D.*={', '.join(dept_cols_marcadas) or '(nenhum)'}"
        )

    print("\nIDS DUPLICADOS EM BP AUTORITY")
    if not duplicate_ids:
        print("(nenhum)")
    for id_user, linhas in duplicate_ids.items():
        print(f"ID_USER={id_user!r} | Linhas BP AUTORITY={', '.join(str(l) for l in linhas)}")

    print("\nCOLUNAS AUSENTES EM BP AUTORITY (IGNORADAS)")
    if not colunas_autority_ausentes_ignoradas:
        print("(nenhum)")
    for col in sorted(colunas_autority_ausentes_ignoradas):
        print(col)

    print("\nDIVERGENCIAS")
    if not divergencias:
        print("(nenhuma)")
    for div in divergencias:
        print(
            f"Linha BP SERVICE={div.linha_service} | "
            f"Linha BP AUTORITY={div.linha_autority or '(nao encontrada)'} | "
            f"ID_USER={div.id_user!r} | "
            f"Nome={div.nome!r} | "
            f"{div.departamento_service}=true -> "
            f"{div.coluna_autority_esperada} deveria ser true | "
            f"Valor atual={div.valor_autority!r} | "
            f"Motivo={div.motivo}"
        )


if __name__ == "__main__":
    main()
