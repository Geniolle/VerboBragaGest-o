"""Diagnostico read-only da hierarquia normal de DOMINGO/MINISTRO.

Mostra a hierarquia real carregada de CLAUDE_BP ALGORITIMO e compara a ordem
oficial com a ordem que o motor percorre nos domingos normais.
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
    avaliar_candidatos_para_slot,
    calcular_demanda_onda_expansiva,
    eh_slot_ceia,
    montar_rank_hierarquia_continua,
    ordenar_hierarquia_atual,
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


def carregar_contexto():
    guard = SpreadsheetGuard(load_settings())
    regras_raw = guard.read_worksheet(BP_ALGORITMO_TITLE)
    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    excluse_header, excluse_rows = carregar_excluse_matriz(guard.read_worksheet("Excluse"))
    bp_log = carregar_bp_log(guard.read_worksheet("BP LOG"))
    bp_service_raw = guard.read_worksheet("BP SERVICE")
    regras = [
        regra
        for regra in carregar_regras_colaboradores(regras_raw)
        if regra.departamento == DEPARTAMENTO
        and regra.funcao == FUNCAO
        and DIA in regra.dia_da_semana
    ]
    vistos: set[str] = set()
    grupo = []
    for regra in ordenar_hierarquia_atual(regras):
        chave = regra.nome.strip().upper()
        if chave in vistos:
            continue
        vistos.add(chave)
        grupo.append(regra)
    return guard, grupo, agenda_raw, excluse_header, excluse_rows, bp_log, bp_service_raw


def slots_janela(agenda_raw: list[list[str]], inicio: date, fim: date) -> list[SlotAgenda]:
    idx = build_header_index(agenda_raw[0])
    slots: list[SlotAgenda] = []
    for row_i, row in enumerate(agenda_raw[1:], start=1):
        dia = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if DIA not in dia:
            continue
        data_slot = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if data_slot is None or data_slot < inicio or data_slot > fim:
            continue
        slots.append(montar_slot(row, idx, row_i, data_slot))
    return sorted(slots, key=lambda slot: slot.data)


def main() -> None:
    _guard, grupo, agenda_raw, excluse_header, excluse_rows, bp_log, bp_service_raw = carregar_contexto()
    print("HIERARQUIA REAL CARREGADA DE CLAUDE_BP ALGORITIMO")
    print("ORDEM | COLABORADOR | PRIORIDADE | REPETICAO | TODOS_MESES | SEMANA_PREF | CEIA | EXTRA")
    for i, regra in enumerate(grupo, start=1):
        print(
            f"{i} | {regra.nome} | {regra.prioridade} | {regra.repeticao_mensal} | "
            f"{regra.alocar_todos_os_meses} | {regra.semana_preferencial} | "
            f"{regra.ceia_alternada} | {regra.alocacao_extra}"
        )

    slots = slots_janela(agenda_raw, date(2026, 10, 4), date(2026, 12, 20))
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

    print()
    print("SEQUENCIA PRODUZIDA PELO MOTOR")
    print("DATA | TIPO_DIA | INTENCAO | POLITICA | ESCOLHIDO | CONSOME | CURSOR_ANTES | CURSOR_DEPOIS | CANDIDATOS")
    for decisao in decisoes:
        tipo_dia = "CEIA" if eh_slot_ceia(decisao.slot) else "DOMINGO_NORMAL"
        print(
            f"{decisao.slot.data.isoformat()} | {tipo_dia} | {decisao.intent} | "
            f"{decisao.politica_selecao} | "
            f"{decisao.vencedor} | {'SIM' if decisao.consome_hierarquia else 'NAO'} | "
            f"{decisao.cursor_antes or '(nenhum)'} | {decisao.cursor_depois or '(nenhum)'} | "
            f"{'; '.join(decisao.candidatos_avaliados)}"
        )

    print()
    print("ANALISE DOS DOMINGOS NORMAIS COM HIERARQUIA A PARTIR DO CURSOR")
    estado_replay = EstadoExecucaoGrupo(
        historico_total={},
        zumbis_prioritarios=carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO),
    )
    decisoes_por_data = {d.slot.data: d for d in decisoes}
    decisoes_por_row = {}
    for slot in slots:
        decisao = decisoes_por_data[slot.data]
        if eh_slot_ceia(slot):
            # Reaplica pela decisao completa para manter o estado coerente para os domingos seguintes.
            alocar_grupo(
                grupo,
                [slot],
                estado_replay,
                demanda.mapa_limites_locais,
                excluse_header=excluse_header,
                excluse_rows=excluse_rows,
                mapa_limites_mensais=demanda.mapa_limites_mensais,
                aniversarios=carregar_aniversarios(bp_service_raw),
                compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA),
            )
            continue

        rank = montar_rank_hierarquia_continua(grupo, decisao.cursor_antes)
        ordem_cursor = sorted(grupo, key=lambda r: rank.get(r.nome, r.prioridade))
        print()
        print(f"DATA={slot.data.isoformat()} CURSOR_ANTES={decisao.cursor_antes or '(nenhum)'} INTENCAO={decisao.intent}")
        print("ORDEM_PURA_CURSOR=" + " > ".join(r.nome for r in ordem_cursor))
        for regra in ordem_cursor:
            validos, _ = avaliar_candidatos_para_slot(
                [regra],
                slot,
                estado_replay,
                demanda.mapa_limites_locais,
                requisito_tema=None,
                ignorar_vizinhanca_e_descanso=False,
                excluse_header=excluse_header,
                excluse_rows=excluse_rows,
                mapa_limites_mensais=demanda.mapa_limites_mensais,
                decisoes_por_row=decisoes_por_row,
                aniversarios=carregar_aniversarios(bp_service_raw),
                compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA),
                meses_da_ronda={s.mes_key for s in slots},
            )
            status = "SIM" if validos else "NAO"
            print(
                f"  {regra.nome} prioridade={regra.prioridade} semana_pref={regra.semana_preferencial} "
                f"elegivel={status}"
            )
        print(f"ESCOLHIDO={decisao.vencedor} CANDIDATOS_MOTOR={'; '.join(decisao.candidatos_avaliados)}")

        # Avanca o estado de replay de forma igual ao motor principal para a proxima data.
        alocar_grupo(
            grupo,
            [slot],
            estado_replay,
            demanda.mapa_limites_locais,
            excluse_header=excluse_header,
            excluse_rows=excluse_rows,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            aniversarios=carregar_aniversarios(bp_service_raw),
            compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA),
        )


if __name__ == "__main__":
    main()
