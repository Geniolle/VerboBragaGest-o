"""Sincroniza BP AUTORITY -> BP ALGORITIMO.

Subprocesso: Atualizar BP ALGORITIMO por BP AUTORITY.

BP AUTORITY e a fonte para os vinculos pessoa+departamento de autoridade.
BP ALGORITIMO deve conter um vinculo ativo para cada COLABORADOR_* true que
tenha departamento correspondente. O reverso tambem vale: vinculo ativo em
BP ALGORITIMO, para departamento gerido pela BP AUTORITY, que nao existe na
BP AUTORITY e marcado ATIVO=FALSE.
Duplicados ativos do mesmo NOME+DEPARTAMENTO sao eliminados, mantendo apenas
uma linha principal.

Por padrao roda em dry-run. Use --aplicar para gravar em BP ALGORITIMO.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_AUTORITY = "BP AUTORITY"
SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_ALGORITIMO = "BP ALGORITIMO"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_DEPARTAMENTO = "DEPARTAMENTO"
COL_ATIVO = "ATIVO"
COL_TYPE = "TYPE"


@dataclass(frozen=True)
class VinculoAuthority:
    id_user: str
    nome: str
    departamento: str
    authority_col: str
    linha_authority: int

    @property
    def dept_token(self) -> str:
        return token_departamento(self.departamento)

    @property
    def id_key(self) -> tuple[str, str]:
        return (self.id_user, self.dept_token)

    @property
    def name_key(self) -> tuple[str, str]:
        return (normalize_text(self.nome), self.dept_token)


@dataclass(frozen=True)
class LinhaAlgoritimo:
    linha: int
    row: list[str]
    id_user: str
    nome: str
    departamento: str
    ativo: bool

    @property
    def dept_token(self) -> str:
        return token_departamento(self.departamento)

    @property
    def id_key(self) -> tuple[str, str]:
        return (self.id_user, self.dept_token)

    @property
    def name_key(self) -> tuple[str, str]:
        return (normalize_text(self.nome), self.dept_token)


@dataclass
class PlanoAuthorityAlgoritimo:
    inserir: list[VinculoAuthority] = field(default_factory=list)
    reativar: list[LinhaAlgoritimo] = field(default_factory=list)
    preencher_id_user: list[tuple[LinhaAlgoritimo, str]] = field(default_factory=list)
    desativar: list[LinhaAlgoritimo] = field(default_factory=list)
    eliminar_duplicados: list[LinhaAlgoritimo] = field(default_factory=list)
    ignorados_sem_departamento_service: list[tuple[int, str, str]] = field(default_factory=list)
    ignorados_type_preenchido: list[tuple[int, str, str, str]] = field(default_factory=list)
    ignorados_sem_bp_service: list[tuple[int, str, str]] = field(default_factory=list)
    authority_id_divergente_service: list[tuple[int, str, str, str]] = field(default_factory=list)
    ignorados_sem_id: int = 0
    vinculos_authority: int = 0
    vinculos_ja_ok: int = 0
    linhas_algoritimo_lidas: int = 0


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


def normalize_text(value: str) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text)


def normalize_token(value: str) -> str:
    text = normalize_text(value)
    return re.sub(r"[^A-Z0-9]+", "", text)


def token_departamento(value: str) -> str:
    name = str(value or "").strip()
    if name.upper().startswith("D."):
        name = name[2:].strip()
    return normalize_token(name)


def token_colaborador_authority(col: str) -> str:
    name = str(col or "").strip()
    if name.upper().startswith("COLABORADOR_"):
        name = name[len("COLABORADOR_") :]
    return normalize_token(name)


def validate_columns(idx: dict[str, int], required: tuple[str, ...], sheet: str) -> None:
    missing = [col for col in required if col not in idx]
    if missing:
        raise RuntimeError(f"{sheet} sem coluna(s): {', '.join(missing)}")


def build_department_map_from_service(bp_service: list[list[str]]) -> dict[str, str]:
    if not bp_service:
        return {}
    result: dict[str, str] = {}
    for raw_col in bp_service[0]:
        col = str(raw_col).strip()
        if col.upper().startswith("D."):
            result[token_departamento(col)] = col
    return result


def build_service_by_id(bp_service: list[list[str]]) -> dict[str, list[str]]:
    idx = map_headers(bp_service[0])
    validate_columns(idx, (COL_ID_USER, COL_NOME, COL_TYPE), SHEET_BP_SERVICE)
    result: dict[str, list[str]] = {}
    for row in bp_service[1:]:
        id_user = get(row, idx, COL_ID_USER)
        if id_user and id_user not in result:
            result[id_user] = row
    return result


def build_unique_service_id_by_name(bp_service: list[list[str]]) -> dict[str, str]:
    idx = map_headers(bp_service[0])
    validate_columns(idx, (COL_ID_USER, COL_NOME), SHEET_BP_SERVICE)
    by_name: dict[str, list[str]] = defaultdict(list)
    for row in bp_service[1:]:
        nome_key = normalize_text(get(row, idx, COL_NOME))
        id_user = get(row, idx, COL_ID_USER)
        if nome_key and id_user:
            by_name[nome_key].append(id_user)
    return {nome_key: ids[0] for nome_key, ids in by_name.items() if len(set(ids)) == 1}


def collaborator_cols(header_authority: list[str]) -> list[str]:
    return [
        str(col).strip()
        for col in header_authority
        if str(col).strip().upper().startswith("COLABORADOR_")
    ]


def carregar_vinculos_authority(
    bp_autority: list[list[str]],
    dept_por_token: dict[str, str],
    service_by_id: dict[str, list[str]],
    idx_service: dict[str, int],
    plano: PlanoAuthorityAlgoritimo,
) -> list[VinculoAuthority]:
    idx = map_headers(bp_autority[0])
    validate_columns(idx, (COL_ID_USER, COL_NOME), SHEET_BP_AUTORITY)

    vinculos: list[VinculoAuthority] = []
    for linha, row in enumerate(bp_autority[1:], start=2):
        id_user = get(row, idx, COL_ID_USER)
        nome = get(row, idx, COL_NOME)
        if not id_user:
            plano.ignorados_sem_id += 1
            continue
        service_row = service_by_id.get(id_user)
        if service_row is None:
            plano.ignorados_sem_bp_service.append((linha, id_user, nome))
            continue
        service_id_user = get(service_row, idx_service, COL_ID_USER)
        if service_id_user != id_user:
            plano.authority_id_divergente_service.append((linha, id_user, service_id_user, nome))
        type_value = get(service_row, idx_service, COL_TYPE)
        if type_value:
            plano.ignorados_type_preenchido.append((linha, id_user, nome, type_value))
            continue

        for col in collaborator_cols(bp_autority[0]):
            if not is_true(get(row, idx, col)):
                continue
            token = token_colaborador_authority(col)
            departamento = dept_por_token.get(token)
            if not departamento:
                plano.ignorados_sem_departamento_service.append((linha, id_user, col))
                continue
            vinculos.append(
                VinculoAuthority(
                    # O ID_USER do BP ALGORITIMO pertence ao cadastro mestre:
                    # BP SERVICE. Nunca e gerado por sequencia propria aqui.
                    id_user=service_id_user,
                    nome=nome,
                    departamento=departamento,
                    authority_col=col,
                    linha_authority=linha,
                )
            )

    # Desduplica por ID_USER + departamento; se houver duplicacao real na origem,
    # a primeira linha e suficiente para o plano de sincronizacao.
    result: list[VinculoAuthority] = []
    seen: set[tuple[str, str]] = set()
    for vinculo in vinculos:
        if vinculo.id_key in seen:
            continue
        seen.add(vinculo.id_key)
        result.append(vinculo)
    plano.vinculos_authority = len(result)
    return result


def carregar_linhas_algoritimo(bp_algoritimo: list[list[str]]) -> list[LinhaAlgoritimo]:
    idx = map_headers(bp_algoritimo[0])
    validate_columns(idx, (COL_ID_USER, COL_NOME, COL_DEPARTAMENTO, COL_ATIVO), SHEET_BP_ALGORITIMO)
    linhas: list[LinhaAlgoritimo] = []
    for linha, row in enumerate(bp_algoritimo[1:], start=2):
        nome = get(row, idx, COL_NOME)
        departamento = get(row, idx, COL_DEPARTAMENTO)
        if not nome or not departamento:
            continue
        linhas.append(
            LinhaAlgoritimo(
                linha=linha,
                row=row,
                id_user=get(row, idx, COL_ID_USER),
                nome=nome,
                departamento=departamento,
                ativo=is_true(get(row, idx, COL_ATIVO)),
            )
        )
    return linhas


def calcular_plano(
    bp_autority: list[list[str]],
    bp_service: list[list[str]],
    bp_algoritimo: list[list[str]],
) -> PlanoAuthorityAlgoritimo:
    if not bp_autority:
        raise RuntimeError(f'Sheet "{SHEET_BP_AUTORITY}" vazia ou sem cabecalho.')
    if not bp_service:
        raise RuntimeError(f'Sheet "{SHEET_BP_SERVICE}" vazia ou sem cabecalho.')
    if not bp_algoritimo:
        raise RuntimeError(f'Sheet "{SHEET_BP_ALGORITIMO}" vazia ou sem cabecalho.')

    plano = PlanoAuthorityAlgoritimo()
    dept_por_token = build_department_map_from_service(bp_service)
    idx_service = map_headers(bp_service[0])
    validate_columns(idx_service, (COL_ID_USER, COL_NOME, COL_TYPE), SHEET_BP_SERVICE)
    service_by_id = build_service_by_id(bp_service)
    service_id_by_name = build_unique_service_id_by_name(bp_service)
    vinculos = carregar_vinculos_authority(bp_autority, dept_por_token, service_by_id, idx_service, plano)
    linhas_algoritimo = carregar_linhas_algoritimo(bp_algoritimo)
    plano.linhas_algoritimo_lidas = len(linhas_algoritimo)

    valid_by_name = {v.name_key: v for v in vinculos}
    valid_name_keys = set(valid_by_name)

    alg_by_name: dict[tuple[str, str], list[LinhaAlgoritimo]] = {}
    managed_dept_tokens = set(dept_por_token)

    for linha in linhas_algoritimo:
        alg_by_name.setdefault(linha.name_key, []).append(linha)

    reativar_keys: set[tuple[str, str]] = set()
    desativar_keys: set[tuple[str, str]] = set()
    update_id_lines: set[int] = set()
    duplicate_lines: set[int] = set()

    def escolher_linha_principal(vinculo: VinculoAuthority, linhas: list[LinhaAlgoritimo]) -> LinhaAlgoritimo:
        for linha in linhas:
            if linha.ativo and linha.id_user == vinculo.id_user:
                return linha
        for linha in linhas:
            if linha.ativo:
                return linha
        for linha in linhas:
            if linha.id_user == vinculo.id_user:
                return linha
        return linhas[0]

    for vinculo in vinculos:
        # Regra de negocio deste subprocesso: a existencia no BP ALGORITIMO
        # e por NOME + DEPARTAMENTO. O ID_USER ajuda a preencher linhas novas
        # ou corrigir linhas existentes, mas nao pode reativar uma linha com
        # outro nome por acaso do mesmo ID antigo/sequencial. Se houver mais
        # de uma linha ativa para o mesmo NOME+DEPARTAMENTO, mantem uma linha
        # principal e elimina as duplicadas.
        existentes = alg_by_name.get(vinculo.name_key, [])
        if not existentes:
            plano.inserir.append(vinculo)
            continue

        existing = escolher_linha_principal(vinculo, existentes)

        if existing.id_user != vinculo.id_user and existing.linha not in update_id_lines:
            update_id_lines.add(existing.linha)
            plano.preencher_id_user.append((existing, vinculo.id_user))

        if existing.ativo:
            plano.vinculos_ja_ok += 1
        elif existing.name_key not in reativar_keys:
            reativar_keys.add(existing.name_key)
            plano.reativar.append(existing)

        for duplicado in existentes:
            if duplicado.linha == existing.linha:
                continue
            if duplicado.ativo and duplicado.linha not in duplicate_lines:
                duplicate_lines.add(duplicado.linha)
                plano.eliminar_duplicados.append(duplicado)

    for linha in linhas_algoritimo:
        if not linha.ativo:
            continue
        if linha.linha in duplicate_lines:
            continue
        if linha.dept_token not in managed_dept_tokens:
            continue
        if linha.name_key not in valid_name_keys and linha.name_key not in desativar_keys:
            desativar_keys.add(linha.name_key)
            plano.desativar.append(linha)

    # Regra global: BP ALGORITIMO.ID_USER pertence ao cadastro mestre BP SERVICE.
    # Mesmo linhas inativas/legadas devem carregar o mesmo ID_USER quando o nome
    # existe de forma inequivoca em BP SERVICE.
    for linha in linhas_algoritimo:
        if linha.linha in duplicate_lines or linha.linha in update_id_lines:
            continue
        service_id = service_id_by_name.get(normalize_text(linha.nome))
        if service_id and linha.id_user != service_id:
            update_id_lines.add(linha.linha)
            plano.preencher_id_user.append((linha, service_id))

    return plano


def montar_linhas_insert(header: list[str], vinculos: list[VinculoAuthority]) -> list[list[str]]:
    idx = map_headers(header)
    validate_columns(idx, (COL_ID_USER, COL_NOME, COL_DEPARTAMENTO, COL_ATIVO), SHEET_BP_ALGORITIMO)
    rows: list[list[str]] = []
    for vinculo in vinculos:
        row = [""] * len(header)
        row[idx[COL_ID_USER]] = vinculo.id_user
        row[idx[COL_NOME]] = vinculo.nome
        row[idx[COL_DEPARTAMENTO]] = vinculo.departamento
        row[idx[COL_ATIVO]] = "TRUE"
        rows.append(row)
    return rows


def imprimir_plano(plano: PlanoAuthorityAlgoritimo, aplicar: bool) -> None:
    print("###############################################################################")
    print("[BP AUTORITY -> BP ALGORITIMO] SINCRONIZACAO")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}")
    print(f"Vinculos validos em BP AUTORITY: {plano.vinculos_authority}")
    print(f"Linhas BP ALGORITIMO lidas: {plano.linhas_algoritimo_lidas}")
    print(f"Vinculos ja OK: {plano.vinculos_ja_ok}")
    print(f"Vinculos a inserir: {len(plano.inserir)}")
    print(f"Vinculos a reativar: {len(plano.reativar)}")
    print(f"ID_USER a corrigir/preencher em vinculo existente: {len(plano.preencher_id_user)}")
    print(f"Vinculos duplicados ativos a eliminar: {len(plano.eliminar_duplicados)}")
    print(f"Vinculos a desativar por nao existirem em BP AUTORITY: {len(plano.desativar)}")
    print(f"BP AUTORITY sem ID_USER ignorados: {plano.ignorados_sem_id}")
    print(f"BP AUTORITY sem BP SERVICE correspondente ignorados: {len(plano.ignorados_sem_bp_service)}")
    print(f"BP AUTORITY com ID_USER divergente do BP SERVICE: {len(plano.authority_id_divergente_service)}")
    print(f"BP AUTORITY com BP SERVICE.TYPE preenchido ignorados: {len(plano.ignorados_type_preenchido)}")
    print(f"COLABORADOR_* sem D.* correspondente em BP SERVICE ignorados: {len(plano.ignorados_sem_departamento_service)}")
    print("###############################################################################")

    print("\nINSERIR")
    if not plano.inserir:
        print("(nenhum)")
    for v in plano.inserir:
        print(f"ID_USER={v.id_user!r} | Nome={v.nome!r} | Departamento={v.departamento!r} | Origem={v.authority_col}")

    print("\nREATIVAR")
    if not plano.reativar:
        print("(nenhum)")
    for l in plano.reativar:
        print(f"Linha BP ALGORITIMO={l.linha} | ID_USER={l.id_user!r} | Nome={l.nome!r} | Departamento={l.departamento!r}")

    print("\nDESATIVAR")
    if not plano.desativar and not plano.eliminar_duplicados:
        print("(nenhum)")
    for l in plano.desativar:
        print(f"Linha BP ALGORITIMO={l.linha} | ID_USER={l.id_user!r} | Nome={l.nome!r} | Departamento={l.departamento!r} | Motivo=nao existe em BP AUTORITY")

    print("\nELIMINAR DUPLICADOS")
    if not plano.eliminar_duplicados:
        print("(nenhum)")
    for l in plano.eliminar_duplicados:
        print(f"Linha BP ALGORITIMO={l.linha} | ID_USER={l.id_user!r} | Nome={l.nome!r} | Departamento={l.departamento!r} | Motivo=duplicado ativo")

    print("\nCORRIGIR/PREENCHER ID_USER")
    if not plano.preencher_id_user:
        print("(nenhum)")
    for l, id_user in plano.preencher_id_user:
        print(f"Linha BP ALGORITIMO={l.linha} | Nome={l.nome!r} | Departamento={l.departamento!r} | ID_USER atual={l.id_user!r} -> {id_user!r}")

    print("\nIGNORADOS: COLABORADOR_* SEM D.* CORRESPONDENTE")
    if not plano.ignorados_sem_departamento_service:
        print("(nenhum)")
    for linha, id_user, col in plano.ignorados_sem_departamento_service:
        print(f"Linha BP AUTORITY={linha} | ID_USER={id_user!r} | Coluna={col}")

    print("\nIGNORADOS: BP SERVICE TYPE PREENCHIDO")
    if not plano.ignorados_type_preenchido:
        print("(nenhum)")
    for linha, id_user, nome, type_value in plano.ignorados_type_preenchido:
        print(f"Linha BP AUTORITY={linha} | ID_USER={id_user!r} | Nome={nome!r} | TYPE={type_value!r}")

    print("\nALERTA: BP AUTORITY ID_USER DIVERGENTE DO BP SERVICE")
    if not plano.authority_id_divergente_service:
        print("(nenhum)")
    for linha, id_authority, id_service, nome in plano.authority_id_divergente_service:
        print(f"Linha BP AUTORITY={linha} | Nome={nome!r} | BP AUTORITY.ID_USER={id_authority!r} | BP SERVICE.ID_USER={id_service!r}")

    print("\nIGNORADOS: SEM BP SERVICE CORRESPONDENTE")
    if not plano.ignorados_sem_bp_service:
        print("(nenhum)")
    for linha, id_user, nome in plano.ignorados_sem_bp_service:
        print(f"Linha BP AUTORITY={linha} | ID_USER={id_user!r} | Nome={nome!r}")


def aplicar_plano(guard: SpreadsheetGuard, bp_algoritimo_header: list[str], plano: PlanoAuthorityAlgoritimo) -> None:
    idx = map_headers(bp_algoritimo_header)
    updates: list[tuple[int, int, str]] = []
    col_ativo = idx[COL_ATIVO] + 1
    col_id = idx[COL_ID_USER] + 1

    updates.extend((linha.linha, col_ativo, "TRUE") for linha in plano.reativar)
    updates.extend((linha.linha, col_ativo, "FALSE") for linha in plano.desativar)
    updates.extend((linha.linha, col_id, id_user) for linha, id_user in plano.preencher_id_user)

    if updates:
        guard.batch_update_cells(SHEET_BP_ALGORITIMO, updates)
    if plano.eliminar_duplicados:
        guard.delete_rows(SHEET_BP_ALGORITIMO, [linha.linha for linha in plano.eliminar_duplicados])
    if plano.inserir:
        guard.append_rows(SHEET_BP_ALGORITIMO, montar_linhas_insert(bp_algoritimo_header, plano.inserir))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Aplica mudancas em BP ALGORITIMO.")
    args = parser.parse_args()

    settings = load_settings()
    writable = {SHEET_BP_ALGORITIMO} if args.aplicar else set()
    guard = SpreadsheetGuard(settings, writable_original_titles=writable)

    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO)
    plano = calcular_plano(bp_autority, bp_service, bp_algoritimo)
    imprimir_plano(plano, args.aplicar)

    if args.aplicar:
        aplicar_plano(guard, bp_algoritimo[0], plano)
        print("\nAplicacao concluida.")
    else:
        print("\nDry-run: nenhuma sheet foi alterada.")


if __name__ == "__main__":
    main()
