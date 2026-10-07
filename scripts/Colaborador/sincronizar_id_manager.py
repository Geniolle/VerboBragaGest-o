"""Sincroniza BP AUTORITY -> ID_MANAGER.

Subprocesso: Sincronizar Managers em ID_MANAGER.

BP AUTORITY é a fonte da verdade para identificar quem atualmente é Manager
de cada departamento.

ID_MANAGER é a tabela derivada que contém a lista de Managers por departamento,
com contato (telefone, email) sincronizado a partir de BP AUTORITY.

Por padrão roda em dry-run. Use --aplicar para gravar em ID_MANAGER.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_AUTORITY = "BP AUTORITY"
SHEET_ID_MANAGER = "ID_MANAGER"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_TELEFONE = "TELEFONE"
COL_EMAIL = "EMAIL"
COL_DEPARTAMENTOS = "DEPARTAMENTOS"


@dataclass(frozen=True)
class ManagerEntry:
    """Vínculo Manager de BP AUTORITY."""
    id_user: str
    nome: str
    telefone: str
    email: str
    departamento: str
    manager_col: str
    linha_authority: int

    @property
    def dept_token(self) -> str:
        token = self.departamento.replace("D.", "").strip().upper()
        token = re.sub(r"[​-‍﻿]", "", token)
        token = unicodedata.normalize("NFD", token)
        token = "".join(ch for ch in token if unicodedata.category(ch) != "Mn")
        token = re.sub(r"[^A-Z0-9]+", "", token)
        return token

    @property
    def idempotency_key(self) -> tuple[str, str]:
        """Chave de idempotência: departamento normalizado + nome normalizado."""
        dept_norm = self.dept_token
        nome_norm = normalize_text(self.nome)
        return (dept_norm, nome_norm)


@dataclass
class PlanoSincronizacaoIdManager:
    criar: list[ManagerEntry] = field(default_factory=list)
    atualizar: list[tuple[int, ManagerEntry]] = field(default_factory=list)  # (linha_manager, novo_valor)
    remover: list[tuple[int, str, str]] = field(default_factory=list)  # (linha, departamento, nome)
    ja_corretos: list[tuple[ManagerEntry, int]] = field(default_factory=list)  # (manager, linha)
    duplicados_id_manager: list[tuple[str, str, list[int]]] = field(default_factory=list)  # (dept, nome, [linhas])
    linhas_id_manager_ambiguas: list[tuple[int, str, str]] = field(default_factory=list)  # (linha, dept, nome)
    ignorados_sem_nome: int = 0
    ignorados_sem_manager: int = 0
    linhas_authority_processadas: int = 0
    linhas_manager_lidas: int = 0


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
    text = re.sub(r"[​-‍﻿]", "", text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text)


def valor_texto_para_sheet(value: str) -> str:
    """Preserva valores iniciados por ``+`` quando escritos como USER_ENTERED.

    Sem o apóstrofo, o Google Sheets interpreta telefones internacionais como
    números e remove o sinal, fazendo a sincronização deixar de ser idempotente.
    """

    text = str(value or "")
    return f"'{text}" if text.startswith("+") else text


def calcular_plano(bp_autority: list[list[str]], id_manager: list[list[str]]) -> PlanoSincronizacaoIdManager:
    """Calcula plano de sincronização de ID_MANAGER."""

    plano = PlanoSincronizacaoIdManager()

    if not bp_autority or not id_manager:
        return plano

    # Mapear headers
    idx_auth = map_headers(bp_autority[0])
    idx_manager = map_headers(id_manager[0])

    # Validar colunas obrigatórias
    for col in (COL_NOME, COL_TELEFONE, COL_EMAIL):
        if col not in idx_auth:
            raise RuntimeError(f"BP AUTORITY sem coluna: {col}")

    for col in (COL_DEPARTAMENTOS, COL_NOME, COL_TELEFONE, COL_EMAIL):
        if col not in idx_manager:
            raise RuntimeError(f"ID_MANAGER sem coluna: {col}")

    # Descobrir colunas MANAGER_* dinamicamente
    manager_cols = [col for col in bp_autority[0] if str(col).strip().upper().startswith("MANAGER_")]

    # Ler managers ativos de BP AUTORITY
    managers_ativos: dict[tuple[str, str], list[ManagerEntry]] = {}  # (dept_token, nome_norm) -> [entries]

    for linha_auth, row_auth in enumerate(bp_autority[1:], start=2):
        nome = get(row_auth, idx_auth, COL_NOME)
        id_user = get(row_auth, idx_auth, COL_ID_USER)

        if not nome:
            plano.ignorados_sem_nome += 1
            continue

        plano.linhas_authority_processadas += 1

        tem_manager = False
        for manager_col in manager_cols:
            if is_true(get(row_auth, idx_auth, manager_col)):
                tem_manager = True
                telefone = get(row_auth, idx_auth, COL_TELEFONE)
                email = get(row_auth, idx_auth, COL_EMAIL)

                # Construir nome de departamento
                dept_suffix = manager_col.replace("MANAGER_", "").strip()
                departamento = f"D. {dept_suffix}"

                entry = ManagerEntry(
                    id_user=id_user,
                    nome=nome,
                    telefone=telefone,
                    email=email,
                    departamento=departamento,
                    manager_col=manager_col,
                    linha_authority=linha_auth,
                )

                key = entry.idempotency_key
                if key not in managers_ativos:
                    managers_ativos[key] = []
                managers_ativos[key].append(entry)

        if not tem_manager:
            plano.ignorados_sem_manager += 1

    # Ler registros atuais de ID_MANAGER
    id_manager_por_key: dict[tuple[str, str], list[tuple[int, list[str]]]] = {}  # (dept_token, nome_norm) -> [(linha, row)]

    duplicados_encontrados = False
    for linha_mgr, row_mgr in enumerate(id_manager[1:], start=2):
        departamento = get(row_mgr, idx_manager, COL_DEPARTAMENTOS)
        nome = get(row_mgr, idx_manager, COL_NOME)

        plano.linhas_manager_lidas += 1

        if not departamento or not nome:
            plano.linhas_id_manager_ambiguas.append((linha_mgr, departamento, nome))
            continue

        # Normalizar para chave
        dept_token = departamento.replace("D.", "").strip().upper()
        dept_token = re.sub(r"[​-‍﻿]", "", dept_token)
        dept_token = unicodedata.normalize("NFD", dept_token)
        dept_token = "".join(ch for ch in dept_token if unicodedata.category(ch) != "Mn")
        dept_token = re.sub(r"[^A-Z0-9]+", "", dept_token)

        nome_norm = normalize_text(nome)

        key = (dept_token, nome_norm)
        if key not in id_manager_por_key:
            id_manager_por_key[key] = []
        id_manager_por_key[key].append((linha_mgr, row_mgr))

        if len(id_manager_por_key[key]) > 1:
            duplicados_encontrados = True

    # Detectar duplicados
    if duplicados_encontrados:
        for key, entries in id_manager_por_key.items():
            if len(entries) > 1:
                dept_token, nome_norm = key
                linhas = [linha for linha, _ in entries]
                plano.duplicados_id_manager.append((dept_token, nome_norm, linhas))

    # Comparar: o que criar, atualizar, remover
    for key, manager_entries in managers_ativos.items():
        if key not in id_manager_por_key:
            # Criar - pode haver múltiplos Managers do mesmo dept
            for entry in manager_entries:
                plano.criar.append(entry)
        else:
            # Já existe - verificar se precisa atualizar
            id_manager_entries = id_manager_por_key[key]

            # Se houver duplicados, não atualizar automaticamente
            if len(id_manager_entries) > 1:
                continue

            linha_mgr, row_mgr = id_manager_entries[0]

            # Comparar dados (pode haver múltiplos managers, usar o primeiro)
            entry = manager_entries[0]

            telefone_atual = get(row_mgr, idx_manager, COL_TELEFONE)
            email_atual = get(row_mgr, idx_manager, COL_EMAIL)

            if (entry.telefone != telefone_atual or entry.email != email_atual):
                plano.atualizar.append((linha_mgr, entry))
            else:
                plano.ja_corretos.append((entry, linha_mgr))

    # Detectar remoções (em ID_MANAGER mas não em BP AUTORITY)
    for key, id_manager_entries in id_manager_por_key.items():
        if key not in managers_ativos:
            # Esta chave não existe mais em BP AUTORITY - remover de ID_MANAGER
            for linha_mgr, row_mgr in id_manager_entries:
                dept_token, nome_norm = key
                plano.remover.append((linha_mgr, dept_token, nome_norm))

    return plano


def imprimir_plano(plano: PlanoSincronizacaoIdManager, aplicar: bool) -> None:
    print("###############################################################################")
    print("[ID_MANAGER] SINCRONIZAR BP AUTORITY -> ID_MANAGER")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}")
    print(f"Linhas BP AUTORITY processadas: {plano.linhas_authority_processadas}")
    print(f"Linhas ID_MANAGER lidas: {plano.linhas_manager_lidas}")
    print(f"Registros já corretos: {len(plano.ja_corretos)}")
    print(f"Registros a criar: {len(plano.criar)}")
    print(f"Registros a atualizar: {len(plano.atualizar)}")
    print(f"Registros a remover: {len(plano.remover)}")
    print(f"Duplicados detectados: {len(plano.duplicados_id_manager)}")
    print(f"Linhas ambíguas: {len(plano.linhas_id_manager_ambiguas)}")
    print(f"Ignorados (sem nome): {plano.ignorados_sem_nome}")
    print(f"Ignorados (sem MANAGER_*): {plano.ignorados_sem_manager}")
    print("###############################################################################")

    if plano.ja_corretos:
        print("\nREGISTROS JÁ CORRETOS")
        for entry, linha in plano.ja_corretos[:10]:
            print(f"  Linha {linha}: {entry.departamento:20} | {entry.nome:30} | {entry.email}")
        if len(plano.ja_corretos) > 10:
            print(f"  ... e mais {len(plano.ja_corretos) - 10}")

    if plano.criar:
        print("\nREGISTROS A CRIAR")
        for entry in plano.criar[:10]:
            print(f"  {entry.departamento:20} | {entry.nome:30} | {entry.telefone} | {entry.email}")
        if len(plano.criar) > 10:
            print(f"  ... e mais {len(plano.criar) - 10}")

    if plano.atualizar:
        print("\nREGISTROS A ATUALIZAR")
        for linha, entry in plano.atualizar[:10]:
            print(f"  Linha {linha}: {entry.departamento:20} | {entry.nome:30} | {entry.telefone} | {entry.email}")
        if len(plano.atualizar) > 10:
            print(f"  ... e mais {len(plano.atualizar) - 10}")

    if plano.remover:
        print("\nREGISTROS A REMOVER")
        for linha, dept, nome in plano.remover[:10]:
            print(f"  Linha {linha}: D. {dept:20} | {nome}")
        if len(plano.remover) > 10:
            print(f"  ... e mais {len(plano.remover) - 10}")

    if plano.duplicados_id_manager:
        print("\nDUPLICADOS DETECTADOS EM ID_MANAGER")
        for dept, nome, linhas in plano.duplicados_id_manager:
            print(f"  D. {dept} | {nome} | Linhas: {linhas}")

    if plano.linhas_id_manager_ambiguas:
        print("\nLINHAS AMBÍGUAS EM ID_MANAGER")
        for linha, dept, nome in plano.linhas_id_manager_ambiguas:
            print(f"  Linha {linha}: DEPARTAMENTOS='{dept}', NOME='{nome}'")

    if not aplicar:
        print(f"\nDry-run: nenhuma sheet foi alterada.")


def aplicar_plano(guard: SpreadsheetGuard, id_manager: list[list[str]], plano: PlanoSincronizacaoIdManager) -> None:
    idx_manager = map_headers(id_manager[0])

    # Criar (append)
    if plano.criar:
        rows_to_append = []
        for entry in plano.criar:
            row = [""] * len(id_manager[0])
            if COL_DEPARTAMENTOS in idx_manager:
                row[idx_manager[COL_DEPARTAMENTOS]] = f"D. {entry.dept_token}"
            if COL_NOME in idx_manager:
                row[idx_manager[COL_NOME]] = entry.nome
            if COL_TELEFONE in idx_manager:
                row[idx_manager[COL_TELEFONE]] = entry.telefone
            if COL_EMAIL in idx_manager:
                row[idx_manager[COL_EMAIL]] = entry.email
            rows_to_append.append(row)

        guard.append_rows(SHEET_ID_MANAGER, rows_to_append)

    # Atualizar
    if plano.atualizar:
        updates = []
        for linha, entry in plano.atualizar:
            if COL_TELEFONE in idx_manager:
                updates.append(
                    (
                        linha,
                        idx_manager[COL_TELEFONE] + 1,
                        valor_texto_para_sheet(entry.telefone),
                    )
                )
            if COL_EMAIL in idx_manager:
                updates.append((linha, idx_manager[COL_EMAIL] + 1, entry.email))

        if updates:
            guard.batch_update_cells(SHEET_ID_MANAGER, updates)

    # Remover
    if plano.remover:
        linhas_remover = sorted([linha for linha, _, _ in plano.remover], reverse=True)
        guard.delete_rows(SHEET_ID_MANAGER, linhas_remover)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Aplica mudancas em ID_MANAGER.",
    )
    args = parser.parse_args()

    settings = load_settings()
    writable = {SHEET_ID_MANAGER} if args.aplicar else set()
    guard = SpreadsheetGuard(settings, writable_original_titles=writable)

    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)
    id_manager = guard.read_worksheet(SHEET_ID_MANAGER)

    plano = calcular_plano(bp_autority, id_manager)
    imprimir_plano(plano, args.aplicar)

    if args.aplicar:
        aplicar_plano(guard, id_manager, plano)


if __name__ == "__main__":
    main()
