"""Diagnostico read-only do cursor da hierarquia de DOMINGO/MINISTRO.

Le as abas `CLAUDE_*` e simula uma janela de domingos sem escrever nada.
Mostra, por data, por que a vaga existe, se a decisao consumiu a hierarquia
e como o cursor mudou.
"""

from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.carregamento import (
    build_header_index,
    carregar_aniversarios,
    carregar_bp_log,
    carregar_compromissos_cruzados,
    carregar_excluse_matriz,
    carregar_regras_colaboradores,
    carregar_zumbis_prioritarios,
    extrair_assiduidade_da_linha,
    extrair_papeis_da_linha,
    get,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.models import SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    calcular_demanda_onda_expansiva,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month,
    month_key,
    parse_date_ddmmyyyy,
    week_of_month,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

DEPARTAMENTO = "D. MINISTROS"
FUNCAO = "MINISTRO"
DIA = "DOMINGO"
COL_NOME = "MINISTRO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
BP_ALGORITMO_TITLE = "CLAUDE_BP ALGORITIMO"


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, data_slot: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=data_slot,
        dia_da_semana=DIA,
        tema="",
        mes_key=month_key(data_slot),
        semana_do_mes=week_of_month(data_slot),
        is_ultima_ocorrencia_do_mes=is_last_occurrence_of_month(data_slot),
        assiduidade=extrair_assiduidade_da_linha(row, idx),
        papeis=extrair_papeis_da_linha(row, idx),
    )


def prioridade_por_nome(regras) -> dict[str, int]:
    return {r.nome: r.prioridade for r in regras}


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)

    regras_raw = guard.read_worksheet(BP_ALGORITMO_TITLE)
    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    excluse_header, excluse_rows = carregar_excluse_matriz(guard.read_worksheet("Excluse"))
    bp_log = carregar_bp_log(guard.read_worksheet("BP LOG"))
    bp_service_raw = guard.read_worksheet("BP SERVICE")

    idx = build_header_index(agenda_raw[0])
    regras = [
        regra
        for regra in carregar_regras_colaboradores(regras_raw)
        if regra.departamento == DEPARTAMENTO
        and regra.funcao == FUNCAO
        and DIA in regra.dia_da_semana
    ]
    vistos: set[str] = set()
    grupo = []
    for regra in regras:
        chave = regra.nome.strip().upper()
        if chave in vistos:
            continue
        vistos.add(chave)
        grupo.append(regra)

    inicio = date(2026, 10, 4)
    fim = date(2026, 12, 20)
    slots: list[SlotAgenda] = []
    for row_i, row in enumerate(agenda_raw[1:], start=1):
        dia = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if DIA not in dia:
            continue
        data_slot = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if data_slot is None or data_slot < inicio or data_slot > fim:
            continue
        slots.append(montar_slot(row, idx, row_i, data_slot))
    slots.sort(key=lambda slot: slot.data)

    estado = EstadoExecucaoGrupo(
        historico_total={},
        zumbis_prioritarios=carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO),
    )
    demanda = calcular_demanda_onda_expansiva(
        grupo,
        vagas_reais_no_periodo=len(slots),
        meses_tocados=len({slot.mes_key for slot in slots}),
    )
    decisoes = alocar_grupo(
        grupo,
        slots,
        estado,
        demanda.mapa_limites_locais,
        excluse_header=excluse_header,
        excluse_rows=excluse_rows,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
        aniversarios=carregar_aniversarios(bp_service_raw),
        compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA),
    )

    prioridades = prioridade_por_nome(grupo)
    print(
        "DATA | MES | INTENCAO | TIPO | COLABORADOR | PRIORIDADE | MOTIVO | "
        "OBRIGACAO | CONSOME | CURSOR ANTES | CURSOR DEPOIS | CANDIDATOS"
    )
    for decisao in decisoes:
        tipo = "CEIA" if decisao.motivo == "CEIA ALTERNADA" else decisao.tipo_alocacao or decisao.motivo
        vencedor = decisao.vencedor or "SEM ALOCACAO"
        prioridade = prioridades.get(decisao.vencedor or "", "")
        print(
            f"{decisao.slot.data.isoformat()} | {decisao.slot.mes_key} | "
            f"{decisao.intent or '(nao informado)'} | {tipo} | "
            f"{vencedor} | {prioridade} | {decisao.motivo} | "
            f"{decisao.obrigacao_satisfeita or '-'} | "
            f"{'SIM' if decisao.consome_hierarquia else 'NAO'} | "
            f"{decisao.cursor_antes or '(nenhum)'} | {decisao.cursor_depois or '(nenhum)'} | "
            f"{'; '.join(decisao.candidatos_avaliados)}"
        )


if __name__ == "__main__":
    main()
