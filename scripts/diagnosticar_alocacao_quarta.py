"""Diagnostico read-only de D. MINISTROS / MINISTRO / QUARTA-FEIRA.

Uso:
    uv run python scripts/diagnosticar_alocacao_quarta.py --data 2026-11-18

O script le as abas CLAUDE_* e imprime a fase de reservas FIXO_RECORRENTE
antes do rodizio normal. Nao escreve em nenhuma aba.
"""

from __future__ import annotations

import argparse
from datetime import date

from pastoreio_orquestrador.carregamento import (
    build_header_index,
    carregar_aniversarios,
    carregar_bp_log,
    carregar_compromissos_cruzados,
    carregar_excluse_matriz,
    carregar_regras_colaboradores,
    carregar_temas,
    carregar_zumbis_prioritarios,
    extrair_assiduidade_da_linha,
    extrair_papeis_da_linha,
    get,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.domain.quarta.recorrencia import (
    avaliar_regra_fixa_na_data,
    montar_decisao_fixa,
    reserva_fixa_para_data,
    separar_regras_quarta,
)
from pastoreio_orquestrador.models import SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    calcular_demanda_onda_expansiva,
    diagnosticar_escolha_slot,
    montar_requisito_tema_por_slot,
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
DIA = "QUARTA-FEIRA"
COL_NOME = "MINISTRO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
BP_ALGORITMO_TITLE = "CLAUDE_BP ALGORITIMO"


def _parse_iso_data(valor: str) -> date:
    return date.fromisoformat(valor)


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, data_slot: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=data_slot,
        dia_da_semana=DIA,
        tema=get(row, idx, ColAppAnualGlobal.TEMA).strip(),
        mes_key=month_key(data_slot),
        semana_do_mes=week_of_month(data_slot),
        is_ultima_ocorrencia_do_mes=is_last_occurrence_of_month(data_slot),
        assiduidade=extrair_assiduidade_da_linha(row, idx),
        papeis=extrair_papeis_da_linha(row, idx),
    )


def imprimir_avaliacoes_fixas(regras_fixas, data_alvo: date) -> list:
    print("RESERVAS FIXAS AVALIADAS:")
    avaliacoes = [avaliar_regra_fixa_na_data(regra, data_alvo) for regra in regras_fixas]
    if not avaliacoes:
        print("- (nenhuma)")
        return []

    for avaliacao in avaliacoes:
        regra = avaliacao.regra
        print(f"- {regra.nome}")
        print(f"  TIPO: {regra.tipo_alocacao}")
        print(f"  ANCORA: {regra.data_inicio_recorrencia}")
        print(f"  INTERVALO: {regra.intervalo_meses} meses")
        print(f"  DELTA_MESES: {avaliacao.delta_meses}")
        print(f"  MES DA RECORRENCIA: {'SIM' if avaliacao.mes_da_recorrencia else 'NAO'}")
        print(f"  SEMANA EXIGIDA: {avaliacao.semana_exigida}")
        print(f"  SEMANA DA DATA: {avaliacao.semana_da_data}")
        print(f"  RESERVA APLICA: {'SIM' if avaliacao.aplica else 'NAO'}")
    return avaliacoes


