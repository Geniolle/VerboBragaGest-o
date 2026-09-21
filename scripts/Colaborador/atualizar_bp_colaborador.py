"""Sincroniza BP SERVICE -> BP COLABORADOR.

Subprocesso: Atualizar BP COLABORADOR.

BP COLABORADOR e uma matriz de nomes por coluna FUNC_*. Cada coluna FUNC_*
que tenha correspondencia em BP SERVICE.D.* deve conter os nomes ativos do
BP SERVICE marcados nesse departamento.

Por padrao roda em dry-run. Use --aplicar para gravar em BP COLABORADOR.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_COLABORADOR = "BP COLABORADOR"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_INATIVO = "INATIVO"
COL_TYPE = "TYPE"


@dataclass
class ColunaPlano:
    col_index_1based: int
    func_col: str
    service_col: str
    esperado: list[str]
    atual: list[str]
    em_falta: list[str] = field(default_factory=list)
    a_mais: list[str] = field(default_factory=list)


@dataclass
class PlanoBpColaborador:
    colunas: list[ColunaPlano] = field(default_factory=list)
    func_sem_origem: list[str] = field(default_factory=list)
    service_ignorados_type: int = 0
    service_ignorados_inativo: int = 0


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


def diff_names(esperado: list[str], atual: list[str]) -> tuple[list[str], list[str]]:
    expected_keys = {normalize_text(nome): nome for nome in esperado}
    current_keys = {normalize_text(nome): nome for nome in atual}
    em_falta = [expected_keys[key] for key in sorted(set(expected_keys) - set(current_keys))]
    a_mais = [current_keys[key] for key in sorted(set(current_keys) - set(expected_keys))]
    return em_falta, a_mais


def calcular_plano(bp_service: list[list[str]], bp_colaborador: list[list[str]]) -> PlanoBpColaborador:
    if not bp_service:
        raise RuntimeError(f'Sheet "{SHEET_BP_SERVICE}" vazia ou sem cabecalho.')
    if not bp_colaborador:
        raise RuntimeError(f'Sheet "{SHEET_BP_COLABORADOR}" vazia ou sem cabecalho.')

    idx_service = map_headers(bp_service[0])
    for col in (COL_NOME, COL_INATIVO, COL_TYPE):
        if col not in idx_service:
            raise RuntimeError(f'{SHEET_BP_SERVICE} sem coluna obrigatoria "{col}".')

    service_cols_by_token = {
        token_departamento_service(col): str(col).strip()
        for col in bp_service[0]
        if str(col).strip().upper().startswith("D.")
    }
    colaboradores_por_token: dict[str, list[str]] = {token: [] for token in service_cols_by_token}

    plano = PlanoBpColaborador()
    for row in bp_service[1:]:
        if is_true(get(row, idx_service, COL_INATIVO)):
            plano.service_ignorados_inativo += 1
            continue
        if get(row, idx_service, COL_TYPE):
            plano.service_ignorados_type += 1
            continue
        nome = get(row, idx_service, COL_NOME)
        if not nome:
            continue
        for token, service_col in service_cols_by_token.items():
            if is_true(get(row, idx_service, service_col)):
                colaboradores_por_token[token].append(nome)

    header_colaborador = [str(col).strip() for col in bp_colaborador[0]]
    for col_zero_based, func_col in enumerate(header_colaborador):
        if not func_col:
            continue
        token = token_departamento_colaborador(func_col)
        service_col = service_cols_by_token.get(token)
        if not service_col:
            plano.func_sem_origem.append(func_col)
            continue
        atual = []
        for row in bp_colaborador[1:]:
            value = row[col_zero_based].strip() if col_zero_based < len(row) else ""
            if value:
                atual.append(value)
        esperado = colaboradores_por_token.get(token, [])
        em_falta, a_mais = diff_names(esperado, atual)
        plano.colunas.append(
            ColunaPlano(
                col_index_1based=col_zero_based + 1,
                func_col=func_col,
                service_col=service_col,
                esperado=esperado,
                atual=atual,
                em_falta=em_falta,
                a_mais=a_mais,
            )
        )

    return plano


def imprimir_plano(plano: PlanoBpColaborador, aplicar: bool) -> None:
    divergentes = [col for col in plano.colunas if col.em_falta or col.a_mais]
    print("###############################################################################")
    print("[BP SERVICE -> BP COLABORADOR] SINCRONIZACAO")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}")
    print(f"Colunas FUNC_* com origem D.*: {len(plano.colunas)}")
    print(f"Colunas FUNC_* sem origem em BP SERVICE: {len(plano.func_sem_origem)}")
    print(f"Colunas divergentes: {len(divergentes)}")
    print(f"BP SERVICE ignorados por INATIVO=true: {plano.service_ignorados_inativo}")
    print(f"BP SERVICE ignorados por TYPE preenchido: {plano.service_ignorados_type}")
    print("###############################################################################")

    print("\nCOLUNAS DIVERGENTES")
    if not divergentes:
        print("(nenhuma)")
    for col in divergentes:
        print(f"\n{col.func_col} <- {col.service_col}")
        print(f"  Esperado: {len(col.esperado)} | Atual: {len(col.atual)}")
        print(f"  Em falta: {', '.join(repr(v) for v in col.em_falta) or '(nenhum)'}")
        print(f"  A mais: {', '.join(repr(v) for v in col.a_mais) or '(nenhum)'}")

    print("\nCOLUNAS SEM ORIGEM BP SERVICE")
    if not plano.func_sem_origem:
        print("(nenhuma)")
    for col in plano.func_sem_origem:
        print(f"{col} preservada")


def aplicar_plano(guard: SpreadsheetGuard, bp_colaborador: list[list[str]], plano: PlanoBpColaborador) -> None:
    max_rows = max(
        [max(len(bp_colaborador) - 1, 0)] + [len(col.esperado) for col in plano.colunas]
    )
    updates: list[tuple[int, int, str]] = []
    for col in plano.colunas:
        for offset in range(max_rows):
            value = col.esperado[offset] if offset < len(col.esperado) else ""
            updates.append((offset + 2, col.col_index_1based, value))

    guard.batch_update_cells(SHEET_BP_COLABORADOR, updates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Aplica mudancas em BP COLABORADOR.")
    args = parser.parse_args()

    settings = load_settings()
    writable = {SHEET_BP_COLABORADOR} if args.aplicar else set()
    guard = SpreadsheetGuard(settings, writable_original_titles=writable)

    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_colaborador = guard.read_worksheet(SHEET_BP_COLABORADOR)
    plano = calcular_plano(bp_service, bp_colaborador)
    imprimir_plano(plano, args.aplicar)

    if args.aplicar:
        aplicar_plano(guard, bp_colaborador, plano)
        print("\nAplicacao concluida.")
    else:
        print("\nDry-run: nenhuma sheet foi alterada.")


if __name__ == "__main__":
    main()
