"""Audita ID_USER em BP ALGORITIMO contra BP SERVICE.

BP SERVICE e o cadastro mestre do ID_USER. Este script e read-only e lista
qualquer linha de BP ALGORITIMO cujo NOME exista de forma inequivoca em
BP SERVICE, mas cujo ID_USER esteja diferente.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_ALGORITIMO = "BP ALGORITIMO"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_DEPARTAMENTO = "DEPARTAMENTO"
COL_ATIVO = "ATIVO"
COL_INATIVO = "INATIVO"
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


def is_true(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO)

    idx_service = map_headers(bp_service[0])
    idx_algoritimo = map_headers(bp_algoritimo[0])

    service_by_name: dict[str, list[tuple[int, list[str]]]] = defaultdict(list)
    for line, row in enumerate(bp_service[1:], start=2):
        nome_key = normalize_text(get(row, idx_service, COL_NOME))
        if not nome_key:
            continue
        service_by_name[nome_key].append((line, row))

    divergentes: list[tuple[int, str, str, str, str, str, int]] = []
    ambiguos: list[tuple[int, str, str, int]] = []
    sem_service: list[tuple[int, str, str]] = []

    for line, row in enumerate(bp_algoritimo[1:], start=2):
        nome = get(row, idx_algoritimo, COL_NOME)
        nome_key = normalize_text(nome)
        if not nome_key:
            continue
        candidatos = service_by_name.get(nome_key, [])
        if not candidatos:
            sem_service.append((line, get(row, idx_algoritimo, COL_ID_USER), nome))
            continue
        if len(candidatos) > 1:
            ambiguos.append((line, get(row, idx_algoritimo, COL_ID_USER), nome, len(candidatos)))
            continue
        service_line, service_row = candidatos[0]
        service_id = get(service_row, idx_service, COL_ID_USER)
        algoritmo_id = get(row, idx_algoritimo, COL_ID_USER)
        if service_id != algoritmo_id:
            divergentes.append(
                (
                    line,
                    nome,
                    get(row, idx_algoritimo, COL_DEPARTAMENTO),
                    get(row, idx_algoritimo, COL_ATIVO),
                    algoritmo_id,
                    service_id,
                    service_line,
                )
            )

    print("###############################################################################")
    print("[BP ALGORITIMO] AUDITORIA ID_USER CONTRA BP SERVICE")
    print(f"Linhas BP ALGORITIMO lidas: {max(len(bp_algoritimo) - 1, 0)}")
    print(f"ID_USER divergente: {len(divergentes)}")
    print(f"Nome ambiguo em BP SERVICE: {len(ambiguos)}")
    print(f"Sem nome correspondente em BP SERVICE: {len(sem_service)}")
    print("###############################################################################")

    print("\nID_USER DIVERGENTE")
    if not divergentes:
        print("(nenhum)")
    for line, nome, departamento, ativo, algoritmo_id, service_id, service_line in divergentes:
        print(
            "Linha BP ALGORITIMO="
            f"{line} | Nome={nome!r} | Departamento={departamento!r} | ATIVO={ativo!r} "
            f"| BP ALGORITIMO.ID_USER={algoritmo_id!r} -> BP SERVICE.ID_USER={service_id!r} "
            f"| Linha BP SERVICE={service_line}"
        )

    print("\nNOME AMBIGUO EM BP SERVICE")
    if not ambiguos:
        print("(nenhum)")
    for line, algoritmo_id, nome, total in ambiguos:
        print(f"Linha BP ALGORITIMO={line} | ID_USER={algoritmo_id!r} | Nome={nome!r} | Ocorrencias BP SERVICE={total}")

    print("\nSEM NOME CORRESPONDENTE EM BP SERVICE")
    if not sem_service:
        print("(nenhum)")
    for line, algoritmo_id, nome in sem_service:
        print(f"Linha BP ALGORITIMO={line} | ID_USER={algoritmo_id!r} | Nome={nome!r}")


if __name__ == "__main__":
    main()
