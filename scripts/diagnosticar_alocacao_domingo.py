"""Diagnostico read-only de uma alocacao de DOMINGO.

Uso:
    uv run python scripts/diagnosticar_alocacao_domingo.py --data 2027-01-31

O script le as abas CLAUDE_* e fontes auxiliares, simula em memoria ate a data
pedida e imprime o mesmo trace estruturado produzido pelo dominio. Nao escreve
em nenhuma aba.
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
    carregar_historico_ceia_persistido,
    carregar_regras_colaboradores,
    carregar_zumbis_prioritarios,
    contar_ocorrencias_mensais_por_colaborador,
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
    calcular_participantes_ciclo_ceia,
    diagnosticar_escolha_slot,
    eh_slot_ceia,
    montar_vizinhos_de_data_por_row,
    ordenar_hierarquia_atual,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month,
    month_key,
    parse_date_ddmmyyyy,
    week_of_month,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
from pastoreio_orquestrador.auditoria import NOME_ABA_AUDITORIA

DEPARTAMENTO_PADRAO = "D. MINISTROS"
FUNCAO_PADRAO = "MINISTRO"
DIA_PADRAO = "DOMINGO"
COLUNA_PADRAO = "MINISTRO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
BP_ALGORITMO_TITLE = "CLAUDE_BP ALGORITIMO"


def _parse_iso_data(valor: str) -> date:
    return date.fromisoformat(valor)


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, data_slot: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=data_slot,
        dia_da_semana=DIA_PADRAO,
        tema="",
        mes_key=month_key(data_slot),
        semana_do_mes=week_of_month(data_slot),
        is_ultima_ocorrencia_do_mes=is_last_occurrence_of_month(data_slot),
        assiduidade=extrair_assiduidade_da_linha(row, idx),
        papeis=extrair_papeis_da_linha(row, idx),
    )


def imprimir_ceia(historico_ceia, participantes_ceia, usados_ciclo, primeiro_candidato) -> None:
    print("HISTORICO CEIA PERSISTIDO:")
    if historico_ceia:
        for nome in historico_ceia:
            print(f"- {nome}")
    else:
        print("- (vazio)")
    print()
    print("PARTICIPANTES ATUAIS:")
    for regra in participantes_ceia:
        print(f"- {regra.nome}")
    print()
    ciclo_completo = bool(historico_ceia) and not usados_ciclo and bool(participantes_ceia)
    print(f"CICLO ANTERIOR: {'COMPLETO' if ciclo_completo else 'INCOMPLETO OU SEM HISTORICO'}")
    print("PARTICIPANTES DO CICLO ATUAL:")
    if usados_ciclo:
        for nome in sorted(usados_ciclo):
            print(f"- {nome}")
    else:
        print("[]")
    print(f"NOVO CICLO: {'SIM' if ciclo_completo else 'NAO'}")
    print("ORDEM:")
    for regra in participantes_ceia:
        print(f"- {regra.nome}")
    print(f"PRIMEIRO CANDIDATO: {primeiro_candidato or '(sem candidato)'}")
    print()


def imprimir_trace(trace, hierarquia) -> None:
    print(f"DATA: {trace.data}")
    print(f"TIPO_DIA: {trace.tipo_dia}")
    print(f"INTENCAO_DA_VAGA: {trace.intent}")
    print(f"POLITICA_DE_SELECAO: {trace.politica_selecao}")
    print(f"CURSOR_ANTES: {trace.cursor_antes or '(nenhum)'}")
    print(f"ULTIMA_ANCORA_NORMAL: {trace.cursor_antes or '(nenhuma)'}")
    print(f"ESCOLHIDO: {trace.selecionado or 'SEM ALOCACAO'}")
    print(f"MOTIVO_DA_ESCOLHA: {trace.motivo_escolha}")
    print(f"CONSOME_HIERARQUIA: {'SIM' if trace.consome_hierarquia else 'NAO'}")
    print(f"CURSOR_DEPOIS: {trace.cursor_depois or '(nenhum)'}")
    print()
    print("HIERARQUIA CARREGADA DO BP ALGORITIMO:")
    print("ORDEM | COLABORADOR | PRIORIDADE | REPETICAO | TODOS_MESES | SEMANA_PREF | CEIA | EXTRA")
    for ordem, regra in enumerate(hierarquia, start=1):
        print(
            f"{ordem} | {regra.nome} | {regra.prioridade} | {regra.repeticao_mensal} | "
            f"{regra.alocar_todos_os_meses} | {regra.semana_preferencial} | "
            f"{regra.ceia_alternada} | {regra.alocacao_extra}"
        )
    print()
    print("CANDIDATOS_ANALISADOS:")
    for avaliacao in trace.avaliacoes:
        status = "ELEGIVEL" if avaliacao.elegivel else "REJEITADO"
        print(
            f"{avaliacao.passada} #{avaliacao.ordem} | {avaliacao.candidato} | "
            f"prioridade={avaliacao.prioridade} | {status} | {avaliacao.motivo} | "
            f"quota_mes={avaliacao.ocorrencias_mes}/{avaliacao.limite_mensal} | "
            f"repeticao={avaliacao.repeticao_mensal} | todos_meses={avaliacao.alocar_todos_os_meses} | "
            f"ceia_mes={avaliacao.ceia_no_mes}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostica uma alocacao de DOMINGO em modo read-only.")
    parser.add_argument("--data", required=True, help="Data ISO da alocacao, ex.: 2027-01-31.")
    parser.add_argument("--departamento", default=DEPARTAMENTO_PADRAO)
    parser.add_argument("--funcao", default=FUNCAO_PADRAO)
    parser.add_argument("--grupo", default=DIA_PADRAO, help="Dia/grupo. Padrao: DOMINGO.")
    args = parser.parse_args()

    data_alvo = _parse_iso_data(args.data)
    departamento = args.departamento
    funcao = args.funcao
    dia = args.grupo.upper()

    guard = SpreadsheetGuard(load_settings())
    regras_raw = guard.read_worksheet(BP_ALGORITMO_TITLE)
    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    titulos = set(guard.list_worksheet_titles())
    auditoria_raw = guard.read_worksheet(NOME_ABA_AUDITORIA) if NOME_ABA_AUDITORIA in titulos else []
    excluse_header, excluse_rows = carregar_excluse_matriz(guard.read_worksheet("Excluse"))
    bp_log = carregar_bp_log(guard.read_worksheet("BP LOG"))
    bp_service_raw = guard.read_worksheet("BP SERVICE")

    idx = build_header_index(agenda_raw[0])
    regras = [
        regra for regra in carregar_regras_colaboradores(regras_raw)
        if regra.departamento == departamento
        and regra.funcao == funcao
        and dia in regra.dia_da_semana
    ]
    vistos: set[str] = set()
    grupo_regras = []
    for regra in ordenar_hierarquia_atual(regras):
        chave = regra.nome.strip().upper()
        if chave in vistos:
            continue
        vistos.add(chave)
        grupo_regras.append(regra)

    nomes_validos = {r.nome.strip().upper(): r.nome for r in grupo_regras}
    historico_ceia_persistido = carregar_historico_ceia_persistido(
        agenda_raw,
        auditoria_raw,
        dia_da_semana=dia,
        coluna_alocacao=COLUNA_PADRAO,
        nomes_validos=nomes_validos,
        antes_de=data_alvo,
    )
    participantes_ceia = [r for r in grupo_regras if r.ceia_alternada]
    usados_ciclo_ceia = calcular_participantes_ciclo_ceia(
        {r.nome for r in participantes_ceia},
        historico_ceia_persistido,
    )
    primeiro_candidato_ceia = next(
        (r.nome for r in participantes_ceia if r.nome not in usados_ciclo_ceia),
        participantes_ceia[0].nome if participantes_ceia else "",
    )
    slots: list[SlotAgenda] = []
    valor_atual_alvo = ""
    for row_i, row in enumerate(agenda_raw[1:], start=1):
        dia_linha = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if dia not in dia_linha:
            continue
        data_slot = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if data_slot is None or data_slot > data_alvo:
            continue
        slot = montar_slot(row, idx, row_i, data_slot)
        slot.valor_atual = get(row, idx, COLUNA_PADRAO).strip()
        slots.append(slot)
        if data_slot == data_alvo:
            valor_atual_alvo = slot.valor_atual
    slots.sort(key=lambda s: s.data)
    if not any(s.data == data_alvo for s in slots):
        raise SystemExit(f"Data {data_alvo.isoformat()} nao encontrada em {AGENDA_TITLE}.")

    alvo = [s for s in slots if s.data == data_alvo][0]
    slots_anteriores = [s for s in slots if s.data < data_alvo]
    meses = {s.mes_key for s in slots}
    demanda = calcular_demanda_onda_expansiva(
        grupo_regras,
        vagas_reais_no_periodo=len(slots),
        meses_tocados=len(meses),
    )
    estado = EstadoExecucaoGrupo(
        historico_total={},
        zumbis_prioritarios=carregar_zumbis_prioritarios(bp_log, departamento, funcao),
        ocorrencias_mensais_externas=contar_ocorrencias_mensais_por_colaborador(
            agenda_raw,
            dia,
            ("CEIA",),
            nomes_validos=nomes_validos,
        ),
    )
    decisoes_por_row = {}
    if slots_anteriores:
        decisoes_anteriores = alocar_grupo(
            grupo_regras,
            slots_anteriores,
            estado,
            demanda.mapa_limites_locais,
            excluse_header=excluse_header,
            excluse_rows=excluse_rows,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            aniversarios=carregar_aniversarios(bp_service_raw),
            compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COLUNA_PADRAO, dia),
        )
        decisoes_por_row = {d.slot.row_index: d for d in decisoes_anteriores}
    estado.historico_vencedores_ceia = list(historico_ceia_persistido)

    vizinhos_de_data = montar_vizinhos_de_data_por_row(slots).get(alvo.row_index, (None, None))
    trace = diagnosticar_escolha_slot(
        grupo_regras,
        alvo,
        estado,
        demanda.mapa_limites_locais,
        requisito_tema=None,
        excluse_header=excluse_header,
        excluse_rows=excluse_rows,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
        decisoes_por_row=decisoes_por_row,
        vizinhos_de_data=vizinhos_de_data,
        aniversarios=carregar_aniversarios(bp_service_raw),
        compromissos_cruzados=carregar_compromissos_cruzados(agenda_raw, COLUNA_PADRAO, dia),
        meses_da_ronda=meses,
        hierarquia_cursor_regras=grupo_regras,
    )

    print("MODO: READ-ONLY (nenhuma escrita em Sheets)")
    print(f"VALOR_ATUAL_NA_AGENDA: {valor_atual_alvo or '(vazio)'}")
    print(f"SLOT_CEIA: {'SIM' if eh_slot_ceia(alvo) else 'NAO'}")
    print()
    imprimir_ceia(historico_ceia_persistido, participantes_ceia, usados_ciclo_ceia, primeiro_candidato_ceia)
    imprimir_trace(trace, grupo_regras)


if __name__ == "__main__":
    main()
