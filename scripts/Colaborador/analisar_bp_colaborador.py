"""Analisa BP COLABORADOR contra BP SERVICE.

Read-only. A sheet BP COLABORADOR parece ser uma matriz de departamentos
FUNC_*; este script mostra amostras, contagens e divergencias provaveis contra
as colunas D.* da BP SERVICE.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_COLABORADOR = "BP COLABORADOR"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_INATIVO = "INATIVO"
COL_DEPARTAMENTOS = "DEPARTAMENTOS"
COL_TYPE = "TYPE"


def map_headers(header: list[str]) -> dict[str, int]:
    return {str(value).strip(): i for i, value in enumerate(header) if str(value).strip()}


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


def normalize_token(value: object) -> str:
    text = normalize_text(value)
    return re.sub(r"[^A-Z0-9]+", "", text)


def is_true(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"


def token_departamento_service(header: str) -> str:
    name = str(header or "").strip()
    if name.upper().startswith("D."):
        name = name[2:].strip()
    return normalize_token(name)


def token_departamento_colaborador(header: str) -> str:
    name = str(header or "").strip()
    if name.upper().startswith("FUNC_"):
        name = name[len("FUNC_") :]
    return normalize_token(name)


def main() -> None:
    guard = SpreadsheetGuard(load_settings())
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_colaborador = guard.read_worksheet(SHEET_BP_COLABORADOR)

    idx_service = map_headers(bp_service[0])
    header_colaborador = bp_colaborador[0] if bp_colaborador else []

    d_cols = [
        col
        for col in bp_service[0]
        if str(col).strip().upper().startswith("D.")
    ]
    func_cols = [str(col).strip() for col in header_colaborador if str(col).strip()]

    service_by_dept: dict[str, list[tuple[str, str]]] = defaultdict(list)
    service_ignorados_type = 0
    for row in bp_service[1:]:
        if is_true(get(row, idx_service, COL_INATIVO)):
            continue
        if get(row, idx_service, COL_TYPE):
            service_ignorados_type += 1
            continue
        id_user = get(row, idx_service, COL_ID_USER)
        nome = get(row, idx_service, COL_NOME)
        if not id_user or not nome:
            continue
        for col in d_cols:
            if is_true(get(row, idx_service, col)):
                service_by_dept[token_departamento_service(col)].append((id_user, nome))

    colaborador_by_dept: dict[str, list[str]] = defaultdict(list)
    for row in bp_colaborador[1:]:
        for idx, col in enumerate(func_cols):
            value = row[idx].strip() if idx < len(row) else ""
            if value:
                colaborador_by_dept[token_departamento_colaborador(col)].append(value)

    print("###############################################################################")
    print("[BP COLABORADOR] ANALISE READ-ONLY")
    print(f"Linhas BP SERVICE: {max(len(bp_service) - 1, 0)}")
    print(f"BP SERVICE ativos ignorados por TYPE preenchido: {service_ignorados_type}")
    print(f"Linhas BP COLABORADOR: {max(len(bp_colaborador) - 1, 0)}")
    print(f"Colunas D.* em BP SERVICE: {len(d_cols)}")
    print(f"Colunas FUNC_* em BP COLABORADOR: {len(func_cols)}")
    print("###############################################################################")

    print("\nMAPEAMENTO PROVAVEL")
    for func in func_cols:
        token = token_departamento_colaborador(func)
        service_match = [col for col in d_cols if token_departamento_service(col) == token]
        status = service_match[0] if service_match else "(sem D.* correspondente)"
        print(f"{func} -> {status}")

    print("\nAMOSTRA BP COLABORADOR")
    for func in func_cols:
        valores = colaborador_by_dept[token_departamento_colaborador(func)]
        amostra = ", ".join(repr(v) for v in valores[:8])
        print(f"{func}: total={len(valores)} | {amostra or '(vazio)'}")

    print("\nCOMPARACAO POR DEPARTAMENTO")
    all_tokens = sorted(set(service_by_dept) | set(colaborador_by_dept))
    for token in all_tokens:
        service_values = service_by_dept.get(token, [])
        col_values = colaborador_by_dept.get(token, [])
        func_names = [col for col in func_cols if token_departamento_colaborador(col) == token]
        service_names = [col for col in d_cols if token_departamento_service(col) == token]
        print(
            f"{token}: BP SERVICE={len(service_values)} | BP COLABORADOR={len(col_values)} "
            f"| D.*={service_names or ['(nenhum)']} | FUNC={func_names or ['(nenhum)']}"
        )

    print("\nDIVERGENCIAS POR COLUNA FUNC_*")
    for func in func_cols:
        token = token_departamento_colaborador(func)
        expected_names = [nome for _, nome in service_by_dept.get(token, [])]
        current_names = colaborador_by_dept.get(token, [])
        expected_keys = {normalize_text(nome): nome for nome in expected_names}
        current_keys = {normalize_text(nome): nome for nome in current_names}
        missing = [expected_keys[key] for key in sorted(set(expected_keys) - set(current_keys))]
        extra = [current_keys[key] for key in sorted(set(current_keys) - set(expected_keys))]
        if not missing and not extra:
            continue
        print(f"\n{func}")
        print(f"  Esperado BP SERVICE: {len(expected_names)} | Atual BP COLABORADOR: {len(current_names)}")
        print(f"  Em falta: {', '.join(repr(v) for v in missing) or '(nenhum)'}")
        print(f"  A mais: {', '.join(repr(v) for v in extra) or '(nenhum)'}")

    print("\nPRIMEIRAS LINHAS BP COLABORADOR")
    for line, row in enumerate(bp_colaborador[:12], start=1):
        print(f"Linha {line}: {row}")


if __name__ == "__main__":
    main()
