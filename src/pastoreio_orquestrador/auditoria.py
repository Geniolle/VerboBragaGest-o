"""Log de auditoria das decisoes do motor.

Cada linha explica uma decisao gravada na agenda. Para DOMINGO, a auditoria
tambem registra se a alocacao consumiu a hierarquia normal; esse dado, cruzado
com AppAnualGlobal, permite reconstruir o cursor entre execucoes mensais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import uuid4

from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.models import DecisaoAlocacao, RegraColaborador
from pastoreio_orquestrador.parsing_utils import parse_date_ddmmyyyy

NOME_ABA_AUDITORIA = "CLAUDE_LOG_AUDITORIA"

CABECALHO_AUDITORIA = [
    "RUN_ID",
    "TIMESTAMP_EXECUCAO",
    "GRUPO",
    "DEPARTAMENTO",
    "FUNCAO",
    "DIA_DA_SEMANA_GRUPO",
    "DATA_SLOT",
    "DIA_DA_SEMANA",
    "TEMA",
    "REQUISITO_TEMA",
    "VENCEDOR",
    "PRIORIDADE_VENCEDOR",
    "MOTIVO",
    "TIPO_ALOCACAO",
    "CONSOME_HIERARQUIA",
    "RUNNER_UP",
    "CANDIDATOS_AVALIADOS",
]


@dataclass
class RegistroAuditoria:
    data_slot: date
    vencedor: str
    motivo: str
    consome_hierarquia: bool
    run_id: str = ""
    prioridade_vencedor: int | None = None
    departamento: str = ""
    funcao: str = ""
    dia_da_semana_grupo: str = ""
    grupo: str = ""


@dataclass
class ResultadoCursorHierarquia:
    ancora: str | None
    prioridade_ancora_atual: int | None
    proximo_candidato: RegraColaborador | None
    registros_validos: list[RegistroAuditoria] = field(default_factory=list)
    diagnosticos: list[str] = field(default_factory=list)


class AuditoriaAgendaInconsistenteError(RuntimeError):
    pass


def _header_index(header: list[str]) -> dict[str, int]:
    return {str(nome).strip().upper(): i for i, nome in enumerate(header)}


def _get(row: list[str], idx: dict[str, int], col: str) -> str:
    pos = idx.get(col.strip().upper())
    if pos is None or pos >= len(row):
        return ""
    return str(row[pos]).strip()


def _parse_bool(valor: str) -> bool:
    return str(valor).strip().upper() in {"TRUE", "SIM", "1", "YES"}


def _parse_data_auditoria(valor: str) -> date | None:
    valor = str(valor).strip()
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return parse_date_ddmmyyyy(valor)


def _grupo_legacy_match(grupo: str, departamento: str, funcao: str, dia: str) -> bool:
    partes = [p.strip().upper() for p in grupo.split("/") if p.strip()]
    return (
        len(partes) >= 3
        and partes[0] == departamento.upper()
        and partes[1] == funcao.upper()
        and partes[2] == dia.upper()
    )


def construir_linhas_auditoria(
    decisoes: list[DecisaoAlocacao],
    grupo_label: str,
    requisitos_tema_por_slot: dict[int, str] | None = None,
    timestamp_execucao: str | None = None,
    run_id: str | None = None,
    departamento: str = "",
    funcao: str = "",
    dia_da_semana_grupo: str = "",
    regras_por_nome: dict[str, RegraColaborador] | None = None,
) -> list[list[str]]:
    """Devolve linhas prontas para `CLAUDE_LOG_AUDITORIA`.

    `CONSOME_HIERARQUIA` diferencia a alocacao normal que move o cursor das
    alocacoes por CEIA, repeticao mensal, ATM, resgate ou lacuna.
    """
    requisitos_tema_por_slot = requisitos_tema_por_slot or {}
    regras_por_nome = regras_por_nome or {}
    ts = timestamp_execucao or datetime.now().isoformat(timespec="seconds")
    rid = run_id or str(uuid4())

    linhas: list[list[str]] = []
    for d in decisoes:
        requisito = requisitos_tema_por_slot.get(d.slot.row_index, "")
        regra = regras_por_nome.get((d.vencedor or "").strip().upper())
        prioridade = d.prioridade_vencedor
        if prioridade is None and regra is not None:
            prioridade = regra.prioridade
        linhas.append(
            [
                rid,
                ts,
                grupo_label,
                departamento,
                funcao,
                dia_da_semana_grupo,
                d.slot.data.isoformat(),
                d.slot.dia_da_semana,
                d.slot.tema,
                requisito,
                d.vencedor or "",
                "" if prioridade is None else str(prioridade),
                d.motivo,
                d.tipo_alocacao or d.motivo,
                "TRUE" if d.consome_hierarquia else "FALSE",
                d.runner_up or "",
                "; ".join(d.candidatos_avaliados),
            ]
        )
    return linhas


def carregar_registros_auditoria(
    valores: list[list[str]],
    departamento: str,
    funcao: str,
    dia_da_semana: str,
) -> list[RegistroAuditoria]:
    if not valores:
        return []
    idx = _header_index(valores[0])
    if "CONSOME_HIERARQUIA" not in idx:
        return []

    registros: list[RegistroAuditoria] = []
    for row in valores[1:]:
        grupo = _get(row, idx, "GRUPO")
        dep = _get(row, idx, "DEPARTAMENTO")
        fn = _get(row, idx, "FUNCAO")
        dia = _get(row, idx, "DIA_DA_SEMANA_GRUPO")
        if dep or fn or dia:
            if dep.upper() != departamento.upper() or fn.upper() != funcao.upper() or dia.upper() != dia_da_semana.upper():
                continue
        elif not _grupo_legacy_match(grupo, departamento, funcao, dia_da_semana):
            continue

        data_slot = _parse_data_auditoria(_get(row, idx, "DATA_SLOT"))
        vencedor = _get(row, idx, "VENCEDOR")
        if data_slot is None or not vencedor:
            continue
        prioridade_txt = _get(row, idx, "PRIORIDADE_VENCEDOR")
        try:
            prioridade = int(prioridade_txt) if prioridade_txt else None
        except ValueError:
            prioridade = None
        registros.append(
            RegistroAuditoria(
                data_slot=data_slot,
                vencedor=vencedor,
                motivo=_get(row, idx, "MOTIVO"),
                consome_hierarquia=_parse_bool(_get(row, idx, "CONSOME_HIERARQUIA")),
                run_id=_get(row, idx, "RUN_ID"),
                prioridade_vencedor=prioridade,
                departamento=dep,
                funcao=fn,
                dia_da_semana_grupo=dia,
                grupo=grupo,
            )
        )
    return registros


def _agenda_por_data(
    agenda_valores: list[list[str]], dia_da_semana: str, coluna_alocacao: str
) -> dict[date, str]:
    if not agenda_valores:
        return {}
    idx = _header_index(agenda_valores[0])
    resultado: dict[date, str] = {}
    for row in agenda_valores[1:]:
        dia = _get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA)
        if dia_da_semana.upper() not in dia.upper():
            continue
        data_slot = parse_date_ddmmyyyy(_get(row, idx, ColAppAnualGlobal.DATA))
        if data_slot is None:
            continue
        resultado[data_slot] = _get(row, idx, coluna_alocacao)
    return resultado


def _proximo_da_hierarquia(
    regras_atuais: list[RegraColaborador], ancora: str | None
) -> tuple[int | None, RegraColaborador | None]:
    hierarquia = sorted(regras_atuais, key=lambda r: (r.prioridade, r.nome.upper()))
    if not hierarquia:
        return None, None
    if not ancora:
        return None, hierarquia[0]
    nomes = [r.nome for r in hierarquia]
    try:
        idx_ancora = nomes.index(ancora)
    except ValueError:
        return None, hierarquia[0]
    proximo = hierarquia[(idx_ancora + 1) % len(hierarquia)]
    return hierarquia[idx_ancora].prioridade, proximo


def resolver_ultimo_cursor_hierarquia(
    agenda_valores: list[list[str]],
    auditoria_valores: list[list[str]],
    regras_atuais: list[RegraColaborador],
    departamento: str,
    funcao: str,
    dia_da_semana: str,
    coluna_alocacao: str,
) -> ResultadoCursorHierarquia:
    """Reconstrui a ultima ancora real da hierarquia normal.

    A auditoria explica quais decisoes consumiram a hierarquia; a agenda
    confirma que aquela alocacao esta realmente persistida. Divergencias sao
    erro explicito, porque usar um log desligado da agenda moveria o cursor
    para uma posicao falsa.
    """
    agenda = _agenda_por_data(agenda_valores, dia_da_semana, coluna_alocacao)
    registros = [
        r for r in carregar_registros_auditoria(auditoria_valores, departamento, funcao, dia_da_semana)
        if r.consome_hierarquia
    ]
    registros.sort(key=lambda r: r.data_slot)

    validos: list[RegistroAuditoria] = []
    inconsistencias: list[str] = []
    for registro in registros:
        vencedor_agenda = agenda.get(registro.data_slot, "")
        if not vencedor_agenda:
            inconsistencias.append(
                f"{registro.data_slot.isoformat()}: auditoria indica {registro.vencedor}, "
                "mas a agenda nao tem alocacao correspondente."
            )
            continue
        if vencedor_agenda.strip().upper() != registro.vencedor.strip().upper():
            inconsistencias.append(
                f"{registro.data_slot.isoformat()}: auditoria indica {registro.vencedor}, "
                f"mas a agenda contem {vencedor_agenda}."
            )
            continue
        validos.append(registro)

    if inconsistencias:
        raise AuditoriaAgendaInconsistenteError("; ".join(inconsistencias))

    ativos_por_nome = {r.nome.strip().upper(): r for r in regras_atuais}
    diagnosticos: list[str] = []
    ancora: str | None = None
    for registro in reversed(validos):
        if registro.vencedor.strip().upper() in ativos_por_nome:
            ancora = ativos_por_nome[registro.vencedor.strip().upper()].nome
            break
        diagnosticos.append(
            f"Ancora ignorada porque nao existe/nao esta ativa na hierarquia atual: {registro.vencedor}"
        )

    prioridade, proximo = _proximo_da_hierarquia(regras_atuais, ancora)
    return ResultadoCursorHierarquia(
        ancora=ancora,
        prioridade_ancora_atual=prioridade,
        proximo_candidato=proximo,
        registros_validos=validos,
        diagnosticos=diagnosticos,
    )
