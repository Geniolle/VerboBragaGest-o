"""Reconcilia flags agregadas de Manager e Coordenador em BP AUTORITY.

Por padrao roda em dry-run. Com ``--aplicar``, garante estas equivalencias:

- algum ``MANAGER_* = TRUE`` <=> ``DEPARTAMENTOS_MANAGER = TRUE``;
- algum ``COORDENADOR_* = TRUE`` <=> ``DEPARTAMENTOS_COORDENADOR = TRUE``.

Quando nenhum vinculo do respetivo papel esta ativo, a flag agregada fica
vazia. Toda escrita passa pelo SpreadsheetGuard.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_AUTORITY = "BP AUTORITY"
COL_ID_USER = "ID_USER"
COL_NOME = "NOME"


@dataclass(frozen=True)
class RegraPapel:
    prefixo: str
    coluna_agregada: str


REGRAS = (
    RegraPapel("MANAGER_", "DEPARTAMENTOS_MANAGER"),
    RegraPapel("COORDENADOR_", "DEPARTAMENTOS_COORDENADOR"),
)


@dataclass
class PlanoFlagsPapeis:
    atualizacoes: list[tuple[int, int, str]] = field(default_factory=list)
    detalhes: list[str] = field(default_factory=list)
    linhas_lidas: int = 0
    linhas_corretas: int = 0


def map_headers(header: list[str]) -> dict[str, int]:
    return {
        str(nome).strip().upper(): indice
        for indice, nome in enumerate(header)
        if str(nome).strip()
    }


def get(row: list[str], indice: int) -> str:
    if indice >= len(row):
        return ""
    return str(row[indice]).strip()


def is_true(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"


def calcular_plano(bp_autority: list[list[str]]) -> PlanoFlagsPapeis:
    if not bp_autority:
        raise RuntimeError(f'Sheet "{SHEET_BP_AUTORITY}" vazia ou sem cabecalho.')

    header = [str(col).strip() for col in bp_autority[0]]
    idx = map_headers(header)
    faltando = [regra.coluna_agregada for regra in REGRAS if regra.coluna_agregada not in idx]
    if faltando:
        raise RuntimeError(
            f'{SHEET_BP_AUTORITY} sem coluna(s) obrigatoria(s): {", ".join(faltando)}'
        )

    colunas_por_regra = {
        regra: [
            indice
            for indice, nome in enumerate(header)
            if nome.upper().startswith(regra.prefixo)
        ]
        for regra in REGRAS
    }

    plano = PlanoFlagsPapeis()
    for linha, row in enumerate(bp_autority[1:], start=2):
        plano.linhas_lidas += 1
        linha_tem_delta = False
        id_user = get(row, idx[COL_ID_USER]) if COL_ID_USER in idx else ""
        nome = get(row, idx[COL_NOME]) if COL_NOME in idx else ""

        for regra in REGRAS:
            tem_papel = any(is_true(get(row, indice)) for indice in colunas_por_regra[regra])
            valor_esperado = "TRUE" if tem_papel else ""
            indice_agregado = idx[regra.coluna_agregada]
            valor_atual = get(row, indice_agregado)
            esta_correto = is_true(valor_atual) if tem_papel else not valor_atual
            if esta_correto:
                continue

            linha_tem_delta = True
            plano.atualizacoes.append((linha, indice_agregado + 1, valor_esperado))
            plano.detalhes.append(
                f"Linha={linha} | ID_USER={id_user!r} | Nome={nome!r} | "
                f"{regra.coluna_agregada}: {valor_atual!r} -> {valor_esperado!r}"
            )

        if not linha_tem_delta:
            plano.linhas_corretas += 1

    return plano


def imprimir_plano(plano: PlanoFlagsPapeis, aplicar: bool) -> None:
    print("###############################################################################")
    print("[BP AUTORITY] RECONCILIAR FLAGS DE MANAGER/COORDENADOR")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}")
    print(f"Linhas lidas: {plano.linhas_lidas}")
    print(f"Linhas sem divergencias: {plano.linhas_corretas}")
    print(f"Celulas a atualizar: {len(plano.atualizacoes)}")
    print("###############################################################################")

    print("\nDIVERGENCIAS")
    if not plano.detalhes:
        print("(nenhuma)")
    for detalhe in plano.detalhes:
        print(detalhe)


def aplicar_plano(guard: SpreadsheetGuard, plano: PlanoFlagsPapeis) -> None:
    if plano.atualizacoes:
        guard.batch_update_cells(SHEET_BP_AUTORITY, plano.atualizacoes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Aplica as correcoes em BP AUTORITY.")
    # O cockpit envia esta opcao a todas as etapas. Esta leitura deve ser fresca,
    # pois etapas anteriores podem ter acabado de alterar BP AUTORITY.
    parser.add_argument("--use-cache", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    writable = {SHEET_BP_AUTORITY} if args.aplicar else set()
    guard = SpreadsheetGuard(load_settings(), writable_original_titles=writable)
    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY, force_refresh=True)
    plano = calcular_plano(bp_autority)
    imprimir_plano(plano, args.aplicar)

    if args.aplicar:
        aplicar_plano(guard, plano)
        print("\nAplicacao concluida.")
    else:
        print("\nDry-run: nenhuma sheet foi alterada.")


if __name__ == "__main__":
    main()