def imprimir_trace_normal(trace, requisito_tema: str | None) -> None:
    print(f"RESULTADO ESPERADO: {trace.selecionado or 'SEM ALOCACAO'}")
    print("RODIZIO NORMAL EXECUTADO: SIM")
    print(f"TIPO_DIA: {trace.tipo_dia}")
    print(f"INTENCAO_DA_VAGA: {trace.intent}")
    print(f"POLITICA_DE_SELECAO: {trace.politica_selecao}")
    print(f"NIVEL/TEMA EXIGIDO: {requisito_tema or '(sem requisito)'}")
    print(f"MOTIVO_DA_ESCOLHA: {trace.motivo_escolha}")
    print()
    print("CANDIDATOS_ANALISADOS:")
    for avaliacao in trace.avaliacoes:
        status = "ELEGIVEL" if avaliacao.elegivel else "REJEITADO"
        print(
            f"{avaliacao.passada} #{avaliacao.ordem} | {avaliacao.candidato} | "
            f"prioridade={avaliacao.prioridade} | {status} | {avaliacao.motivo} | "
            f"quota_mes={avaliacao.ocorrencias_mes}/{avaliacao.limite_mensal}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostica uma alocacao de QUARTA-FEIRA em modo read-only.")
    parser.add_argument("--data", required=True, help="Data ISO da alocacao, ex.: 2026-11-18.")
    args = parser.parse_args()

    data_alvo = _parse_iso_data(args.data)

    settings = load_settings()
    data_corte_historico = settings.data_corte_historico
    guard = SpreadsheetGuard(settings)

    regras_raw = guard.read_worksheet(BP_ALGORITMO_TITLE)
    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    livros_raw = guard.read_worksheet("Livros")
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
    grupo_normal, regras_fixas = separar_regras_quarta(regras)

    slots: list[SlotAgenda] = []
    alvo: SlotAgenda | None = None
    valor_atual = ""
    registros_rotacionais_ignorados = 0
    for row_i, row in enumerate(agenda_raw[1:], start=1):
        dia_linha = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if DIA not in dia_linha:
            continue
        data_slot = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if data_slot is None:
            continue
        if data_slot < data_corte_historico:
            registros_rotacionais_ignorados += 1
            continue
        if data_slot > data_alvo:
            continue
        slot = montar_slot(row, idx, row_i, data_slot)
        slot.valor_atual = get(row, idx, COL_NOME).strip()
        slots.append(slot)
        if data_slot == data_alvo:
            alvo = slot
            valor_atual = slot.valor_atual

    if alvo is None:
        raise SystemExit(f"Data {data_alvo.isoformat()} nao encontrada em {AGENDA_TITLE} a partir do corte.")

    print("MODO: READ-ONLY (nenhuma escrita em Sheets)")
    print(f"DATA: {data_alvo.isoformat()}")
    print(f"DATA_CORTE_HISTORICO: {data_corte_historico.isoformat()}")
    print(f"TEMA: {alvo.tema or '(vazio)'}")
    print(f"SEMANA_DO_MES: {alvo.semana_do_mes}")
    print(f"VALOR ATUAL NA AGENDA: {valor_atual or '(vazio)'}")
    print(f"REGISTROS_ROTACIONAIS_IGNORADOS_ANTES_DO_CORTE: {registros_rotacionais_ignorados}")
    print()

    imprimir_avaliacoes_fixas(regras_fixas, data_alvo)
    print()

    regra_fixa = reserva_fixa_para_data(regras_fixas, data_alvo)
    if regra_fixa is not None:
        decisao = montar_decisao_fixa(alvo, regra_fixa)
        print(f"RESULTADO ESPERADO: {decisao.vencedor}")
        print("RODIZIO NORMAL EXECUTADO: NAO")
        if valor_atual and valor_atual.strip().upper() != decisao.vencedor.upper():
            print(f"CONFLITO: RESERVA FIXA ESPERADA {decisao.vencedor}; VALOR PERSISTIDO {valor_atual}.")
            print("ACAO: nenhuma escrita automatica; configuracao/agenda precisa ser validada.")
        return

    slots.sort(key=lambda slot: slot.data)
    slots_anteriores = [slot for slot in slots if slot.data < data_alvo]
    slots_normais_anteriores = [
        slot for slot in slots_anteriores
        if reserva_fixa_para_data(regras_fixas, slot.data) is None
    ]
    temas_livros = carregar_temas(livros_raw)
    requisitos_tema = montar_requisito_tema_por_slot(slots_normais_anteriores + [alvo], temas_livros)
    demanda = calcular_demanda_onda_expansiva(
        grupo_normal,
        vagas_reais_no_periodo=len(slots_normais_anteriores) + 1,
        meses_tocados=len({slot.mes_key for slot in slots_normais_anteriores + [alvo]}),
    )
    estado = EstadoExecucaoGrupo(
        historico_total={},
        zumbis_prioritarios=carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO),
    )
    decisoes_por_row = {}
    if slots_normais_anteriores:
        decisoes_anteriores = alocar_grupo(
            grupo_normal,
            slots_normais_anteriores,
            estado,
            demanda.mapa_limites_locais,
            requisitos_tema_por_slot=requisitos_tema,
            excluse_header=excluse_header,
            excluse_rows=excluse_rows,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            aniversarios=carregar_aniversarios(bp_service_raw),
            compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA),
        )
        decisoes_por_row = {decisao.slot.row_index: decisao for decisao in decisoes_anteriores}

    requisito_alvo = requisitos_tema.get(alvo.row_index)
    trace = diagnosticar_escolha_slot(
        grupo_normal,
        alvo,
        estado,
        demanda.mapa_limites_locais,
        requisito_tema=requisito_alvo,
        excluse_header=excluse_header,
        excluse_rows=excluse_rows,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
        decisoes_por_row=decisoes_por_row,
        aniversarios=carregar_aniversarios(bp_service_raw),
        compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA),
        meses_da_ronda={slot.mes_key for slot in slots_normais_anteriores + [alvo]},
        hierarquia_cursor_regras=grupo_normal,
    )
    imprimir_trace_normal(trace, requisito_alvo)


if __name__ == "__main__":
    main()
