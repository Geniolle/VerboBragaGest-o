"""Sincroniza Membresia -> BP SERVICE.

Processo Utilizador / Membresia. Marca a flag quando a pessoa ja existe em
BP SERVICE e cria um novo registo quando nao existe match seguro. Por padrao
roda em dry-run; use --aplicar para escrever nas sheets.
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
    TEM_WHATSAPP = "O número acima tem WhatsApp"
    NUMBER_WHATSAPP = "Nº WhatsApp"
    CODIGO_POSTAL = "Código Postal"
    MORADA = "Morada"
    FREGUESIA = "Freguesia"
    DISCIPULADO = "Discipulado Verbo da Vida"
    FLAG_BP_SERVICE = "BP SERVICE"


class ColBpService:
    ID_USER = "ID_USER"
    NOME = "NOME"
    DATA_NASCIMENTO = "DATA NASCIMENTO"
    EMAIL = "EMAIL"
    TELEFONE = "TELEFONE"
    WHATSAPP = "WHATSAPP"
    NUMBER_WHATSAPP = "NUMBER_WHATSAPP"
    CODIGO_POSTAL = "CÓDIGO POSTAL"
    MORADA = "MORADA"
    FREGUESIA = "FREGUESIA"
    DISCIPULADO = "DISCIPULADO VERBO DA VIDA"
    TYPE = "TYPE"
    INATIVO = "INATIVO"


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
    nome_bp: str = ""


@dataclass(frozen=True)
class Ambiguidade:
    linha_membresia: int
    nome: str
    motivo: str
    ids_possiveis: tuple[str, ...]


@dataclass(frozen=True)
class Criacao:
    identidade: IdentidadeMembresia
    id_user: str
    row: list[str]


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


def parse_whatsapp(valor: object) -> bool | None:
    texto = normalize_text(valor)
    if texto == "SIM":
        return True
    if texto in {"NAO", "NÃO"}:
        return False
    return None


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
            ColBpService.TYPE,
            ColBpService.INATIVO,
        ),
        SHEET_BP_SERVICE,
    )
    por_email: dict[str, list[PessoaBp]] = {}
    por_telefone: dict[str, list[PessoaBp]] = {}
    por_nome_nascimento: dict[str, list[PessoaBp]] = {}

    for linha, row in enumerate(valores[1:], start=2):
        if get(row, idx, ColBpService.TYPE) or is_true(get(row, idx, ColBpService.INATIVO)):
            continue
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


def conflito_nome_data(pessoa: PessoaBp, identidade: IdentidadeMembresia) -> bool:
    if identidade.nome_nascimento and pessoa.nome_nascimento:
        return identidade.nome_nascimento != pessoa.nome_nascimento
    if identidade.nome and pessoa.nome and identidade.nome != pessoa.nome and identidade.nascimento and pessoa.nascimento:
        return True
    return False


def resolver_multiplos_por_desempate(candidatos: list[PessoaBp], identidade: IdentidadeMembresia, metodo_base: str) -> Match | Ambiguidade:
    candidatos = unicos(candidatos)
    if len(candidatos) == 1:
        pessoa = candidatos[0]
        if metodo_base.startswith("TELEFONE") and conflito_nome_data(pessoa, identidade):
            return Ambiguidade(
                identidade.linha,
                identidade.nome_original,
                "TELEFONE encontrou um registo, mas nome/data conflitam",
                (pessoa.id_user,) if pessoa.id_user else (),
            )
        return Match(identidade.linha, identidade.nome_original, pessoa.id_user, metodo_base, pessoa.nome)

    for telefone, sufixo in (
        (identidade.telefone, "TELEFONE"),
        (identidade.number_whatsapp, "NUMBER_WHATSAPP"),
    ):
        if not telefone:
            continue
        filtrados = [p for p in candidatos if telefone in p.telefones]
        if len(filtrados) == 1:
            pessoa = filtrados[0]
            if metodo_base.startswith("TELEFONE") and conflito_nome_data(pessoa, identidade):
                continue
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, f"{metodo_base}+{sufixo}", pessoa.nome)

    if identidade.nome_nascimento:
        filtrados = [p for p in candidatos if p.nome_nascimento == identidade.nome_nascimento]
        if len(filtrados) == 1:
            pessoa = filtrados[0]
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, f"{metodo_base}+NOME+DATA_NASCIMENTO", pessoa.nome)

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
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, "EMAIL", pessoa.nome)
        if len(candidatos) > 1:
            return resolver_multiplos_por_desempate(candidatos, identidade, "EMAIL")

    candidatos_telefone: list[PessoaBp] = []
    for telefone in identidade.telefones:
        candidatos_telefone.extend(por_telefone.get(telefone, []))
    candidatos_telefone = unicos(candidatos_telefone)
    if len(candidatos_telefone) == 1:
        pessoa = candidatos_telefone[0]
        if not conflito_nome_data(pessoa, identidade):
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, "TELEFONE", pessoa.nome)
        return Ambiguidade(
            identidade.linha,
            identidade.nome_original,
            "TELEFONE encontrou um registo, mas nome/data conflitam",
            (pessoa.id_user,) if pessoa.id_user else (),
        )
    if len(candidatos_telefone) > 1:
        return resolver_multiplos_por_desempate(candidatos_telefone, identidade, "TELEFONE")

    if identidade.nome_nascimento:
        candidatos_nome = por_nome_nascimento.get(identidade.nome_nascimento, [])
        if len(candidatos_nome) == 1:
            pessoa = candidatos_nome[0]
            return Match(identidade.linha, identidade.nome_original, pessoa.id_user, "NOME+DATA_NASCIMENTO", pessoa.nome)
        if len(candidatos_nome) > 1:
            return Ambiguidade(
                identidade.linha,
                identidade.nome_original,
                "NOME+DATA_NASCIMENTO encontrou multiplos registos",
                tuple(p.id_user for p in candidatos_nome if p.id_user),
            )

    return None


def collect_existing_numeric_ids(bp_service: list[list[str]]) -> set[int]:
    idx = map_headers(bp_service[0])
    ids: set[int] = set()
    for row in bp_service[1:]:
        raw = get(row, idx, ColBpService.ID_USER)
        if re.fullmatch(r"\d+", raw):
            ids.add(int(raw))
    return ids


def next_user_id(existing: set[int]) -> str:
    candidate = max(existing or {0}) + 1
    while candidate in existing:
        candidate += 1
    existing.add(candidate)
    return str(candidate)


def format_date_for_bp_service(valor: object) -> str:
    normalized = normalize_date(valor)
    if not normalized:
        return ""
    yyyy, mm, dd = normalized.split("-")
    return f"{dd}/{mm}/{yyyy}"


def set_value(row: list[str], idx: dict[str, int], col: str, value: object) -> None:
    i = idx.get(col)
    if i is not None:
        row[i] = value


def build_new_bp_row(
    identidade: IdentidadeMembresia,
    membresia_row: list[str],
    idx_membresia: dict[str, int],
    bp_header: list[str],
    idx_bp: dict[str, int],
    id_user: str,
) -> list[str]:
    row: list[object] = [""] * len(bp_header)
    whatsapp = parse_whatsapp(get(membresia_row, idx_membresia, ColMembresia.TEM_WHATSAPP))

    set_value(row, idx_bp, ColBpService.ID_USER, id_user)
    set_value(row, idx_bp, ColBpService.NOME, identidade.nome_original)
    set_value(row, idx_bp, ColBpService.TELEFONE, get(membresia_row, idx_membresia, ColMembresia.TELEFONE))
    set_value(row, idx_bp, ColBpService.EMAIL, get(membresia_row, idx_membresia, ColMembresia.EMAIL))
    set_value(row, idx_bp, ColBpService.CODIGO_POSTAL, get(membresia_row, idx_membresia, ColMembresia.CODIGO_POSTAL))
    set_value(row, idx_bp, ColBpService.MORADA, get(membresia_row, idx_membresia, ColMembresia.MORADA))
    set_value(row, idx_bp, ColBpService.FREGUESIA, get(membresia_row, idx_membresia, ColMembresia.FREGUESIA))
    set_value(
        row,
        idx_bp,
        ColBpService.DATA_NASCIMENTO,
        format_date_for_bp_service(get(membresia_row, idx_membresia, ColMembresia.DATA_NASCIMENTO)),
    )
    set_value(row, idx_bp, ColBpService.DISCIPULADO, get(membresia_row, idx_membresia, ColMembresia.DISCIPULADO))

    if whatsapp is not None:
        set_value(row, idx_bp, ColBpService.WHATSAPP, whatsapp)
    if whatsapp is False:
        set_value(row, idx_bp, ColBpService.NUMBER_WHATSAPP, get(membresia_row, idx_membresia, ColMembresia.NUMBER_WHATSAPP))

    return ["" if value is None else value for value in row]


def calcular_matches(
    membresia: list[list[str]],
    bp_service: list[list[str]],
) -> tuple[list[Match], list[Ambiguidade], list[Criacao]]:
    idx_membresia = map_headers(membresia[0])
    validar_colunas(
        idx_membresia,
        (
            ColMembresia.NOME,
            ColMembresia.DATA_NASCIMENTO,
            ColMembresia.EMAIL,
            ColMembresia.TELEFONE,
            ColMembresia.TEM_WHATSAPP,
            ColMembresia.NUMBER_WHATSAPP,
            ColMembresia.CODIGO_POSTAL,
            ColMembresia.MORADA,
            ColMembresia.FREGUESIA,
            ColMembresia.DISCIPULADO,
            ColMembresia.FLAG_BP_SERVICE,
        ),
        SHEET_MEMBRESIA,
    )
    idx_bp = map_headers(bp_service[0])
    validar_colunas(
        idx_bp,
        (
            ColBpService.ID_USER,
            ColBpService.NOME,
            ColBpService.DATA_NASCIMENTO,
            ColBpService.EMAIL,
            ColBpService.TELEFONE,
            ColBpService.WHATSAPP,
            ColBpService.NUMBER_WHATSAPP,
            ColBpService.CODIGO_POSTAL,
            ColBpService.MORADA,
            ColBpService.FREGUESIA,
            ColBpService.DISCIPULADO,
        ),
        SHEET_BP_SERVICE,
    )
    por_email, por_telefone, por_nome_nascimento = indexar_bp_service(bp_service)
    existing_ids = collect_existing_numeric_ids(bp_service)

    encontrados: list[Match] = []
    ambiguos: list[Ambiguidade] = []
    criacoes: list[Criacao] = []

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
            id_user = next_user_id(existing_ids)
            criacoes.append(
                Criacao(
                    identidade=identidade,
                    id_user=id_user,
                    row=build_new_bp_row(
                        identidade,
                        row,
                        idx_membresia,
                        bp_service[0],
                        idx_bp,
                        id_user,
                    ),
                )
            )

    return encontrados, ambiguos, criacoes


def validar_criacoes_bp_service(
    bp_service: list[list[str]],
    criacoes: list[Criacao],
) -> tuple[list[Criacao], list[Criacao]]:
    idx_bp = map_headers(bp_service[0])
    por_id: dict[str, list[PessoaBp]] = {}

    for linha, row in enumerate(bp_service[1:], start=2):
        pessoa = PessoaBp(
            linha=linha,
            id_user=get(row, idx_bp, ColBpService.ID_USER),
            nome=normalize_text(get(row, idx_bp, ColBpService.NOME)),
            email=normalize_email(get(row, idx_bp, ColBpService.EMAIL)),
            telefone=normalize_phone(get(row, idx_bp, ColBpService.TELEFONE)),
            number_whatsapp=normalize_phone(get(row, idx_bp, ColBpService.NUMBER_WHATSAPP)),
            nascimento=normalize_date(get(row, idx_bp, ColBpService.DATA_NASCIMENTO)),
        )
        if pessoa.id_user:
            por_id.setdefault(pessoa.id_user, []).append(pessoa)

    validadas: list[Criacao] = []
    falhadas: list[Criacao] = []

    for criacao in criacoes:
        candidatos = por_id.get(criacao.id_user, [])
        if len(candidatos) != 1:
            falhadas.append(criacao)
            continue

        pessoa = candidatos[0]
        identidade = criacao.identidade
        if identidade.nome and pessoa.nome != identidade.nome:
            falhadas.append(criacao)
            continue
        if identidade.email and pessoa.email != identidade.email:
            falhadas.append(criacao)
            continue
        if identidade.telefone and identidade.telefone not in pessoa.telefones:
            falhadas.append(criacao)
            continue

        validadas.append(criacao)

    return validadas, falhadas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Cria/valida BP SERVICE e marca TRUE na Membresia.")
    args = parser.parse_args()

    settings = load_settings()
    guard = SpreadsheetGuard(settings, writable_original_titles={SHEET_MEMBRESIA, SHEET_BP_SERVICE} if args.aplicar else set())
    membresia = guard.read_worksheet(SHEET_MEMBRESIA)
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)

    encontrados, ambiguos, criacoes = calcular_matches(membresia, bp_service)
    idx_membresia = map_headers(membresia[0])
    col_flag = idx_membresia[ColMembresia.FLAG_BP_SERVICE] + 1

    print("###############################################################################")
    print("[MEMBRESIA-BP] SINCRONIZACAO MEMBRESIA -> BP SERVICE")
    print(f"Modo: {'APLICAR' if args.aplicar else 'DRY-RUN'}")
    print(f"Encontrados inequivocos: {len(encontrados)}")
    print(f"Criacoes previstas: {len(criacoes)}")
    print(f"Ambiguos: {len(ambiguos)}")
    print("###############################################################################")

    print("\nENCONTRADOS INEQUIVOCOS")
    for item in encontrados:
        print(f"Linha={item.linha_membresia} Nome={item.nome!r} ID_USER={item.id_user} Metodo={item.metodo} Nome BP={item.nome_bp!r}")

    print("\nAMBIGUOS")
    for item in ambiguos:
        print(f"Linha={item.linha_membresia} Nome={item.nome!r} Motivo={item.motivo} IDs={', '.join(item.ids_possiveis)}")

    print("\nCRIAR EM BP SERVICE")
    for item in criacoes:
        print(f"Linha={item.identidade.linha} Nome={item.identidade.nome_original!r} Novo ID_USER={item.id_user}")

    if args.aplicar:
        criacoes_validadas = criacoes
        criacoes_falhadas: list[Criacao] = []
        if criacoes:
            guard.append_rows(SHEET_BP_SERVICE, [item.row for item in criacoes])
            print(f"\nCriadas {len(criacoes)} linhas em BP SERVICE.")
            bp_service_pos_criacao = guard.read_worksheet(SHEET_BP_SERVICE)
            criacoes_validadas, criacoes_falhadas = validar_criacoes_bp_service(
                bp_service_pos_criacao,
                criacoes,
            )
            print(f"Criacoes validadas em BP SERVICE: {len(criacoes_validadas)}")
            if criacoes_falhadas:
                print("Criacoes NAO validadas; Membresia.BP SERVICE nao sera marcada:")
                for item in criacoes_falhadas:
                    print(
                        f"Linha={item.identidade.linha} "
                        f"Nome={item.identidade.nome_original!r} "
                        f"ID_USER={item.id_user}"
                    )
        updates = [(item.linha_membresia, col_flag, "TRUE") for item in encontrados]
        updates.extend((item.identidade.linha, col_flag, "TRUE") for item in criacoes_validadas)
        if updates:
            guard.batch_update_cells(SHEET_MEMBRESIA, updates)
            print(f"Atualizadas {len(updates)} linhas em Membresia.BP SERVICE.")
        else:
            print("\nNenhuma alteracao para aplicar.")
    elif not args.aplicar:
        print("\nDry-run: nenhuma sheet foi alterada.")


if __name__ == "__main__":
    main()
