"""Remove lixo de BP AUTORITY usando BP SERVICE como fonte da verdade.

Subprocesso: Reconciliar BP AUTORITY.

Por padrao roda em dry-run. Com --aplicar:
- limpa COLABORADOR_* em BP AUTORITY quando o departamento correspondente
  nao esta mais marcado em BP SERVICE;
- limpa todos os COLABORADOR_* quando o ID_USER nao existe mais em BP SERVICE,
  esta INATIVO=true, ou nao tem DEPARTAMENTOS=true;
- elimina a linha de BP AUTORITY quando, depois da limpeza, nao resta nenhum
  campo de permissao preenchido;
- limpa BP SERVICE.BP AUTORITY quando a linha correspondente de BP AUTORITY
  for eliminada ou quando a pessoa esta fora do escopo por sem departamentos.

BP SERVICE e a fonte da verdade. BP AUTORITY e consequencia.
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
COL_INATIVO = "INATIVO"
COL_DEPARTAMENTOS = "DEPARTAMENTOS"
COL_BP_AUTORITY = "BP AUTORITY"

IDENTITY_COLS = {
    "ID_USER",
    "NOME",
    "TELEFONE",
    "EMAIL",
    "FOTO DO PERFIL",
    "USEREMAIL",
    "TIMESTAMP",
}

PERMISSION_PREFIXES = (
    "USER_ALL",
    "DEPARTAMENTOS_",
    "GERAL_DEPARTAMENTOS",
    "MANAGER_",
    "COORDENADOR_",
    "COLABORADOR_",
)


@dataclass(frozen=True)
class PessoaService:
    linha: int
    id_user: str
    nome: str
    ativa: bool
    departamentos_flag: bool
    dept_tokens: set[str]


@dataclass
class PlanoReconciliarAuthority:
    limpar_authority: list[tuple[int, int, str]] = field(default_factory=list)
    limpar_service: list[tuple[int, int, str]] = field(default_factory=list)
    eliminar_linhas_authority: list[int] = field(default_factory=list)
    detalhes_limpeza: list[str] = field(default_factory=list)
    detalhes_eliminacao: list[str] = field(default_factory=list)
    authority_linhas_lidas: int = 0
    authority_sem_id: int = 0
    authority_id_duplicado: int = 0
    sem_bp_service: int = 0
    fora_escopo_service: int = 0
    permissoes_validas: int = 0
    permissoes_invalidas: int = 0
    linhas_sem_permissao_apos_limpeza: int = 0


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
    return re.sub(r"[^A-Z0-9]+", "", text)


def token_departamento_service(department_col: str) -> str:
    name = str(department_col).strip()
    if name.upper().startswith("D."):
        name = name[2:].strip()
    return normalize_token(name)


def token_colaborador_authority(col: str) -> str:
    name = str(col).strip()
    if name.upper().startswith("COLABORADOR_"):
        name = name[len("COLABORADOR_") :]
    return normalize_token(name)


def is_permission_col(col: str) -> bool:
    upper = str(col).strip().upper()
    return any(upper == prefix or upper.startswith(prefix) for prefix in PERMISSION_PREFIXES)


def is_colaborador_col(col: str) -> bool:
    return str(col).strip().upper().startswith("COLABORADOR_")


def validar_colunas(idx: dict[str, int], colunas: tuple[str, ...], sheet: str) -> None:
    faltando = [col for col in colunas if col not in idx]
    if faltando:
        raise RuntimeError(f"{sheet} sem coluna(s): {', '.join(faltando)}")


def carregar_service(bp_service: list[list[str]]) -> tuple[dict[str, PessoaService], set[str], dict[str, int]]:
    idx = map_headers(bp_service[0])
    validar_colunas(idx, (COL_ID_USER, COL_NOME, COL_INATIVO, COL_DEPARTAMENTOS, COL_BP_AUTORITY), SHEET_BP_SERVICE)
    dept_cols = [str(col).strip() for col in bp_service[0] if str(col).strip().upper().startswith("D.")]
    por_id: dict[str, PessoaService] = {}
    duplicados: set[str] = set()

    for linha, row in enumerate(bp_service[1:], start=2):
        id_user = get(row, idx, COL_ID_USER)
        if not id_user:
            continue
        if id_user in por_id:
            duplicados.add(id_user)
            continue
        por_id[id_user] = PessoaService(
            linha=linha,
            id_user=id_user,
            nome=get(row, idx, COL_NOME),
            ativa=not is_true(get(row, idx, COL_INATIVO)),
            departamentos_flag=is_true(get(row, idx, COL_DEPARTAMENTOS)),
            dept_tokens={token_departamento_service(col) for col in dept_cols if is_true(get(row, idx, col))},
        )
    return por_id, duplicados, idx


def row_has_permissions_after(row: list[str], header: list[str], idx: dict[str, int], cleared_cols: set[str]) -> bool:
    for col in header:
        name = str(col).strip()
        if name in IDENTITY_COLS or not is_permission_col(name):
            continue
        if name in cleared_cols:
            continue
        if is_true(get(row, idx, name)) or get(row, idx, name):
            return True
    return False


def calcular_plano(bp_service: list[list[str]], bp_autority: list[list[str]]) -> PlanoReconciliarAuthority:
    if not bp_service:
        raise RuntimeError(f'Sheet "{SHEET_BP_SERVICE}" vazia ou sem cabecalho.')
    if not bp_autority:
        raise RuntimeError(f'Sheet "{SHEET_BP_AUTORITY}" vazia ou sem cabecalho.')

    service_by_id, service_duplicados, idx_service = carregar_service(bp_service)
    header_authority = [str(col).strip() for col in bp_autority[0]]
    idx_authority = map_headers(bp_autority[0])
    validar_colunas(idx_authority, (COL_ID_USER, COL_NOME), SHEET_BP_AUTORITY)

    plano = PlanoReconciliarAuthority()
    service_flag_col = idx_service[COL_BP_AUTORITY] + 1
    seen_authority_ids: set[str] = set()

    for linha_authority, row_authority in enumerate(bp_autority[1:], start=2):
        plano.authority_linhas_lidas += 1
        id_user = get(row_authority, idx_authority, COL_ID_USER)
        nome_authority = get(row_authority, idx_authority, COL_NOME)
        if not id_user:
            plano.authority_sem_id += 1
            continue
        if id_user in seen_authority_ids:
            plano.authority_id_duplicado += 1
            continue
        seen_authority_ids.add(id_user)

        pessoa = service_by_id.get(id_user)
        if pessoa is None or id_user in service_duplicados:
            plano.sem_bp_service += 1
            valid_tokens: set[str] = set()
            service_linha = None
            service_nome = ""
            motivo_base = "ID_USER nao existe em BP SERVICE" if pessoa is None else "ID_USER duplicado em BP SERVICE"
        else:
            service_linha = pessoa.linha
            service_nome = pessoa.nome
            if not pessoa.ativa or not pessoa.departamentos_flag:
                plano.fora_escopo_service += 1
                valid_tokens = set()
                motivo_base = "BP SERVICE inativo ou sem DEPARTAMENTOS=true"
            else:
                valid_tokens = pessoa.dept_tokens
                motivo_base = ""

        cols_to_clear: set[str] = set()
        for col in header_authority:
            if not is_colaborador_col(col):
                continue
            if not is_true(get(row_authority, idx_authority, col)):
                continue
            token = token_colaborador_authority(col)
            if token in valid_tokens:
                plano.permissoes_validas += 1
                continue
            plano.permissoes_invalidas += 1
            cols_to_clear.add(col)
            plano.limpar_authority.append((linha_authority, idx_authority[col] + 1, ""))
            motivo = motivo_base or f"departamento {token} nao esta marcado em BP SERVICE"
            plano.detalhes_limpeza.append(
                f"Linha BP AUTORITY={linha_authority} | ID_USER={id_user!r} | "
                f"NomeAuthority={nome_authority!r} | Linha BP SERVICE={service_linha or '(nao encontrada)'} | "
                f"NomeService={service_nome!r} | Limpar={col} | Motivo={motivo}"
            )

        if cols_to_clear and not row_has_permissions_after(row_authority, header_authority, idx_authority, cols_to_clear):
            plano.linhas_sem_permissao_apos_limpeza += 1
            plano.eliminar_linhas_authority.append(linha_authority)
            plano.detalhes_eliminacao.append(
                f"Linha BP AUTORITY={linha_authority} | ID_USER={id_user!r} | "
                f"Nome={nome_authority!r} | Motivo=sem campos de permissao apos limpeza"
            )
            if pessoa is not None and service_linha is not None:
                plano.limpar_service.append((service_linha, service_flag_col, ""))

    return plano


def imprimir_plano(plano: PlanoReconciliarAuthority, aplicar: bool) -> None:
    print("###############################################################################")
    print("[BP AUTORITY] RECONCILIAR BP AUTORITY")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}")
    print(f"Linhas BP AUTORITY lidas: {plano.authority_linhas_lidas}")
    print(f"Linhas BP AUTORITY sem ID_USER: {plano.authority_sem_id}")
    print(f"IDs duplicados em BP AUTORITY ignorados: {plano.authority_id_duplicado}")
    print(f"Linhas sem BP SERVICE correspondente: {plano.sem_bp_service}")
    print(f"Linhas com BP SERVICE inativo/sem departamentos: {plano.fora_escopo_service}")
    print(f"Permissoes COLABORADOR_* validas: {plano.permissoes_validas}")
    print(f"Permissoes COLABORADOR_* a limpar: {plano.permissoes_invalidas}")
    print(f"Linhas BP AUTORITY a eliminar: {len(plano.eliminar_linhas_authority)}")
    print(f"Flags BP SERVICE.BP AUTORITY a limpar: {len(plano.limpar_service)}")
    print("###############################################################################")

    print("\nPERMISSOES A LIMPAR")
    if not plano.detalhes_limpeza:
        print("(nenhuma)")
    for detalhe in plano.detalhes_limpeza:
        print(detalhe)

    print("\nLINHAS A ELIMINAR")
    if not plano.detalhes_eliminacao:
        print("(nenhuma)")
    for detalhe in plano.detalhes_eliminacao:
        print(detalhe)


def aplicar_plano(guard: SpreadsheetGuard, plano: PlanoReconciliarAuthority) -> None:
    linhas_eliminadas = set(plano.eliminar_linhas_authority)
    updates_authority = [upd for upd in plano.limpar_authority if upd[0] not in linhas_eliminadas]
    if updates_authority:
        guard.batch_update_cells(SHEET_BP_AUTORITY, updates_authority)
    if plano.eliminar_linhas_authority:
        guard.delete_rows(SHEET_BP_AUTORITY, plano.eliminar_linhas_authority)
    if plano.limpar_service:
        guard.batch_update_cells(SHEET_BP_SERVICE, plano.limpar_service)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Aplica limpeza em BP AUTORITY e BP SERVICE.")
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
