"""Marca Membresia.BP SERVICE=TRUE para pessoas ja existentes em BP SERVICE.

Processo Utilizador / Membresia. Este script nao cria colaboradores e nao
altera BP SERVICE. Por padrao roda em dry-run; use --aplicar para escrever a
flag apenas nas linhas com match inequivoco.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_MEMBRESIA = "Membresia"
SHEET_BP_SERVICE = "BP SERVICE"


class ColMembresia:
    NOME = "Nome Próprio + Apelido"
    DATA_NASCIMENTO = "Data de Nascimento"
    EMAIL = "Email"
    TELEFONE = "Contacto Telefónico"
    NUMBER_WHATSAPP = "Nº WhatsApp"
    FLAG_BP_SERVICE = "BP SERVICE"


class ColBpService:
    ID_USER = "ID_USER"
    NOME = "NOME"
    DATA_NASCIMENTO = "DATA NASCIMENTO"
    EMAIL = "EMAIL"
    TELEFONE = "TELEFONE"
    NUMBER_WHATSAPP = "NUMBER_WHATSAPP"


@dataclass(frozen=True)
class PessoaBp:
    linha: int
    id_user: str
    nome: str
    email: str
    telefone: str
    number_whatsapp: str
    nascimento: str

    @property
    def telefones(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(t for t in (self.telefone, self.number_whatsapp) if t))

    @property
    def nome_nascimento(self) -> str:
        return f"{self.nome}|{self.nascimento}" if self.nome and self.nascimento else ""


@dataclass(frozen=True)
class IdentidadeMembresia:
    linha: int
    nome_original: str
    nome: str
    email: str
    telefone: str
    number_whatsapp: str
    nascimento: str

    @property
    def telefones(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(t for t in (self.telefone, self.number_whatsapp) if t))

    @property
    def nome_nascimento(self) -> str:
        return f"{self.nome}|{self.nascimento}" if self.nome and self.nascimento else ""


@dataclass(frozen=True)
class Match:
    linha_membresia: int
    nome: str
    id_user: str
    metodo: str


@dataclass(frozen=True)
class Ambiguidade:
    linha_membresia: int
    nome: str
    motivo: str
    ids_possiveis: tuple[str, ...]


def map_headers(header: list[str]) -> dict[str, int]:
    return {str(nome).strip(): i for i, nome in enumerate(header) if str(nome).strip()}


def get(row: list[str], idx: dict[str, int], coluna: str) -> str:
    i = idx.get(coluna)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def validar_colunas(idx: dict[str, int], colunas: tuple[str, ...], sheet: str) -> None:
    faltando = [col for col in colunas if col not in idx]
    if faltando:
        raise RuntimeError(f"{sheet} sem coluna(s): {', '.join(faltando)}")


def normalize_text(valor: object) -> str:
    texto = "" if valor is None else str(valor)
    texto = re.sub(r"[\u200B-\u200D\uFEFF]", "", texto)
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", texto.strip().upper())


def normalize_email(valor: object) -> str:
    return "" if valor is None else str(valor).strip().lower()


def normalize_phone(valor: object) -> str:
    return re.sub(r"\D+", "", "" if valor is None else str(valor))


def normalize_date(valor: object) -> str:
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        return ""
    texto = texto.split()[0]
    for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def is_true(valor: object) -> bool:
    return normalize_text(valor) == "TRUE"


def indexar_bp_service(valores: list[list[str]]) -> tuple[dict[str, list[PessoaBp]], dict[str, list[PessoaBp]], dict[str, list[PessoaBp]]]:
    idx = map_headers(valores[0])
    validar_colunas(
        idx,
        (
            ColBpService.ID_USER,
            ColBpService.NOME,
            ColBpService.DATA_NASCIMENTO,
            ColBpService.EMAIL,
            ColBpService.TELEFONE,
            ColBpService.NUMBER_WHATSAPP,
        ),
        SHEET_BP_SERVICE,
    )
    por_email: dict[str, list[PessoaBp]] = {}
    por_telefone: dict[str, list[PessoaBp]] = {}
    por_nome_nascimento: dict[str, list[PessoaBp]] = {}

    for linha, row in enumerate(valores[1:], start=2):
        pessoa = PessoaBp(
            linha=linha,
            id_user=get(row, idx, ColBpService.ID_USER),
            nome=normalize_text(get(row, idx, ColBpService.NOME)),
            email=normalize_email(get(row, idx, ColBpService.EMAIL)),
            telefone=normalize_phone(get(row, idx, ColBpService.TELEFONE)),
            number_whatsapp=normalize_phone(get(row, idx, ColBpService.NUMBER_WHATSAPP)),
            nascimento=normalize_date(get(row, idx, ColBpService.DATA_NASCIMENTO)),
        )
        if pessoa.email:
            por_email.setdefault(pessoa.email, []).append(pessoa)
        for telefone in pessoa.telefones:
            por_telefone.setdefault(telefone, []).append(pessoa)
        if pessoa.nome_nascimento:
            por_nome_nascimento.setdefault(pessoa.nome_nascimento, []).append(pessoa)

    return por_email, por_telefone, por_nome_nascimento


def identidade_membresia(linha: int, row: list[str], idx: dict[str, int]) -> IdentidadeMembresia:
    nome_original = get(row, idx, ColMembresia.NOME)
    return IdentidadeMembresia(
        linha=linha,
        nome_original=nome_original,
        nome=normalize_text(nome_original),
        email=normalize_email(get(row, idx, ColMembresia.EMAIL)),
        telefone=normalize_phone(get(row, idx, ColMembresia.TELEFONE)),
        number_whatsapp=normalize_phone(get(row, idx, ColMembresia.NUMBER_WHATSAPP)),
        nascimento=normalize_date(get(row, idx, ColMembresia.DATA_NASCIMENTO)),
    )


def unicos(pessoas: list[PessoaBp]) -> list[PessoaBp]:
    vistos: set[tuple[str, int]] = set()
    resultado: list[PessoaBp] = []
    for pessoa in pessoas:
        chave = (pessoa.id_user, pessoa.linha)
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(pessoa)
    return resultado


def resolver_multiplos_por_desempate(candidatos: list[PessoaBp], identidade: IdentidadeMembresia, metodo_base: str) -> Match | Ambiguidade:
    candidatos = unicos(candidatos)
    if len(candidatos) == 1:
        pessoa = candidatos[0]
        return Match(identidade.linha, identidade.nome_original, pessoa.id_user, metodo_base)

    for telefone, sufixo in (
        (identidade.telefone, "TELEFONE"),
        (identidade.number_whatsapp, "NUMBER_WHATSAPP"),
    ):
        if not telefone:
            continue
        filtrados = [p for p in candidatos if telefone in p.telefones]
        if len(filtrados) == 1:
            pessoa = filtrados[0]
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, f"{metodo_base}+{sufixo}")

    if identidade.nome_nascimento:
        filtrados = [p for p in candidatos if p.nome_nascimento == identidade.nome_nascimento]
        if len(filtrados) == 1:
            pessoa = filtrados[0]
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, f"{metodo_base}+NOME+DATA_NASCIMENTO")

    return Ambiguidade(
        identidade.linha,
        identidade.nome_original,
        f"{metodo_base} encontrou multiplos registos sem desempate inequivoco",
        tuple(p.id_user for p in candidatos if p.id_user),
    )


def encontrar_match(
    identidade: IdentidadeMembresia,
    por_email: dict[str, list[PessoaBp]],
    por_telefone: dict[str, list[PessoaBp]],
    por_nome_nascimento: dict[str, list[PessoaBp]],
) -> Match | Ambiguidade | None:
    if identidade.email:
        candidatos = por_email.get(identidade.email, [])
        if len(candidatos) == 1:
            pessoa = candidatos[0]
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, "EMAIL")
        if len(candidatos) > 1:
            return resolver_multiplos_por_desempate(candidatos, identidade, "EMAIL")

    candidatos_telefone: list[PessoaBp] = []
    for telefone in identidade.telefones:
        candidatos_telefone.extend(por_telefone.get(telefone, []))
    candidatos_telefone = unicos(candidatos_telefone)
    if len(candidatos_telefone) == 1:
        pessoa = candidatos_telefone[0]
        return Match(identidade.linha, identidade.nome_original, pessoa.id_user, "TELEFONE")
    if len(candidatos_telefone) > 1:
        return resolver_multiplos_por_desempate(candidatos_telefone, identidade, "TELEFONE")

    if identidade.nome_nascimento:
        candidatos_nome = por_nome_nascimento.get(identidade.nome_nascimento, [])
        if len(candidatos_nome) == 1:
            pessoa = candidatos_nome[0]
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, "NOME+DATA_NASCIMENTO")
        if len(candidatos_nome) > 1:
            return Ambiguidade(
                identidade.linha,
                identidade.nome_original,
                "NOME+DATA_NASCIMENTO encontrou multiplos registos",
                tuple(p.id_user for p in candidatos_nome if p.id_user),
            )

    return None


def calcular_matches(
    membresia: list[list[str]],
    bp_service: list[list[str]],
) -> tuple[list[Match], list[Ambiguidade], list[IdentidadeMembresia]]:
    idx_membresia = map_headers(membresia[0])
    validar_colunas(
        idx_membresia,
        (
            ColMembresia.NOME,
            ColMembresia.DATA_NASCIMENTO,
            ColMembresia.EMAIL,
            ColMembresia.TELEFONE,
            ColMembresia.NUMBER_WHATSAPP,
            ColMembresia.FLAG_BP_SERVICE,
        ),
        SHEET_MEMBRESIA,
    )
    por_email, por_telefone, por_nome_nascimento = indexar_bp_service(bp_service)

    encontrados: list[Match] = []
    ambiguos: list[Ambiguidade] = []
    nao_encontrados: list[IdentidadeMembresia] = []

    for linha, row in enumerate(membresia[1:], start=2):
        flag = get(row, idx_membresia, ColMembresia.FLAG_BP_SERVICE)
        if is_true(flag) or flag:
            continue
        identidade = identidade_membresia(linha, row, idx_membresia)
        resultado = encontrar_match(identidade, por_email, por_telefone, por_nome_nascimento)
        if isinstance(resultado, Match):
            encontrados.append(resultado)
        elif isinstance(resultado, Ambiguidade):
            ambiguos.append(resultado)
        else:
            nao_encontrados.append(identidade)

    return encontrados, ambiguos, nao_encontrados


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Marca TRUE na coluna BP SERVICE da Membresia.")
    args = parser.parse_args()

    settings = load_settings()
    guard = SpreadsheetGuard(settings, writable_original_titles={SHEET_MEMBRESIA} if args.aplicar else set())
    membresia = guard.read_worksheet(SHEET_MEMBRESIA)
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)

    encontrados, ambiguos, nao_encontrados = calcular_matches(membresia, bp_service)
    idx_membresia = map_headers(membresia[0])
    col_flag = idx_membresia[ColMembresia.FLAG_BP_SERVICE] + 1

    print("###############################################################################")
    print("[MEMBRESIA-BP] VALIDACAO DE EXISTENTES")
    print(f"Modo: {'APLICAR' if args.aplicar else 'DRY-RUN'}")
    print(f"Encontrados inequivocos: {len(encontrados)}")
    print(f"Ambiguos: {len(ambiguos)}")
    print(f"Nao encontrados: {len(nao_encontrados)}")
    print("###############################################################################")

    print("\nENCONTRADOS INEQUIVOCOS")
    for item in encontrados:
        print(f"Linha={item.linha_membresia} Nome={item.nome!r} ID_USER={item.id_user} Metodo={item.metodo}")

    print("\nAMBIGUOS")
    for item in ambiguos:
        print(f"Linha={item.linha_membresia} Nome={item.nome!r} Motivo={item.motivo} IDs={', '.join(item.ids_possiveis)}")

    print("\nNAO ENCONTRADOS")
    for item in nao_encontrados:
        print(f"Linha={item.linha} Nome={item.nome_original!r}")

    if args.aplicar and encontrados:
        updates = [(item.linha_membresia, col_flag, "TRUE") for item in encontrados]
        guard.batch_update_cells(SHEET_MEMBRESIA, updates)
        print(f"\nAtualizadas {len(updates)} linhas em Membresia.BP SERVICE.")
    elif not args.aplicar:
        print("\nDry-run: nenhuma sheet foi alterada.")


if __name__ == "__main__":
    main()
