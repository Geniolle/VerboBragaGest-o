"""Atualiza BP AUTORITY a partir de BP SERVICE.

Subprocesso: Atualizar BP AUTORITY.

Por padrao roda em dry-run. Com --aplicar:
- atualiza colunas COLABORADOR_* existentes em BP AUTORITY para departamentos
  marcados em BP SERVICE;
- cria linha em BP AUTORITY quando ID_USER ainda nao existe;
- marca BP SERVICE.BP AUTORITY=true somente depois de preparar/validar a
  existencia do registro em BP AUTORITY.

Nunca cria colunas novas em BP AUTORITY. Departamentos sem coluna
COLABORADOR_* correspondente sao ignorados.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_AUTORITY = "BP AUTORITY"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_TELEFONE = "TELEFONE"
COL_EMAIL = "EMAIL"
COL_FOTO = "FOTO DO PERFIL"
COL_INATIVO = "INATIVO"
COL_DEPARTAMENTOS = "DEPARTAMENTOS"
COL_BP_AUTORITY = "BP AUTORITY"


@dataclass(frozen=True)
class PessoaService:
    linha: int
    row: list[str]
    id_user: str
    nome: str
    departamentos: list[str]


@dataclass(frozen=True)
class LinhaAuthority:
    linha: int
    row: list[str]


@dataclass
class PlanoAtualizarAuthority:
    criar: list[list[str]] = field(default_factory=list)
    criar_origem: list[PessoaService] = field(default_factory=list)
    atualizacoes_authority: list[tuple[int, int, str]] = field(default_factory=list)
    atualizacoes_service: list[tuple[int, int, str]] = field(default_factory=list)
    ignorados_coluna_ausente: list[tuple[PessoaService, str, str]] = field(default_factory=list)
    ignorados_id_duplicado: list[PessoaService] = field(default_factory=list)
    fora_escopo_inativo: int = 0
    fora_escopo_sem_departamentos: int = 0
    fora_escopo_bp_autority_preenchido: int = 0
    sem_id: int = 0
    analisados: int = 0
    existentes: int = 0
    novos: int = 0
    vinculos_ok: int = 0
    vinculos_a_atualizar: int = 0


def map_headers(header: list[str]) -> dict[str, int]:
    return {str(nome).strip(): i for i, nome in enumerate(header) if str(nome).strip()}


def get(row: list[str], idx: dict[str, int], col: str) -> str:
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def set_value(row: list[str], idx: dict[str, int], col: str, value: object) -> None:
    i = idx.get(col)
    if i is not None and i < len(row):
        row[i] = value


def is_true(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"


def normalize_token(value: str) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^A-Z0-9]+", "", text)


def token_departamento_service(department_col: str) -> str:
    name = str(department_col).strip()
    if name.upper().startswith("D."):
        name = name[2:].strip()
    return normalize_token(name)


def build_colaborador_authority_map(header: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for col in header:
        name = str(col).strip()
        upper = name.upper()
        if not upper.startswith("COLABORADOR_"):
            continue
        token = normalize_token(name[len("COLABORADOR_") :])
        if token:
            result[token] = name
    return result


def validar_colunas(idx: dict[str, int], colunas: tuple[str, ...], sheet: str) -> None:
    faltando = [col for col in colunas if col not in idx]
    if faltando:
        raise RuntimeError(f"{sheet} sem coluna(s): {', '.join(faltando)}")


def indexar_authority(bp_autority: list[list[str]], idx_authority: dict[str, int]) -> tuple[dict[str, LinhaAuthority], set[str]]:
    by_id: dict[str, LinhaAuthority] = {}
    duplicados: set[str] = set()
    for linha, row in enumerate(bp_autority[1:], start=2):
        id_user = get(row, idx_authority, COL_ID_USER)
        if not id_user:
            continue
        if id_user in by_id:
            duplicados.add(id_user)
            continue
        by_id[id_user] = LinhaAuthority(linha=linha, row=row)
    return by_id, duplicados


def montar_linha_authority(
    pessoa: PessoaService,
    header_authority: list[str],
    idx_service: dict[str, int],
    idx_authority: dict[str, int],
    authority_cols_por_dept: dict[str, str],
    plano: PlanoAtualizarAuthority,
) -> list[str]:
    row = [""] * len(header_authority)
    set_value(row, idx_authority, COL_ID_USER, pessoa.id_user)
    set_value(row, idx_authority, COL_NOME, get(pessoa.row, idx_service, COL_NOME))
    set_value(row, idx_authority, COL_TELEFONE, get(pessoa.row, idx_service, COL_TELEFONE))
    set_value(row, idx_authority, COL_EMAIL, get(pessoa.row, idx_service, COL_EMAIL))
    set_value(row, idx_authority, COL_FOTO, get(pessoa.row, idx_service, COL_FOTO))

    for dept_col in pessoa.departamentos:
        token = token_departamento_service(dept_col)
        authority_col = authority_cols_por_dept.get(token)
        if not authority_col:
            plano.ignorados_coluna_ausente.append((pessoa, dept_col, f"COLABORADOR_{token}"))
            continue
        set_value(row, idx_authority, authority_col, "TRUE")
        plano.vinculos_a_atualizar += 1

    return row


def calcular_plano(bp_service: list[list[str]], bp_autority: list[list[str]]) -> PlanoAtualizarAuthority:
    if not bp_service:
        raise RuntimeError(f'Sheet "{SHEET_BP_SERVICE}" vazia ou sem cabecalho.')
    if not bp_autority:
        raise RuntimeError(f'Sheet "{SHEET_BP_AUTORITY}" vazia ou sem cabecalho.')

    header_service = bp_service[0]
    header_authority = bp_autority[0]
    idx_service = map_headers(header_service)
    idx_authority = map_headers(header_authority)

    validar_colunas(
        idx_service,
        (COL_ID_USER, COL_NOME, COL_TELEFONE, COL_EMAIL, COL_INATIVO, COL_DEPARTAMENTOS, COL_BP_AUTORITY),
        SHEET_BP_SERVICE,
    )
    validar_colunas(idx_authority, (COL_ID_USER, COL_NOME, COL_TELEFONE, COL_EMAIL), SHEET_BP_AUTORITY)

    dept_cols = [str(col).strip() for col in header_service if str(col).strip().upper().startswith("D.")]
    authority_cols_por_dept = build_colaborador_authority_map(header_authority)
    authority_by_id, duplicate_ids = indexar_authority(bp_autority, idx_authority)

    plano = PlanoAtualizarAuthority()
    flag_col = idx_service[COL_BP_AUTORITY] + 1

    for linha_service, row_service in enumerate(bp_service[1:], start=2):
        if is_true(get(row_service, idx_service, COL_INATIVO)):
            plano.fora_escopo_inativo += 1
            continue
        if not is_true(get(row_service, idx_service, COL_DEPARTAMENTOS)):
            plano.fora_escopo_sem_departamentos += 1
            continue
        if get(row_service, idx_service, COL_BP_AUTORITY):
            plano.fora_escopo_bp_autority_preenchido += 1
            continue

        id_user = get(row_service, idx_service, COL_ID_USER)
        if not id_user:
            plano.sem_id += 1
            continue

        departamentos = [col for col in dept_cols if is_true(get(row_service, idx_service, col))]
        pessoa = PessoaService(
            linha=linha_service,
            row=row_service,
            id_user=id_user,
            nome=get(row_service, idx_service, COL_NOME),
            departamentos=departamentos,
        )
        plano.analisados += 1

        if id_user in duplicate_ids:
            plano.ignorados_id_duplicado.append(pessoa)
            continue

        authority = authority_by_id.get(id_user)
        if authority is None:
            plano.novos += 1
            plano.criar.append(
                montar_linha_authority(
                    pessoa,
                    header_authority,
                    idx_service,
                    idx_authority,
                    authority_cols_por_dept,
                    plano,
                )
            )
            plano.criar_origem.append(pessoa)
            plano.atualizacoes_service.append((linha_service, flag_col, "TRUE"))
            continue

        plano.existentes += 1
        for dept_col in departamentos:
            token = token_departamento_service(dept_col)
            authority_col = authority_cols_por_dept.get(token)
            if not authority_col:
                plano.ignorados_coluna_ausente.append((pessoa, dept_col, f"COLABORADOR_{token}"))
                continue
            col_authority = idx_authority[authority_col] + 1
            valor_atual = get(authority.row, idx_authority, authority_col)
            if is_true(valor_atual):
                plano.vinculos_ok += 1
            else:
                plano.vinculos_a_atualizar += 1
                plano.atualizacoes_authority.append((authority.linha, col_authority, "TRUE"))

        plano.atualizacoes_service.append((linha_service, flag_col, "TRUE"))

    return plano


def imprimir_plano(plano: PlanoAtualizarAuthority, aplicar: bool) -> None:
    print("###############################################################################")
    print("[BP AUTORITY] ATUALIZAR BP AUTORITY")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}")
    print(f"Fora do escopo por INATIVO=true: {plano.fora_escopo_inativo}")
    print(f"Fora do escopo por DEPARTAMENTOS nao true: {plano.fora_escopo_sem_departamentos}")
    print(f"Fora do escopo por BP AUTORITY preenchido: {plano.fora_escopo_bp_autority_preenchido}")
    print(f"Linhas analisadas: {plano.analisados}")
    print(f"Registros existentes em BP AUTORITY: {plano.existentes}")
    print(f"Registros a criar em BP AUTORITY: {plano.novos}")
    print(f"Vinculos ja OK: {plano.vinculos_ok}")
    print(f"Vinculos a marcar TRUE em BP AUTORITY: {plano.vinculos_a_atualizar}")
    print(f"Flags BP SERVICE.BP AUTORITY a marcar TRUE: {len(plano.atualizacoes_service)}")
    print(f"Vinculos ignorados por coluna ausente: {len(plano.ignorados_coluna_ausente)}")
    print(f"Linhas ignoradas por ID_USER duplicado em BP AUTORITY: {len(plano.ignorados_id_duplicado)}")
    print(f"Linhas sem ID_USER: {plano.sem_id}")
    print("###############################################################################")

    print("\nREGISTROS A CRIAR EM BP AUTORITY")
    if not plano.criar_origem:
        print("(nenhum)")
    for pessoa in plano.criar_origem:
        print(f"Linha BP SERVICE={pessoa.linha} | ID_USER={pessoa.id_user!r} | Nome={pessoa.nome!r}")

    print("\nVINCULOS IGNORADOS POR COLUNA AUSENTE")
    if not plano.ignorados_coluna_ausente:
        print("(nenhum)")
    for pessoa, dept_col, expected in plano.ignorados_coluna_ausente:
        print(
            f"Linha BP SERVICE={pessoa.linha} | ID_USER={pessoa.id_user!r} | "
            f"Nome={pessoa.nome!r} | {dept_col}=true | Coluna ausente ignorada={expected}"
        )

    print("\nID_USER DUPLICADO EM BP AUTORITY")
    if not plano.ignorados_id_duplicado:
        print("(nenhum)")
    for pessoa in plano.ignorados_id_duplicado:
        print(f"Linha BP SERVICE={pessoa.linha} | ID_USER={pessoa.id_user!r} | Nome={pessoa.nome!r}")


def validar_criacao(guard: SpreadsheetGuard, ids_criados: set[str]) -> None:
    if not ids_criados:
        return
    valores = guard.read_worksheet(SHEET_BP_AUTORITY)
    idx = map_headers(valores[0] if valores else [])
    if COL_ID_USER not in idx:
        raise RuntimeError(f'Coluna "{COL_ID_USER}" nao encontrada em "{SHEET_BP_AUTORITY}" apos gravacao.')
    ids_existentes = {get(row, idx, COL_ID_USER) for row in valores[1:]}
    faltando = sorted(id_user for id_user in ids_criados if id_user not in ids_existentes)
    if faltando:
        raise RuntimeError("Criacao em BP AUTORITY nao validada para ID_USER: " + ", ".join(faltando))


def aplicar_plano(guard: SpreadsheetGuard, plano: PlanoAtualizarAuthority) -> None:
    if plano.atualizacoes_authority:
        guard.batch_update_cells(SHEET_BP_AUTORITY, plano.atualizacoes_authority)

    if plano.criar:
        guard.append_rows(SHEET_BP_AUTORITY, plano.criar)
        validar_criacao(guard, {p.id_user for p in plano.criar_origem})

    if plano.atualizacoes_service:
        guard.batch_update_cells(SHEET_BP_SERVICE, plano.atualizacoes_service)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Aplica atualizacoes em BP AUTORITY e BP SERVICE.")
    args = parser.parse_args()

    settings = load_settings()
    writable = {SHEET_BP_AUTORITY, SHEET_BP_SERVICE} if args.aplicar else set()
    guard = SpreadsheetGuard(settings, writable_original_titles=writable)

    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)
    plano = calcular_plano(bp_service, bp_autority)
    imprimir_plano(plano, args.aplicar)

    if args.aplicar:
        aplicar_plano(guard, plano)
        print("\nAplicacao concluida.")
    else:
        print("\nDry-run: nenhuma sheet foi alterada.")


if __name__ == "__main__":
    main()
