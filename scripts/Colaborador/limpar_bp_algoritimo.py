"""Limpar BP ALGORITIMO de linhas obsoletas.

Remove resíduos que não correspondem mais a vínculos activos em BP AUTORITY:
- Linhas com ATIVO=FALSE
- Vínculos para pessoas sem correspondência em BP AUTORITY
- Duplicados (mesmo ID_USER + DEPARTAMENTO)

Por padrão roda em dry-run. Use --aplicar para remover linhas.

Este script APENAS REMOVE (delta de eliminação), nunca reescreve.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
try:
    from scripts.Colaborador.sincronizar_bp_autority_bp_algoritimo import (
        token_colaborador_authority,
        token_departamento,
    )
except ModuleNotFoundError:  # Execucao direta: sys.path aponta para scripts/Colaborador.
    from sincronizar_bp_autority_bp_algoritimo import (  # type: ignore[no-redef]
        token_colaborador_authority,
        token_departamento,
    )

SHEET_BP_ALGORITIMO = "BP ALGORITIMO"
SHEET_BP_AUTORITY = "BP AUTORITY"
SHEET_BP_SERVICE = "BP SERVICE"


@dataclass
class PlanoLimpezaAlgoritimo:
    remover_ativo_false: list[int] = field(default_factory=list)
    remover_sem_autority: list[int] = field(default_factory=list)
    remover_duplicados: list[int] = field(default_factory=list)
    linhas_ok: int = 0
    linhas_processadas: int = 0


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


def calcular_plano(bp_algoritimo: list[list[str]], bp_autority: list[list[str]]) -> PlanoLimpezaAlgoritimo:
    """Calcula plano de limpeza de BP ALGORITIMO."""

    plano = PlanoLimpezaAlgoritimo()

    if not bp_algoritimo or not bp_autority:
        return plano

    idx_alg = map_headers(bp_algoritimo[0])
    idx_auth = map_headers(bp_autority[0])

    # Construir mapa de vínculos activos em BP AUTORITY
    autority_vinculos = set()  # (id_user, departamento_token)

    for row_auth in bp_autority[1:]:
        id_user = get(row_auth, idx_auth, "ID_USER")
        if not id_user:
            continue

        for col in bp_autority[0]:
            col_str = str(col).strip()
            if col_str.upper().startswith("COLABORADOR_"):
                if is_true(get(row_auth, idx_auth, col_str)):
                    dept_token = token_colaborador_authority(col_str)
                    autority_vinculos.add((id_user, dept_token))

    # Auditar BP ALGORITIMO
    visto = set()  # Para detectar duplicados

    for linha, row_alg in enumerate(bp_algoritimo[1:], start=2):
        plano.linhas_processadas += 1

        id_user = get(row_alg, idx_alg, "ID_USER")
        departamento = get(row_alg, idx_alg, "DEPARTAMENTO")
        ativo = get(row_alg, idx_alg, "ATIVO")

        # Critério 1: ATIVO=FALSE ou vazio
        if ativo and not is_true(ativo):
            plano.remover_ativo_false.append(linha)
            continue

        # Critério 2: Vínculo não existe em BP AUTORITY
        if id_user:
            dept_token = token_departamento(departamento)
            if (id_user, dept_token) not in autority_vinculos:
                plano.remover_sem_autority.append(linha)
                continue

            # Critério 3: Duplicado
            chave = (id_user, dept_token)
            if chave in visto:
                plano.remover_duplicados.append(linha)
                continue
            visto.add(chave)

        plano.linhas_ok += 1

    return plano


def imprimir_plano(plano: PlanoLimpezaAlgoritimo, aplicar: bool) -> None:
    print("###############################################################################")
    print("[BP ALGORITIMO] LIMPAR LINHAS OBSOLETAS")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}")
    print(f"Linhas processadas: {plano.linhas_processadas}")
    print(f"Linhas OK: {plano.linhas_ok}")
    print(f"Linhas a remover (ATIVO=FALSE): {len(plano.remover_ativo_false)}")
    print(f"Linhas a remover (sem vínculo AUTORITY): {len(plano.remover_sem_autority)}")
    print(f"Linhas a remover (duplicados): {len(plano.remover_duplicados)}")
    total_remover = len(plano.remover_ativo_false) + len(plano.remover_sem_autority) + len(plano.remover_duplicados)
    print(f"TOTAL A REMOVER: {total_remover}")
    print("###############################################################################")

    if plano.remover_ativo_false:
        print("\nLINHAS COM ATIVO=FALSE A REMOVER")
        for linha in plano.remover_ativo_false[:10]:
            print(f"  Linha {linha}")
        if len(plano.remover_ativo_false) > 10:
            print(f"  ... e mais {len(plano.remover_ativo_false) - 10}")

    if plano.remover_sem_autority:
        print("\nLINHAS SEM VÍNCULO EM BP AUTORITY A REMOVER")
        for linha in plano.remover_sem_autority[:10]:
            print(f"  Linha {linha}")
        if len(plano.remover_sem_autority) > 10:
            print(f"  ... e mais {len(plano.remover_sem_autority) - 10}")

    if plano.remover_duplicados:
        print("\nDUPLICADOS A REMOVER")
        for linha in plano.remover_duplicados[:10]:
            print(f"  Linha {linha}")
        if len(plano.remover_duplicados) > 10:
            print(f"  ... e mais {len(plano.remover_duplicados) - 10}")

    if not aplicar:
        print(f"\nDry-run: nenhuma sheet foi alterada.")


def aplicar_plano(guard: SpreadsheetGuard, plano: PlanoLimpezaAlgoritimo) -> None:
    """Aplicar remoções."""

    todas_linhas = (
        plano.remover_ativo_false
        + plano.remover_sem_autority
        + plano.remover_duplicados
    )

    if not todas_linhas:
        return

    # Ordenar em ordem descendente para remover de baixo para cima
    linhas_remover = sorted(set(todas_linhas), reverse=True)

    guard.delete_rows(SHEET_BP_ALGORITIMO, linhas_remover)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Remove linhas obsoletas de BP ALGORITIMO.",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        default=True,
        help="Usar cache de sheets (padrão: True).",
    )
    args = parser.parse_args()

    # Usar cache se disponível
    if args.use_cache:
        try:
            from sheets_cache import SheetsCache
            cache = SheetsCache()
            bp_algoritimo = cache.read(SHEET_BP_ALGORITIMO)
            bp_autority = cache.read(SHEET_BP_AUTORITY)
        except (ImportError, Exception):
            # Fallback: ler direto se cache falhar
            settings = load_settings()
            writable = {SHEET_BP_ALGORITIMO} if args.aplicar else set()
            guard = SpreadsheetGuard(settings, writable_original_titles=writable)
            bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO)
            bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)
    else:
        settings = load_settings()
        writable = {SHEET_BP_ALGORITIMO} if args.aplicar else set()
        guard = SpreadsheetGuard(settings, writable_original_titles=writable)
        bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO)
        bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)

    # Sempre obter guard para escrita
    settings = load_settings()
    writable = {SHEET_BP_ALGORITIMO} if args.aplicar else set()
    guard = SpreadsheetGuard(settings, writable_original_titles=writable)

    plano = calcular_plano(bp_algoritimo, bp_autority)
    imprimir_plano(plano, args.aplicar)

    if args.aplicar:
        aplicar_plano(guard, plano)


if __name__ == "__main__":
    main()
