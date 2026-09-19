"""Simula, sem escrever, a quota mensal de MINISTRO/DOMINGO contando CEIA.

Le apenas abas `CLAUDE_*`/originais em modo read-only e reproduz a proxima
Ronda de D. MINISTROS/MINISTRO/DOMINGO com as ocorrencias de CEIA ja
persistidas contabilizadas para REPETICAO MENSAL.
"""

from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.auditoria import NOME_ABA_AUDITORIA, resolver_ultimo_cursor_hierarquia
from pastoreio_orquestrador.carregamento import (
    build_header_index,
    carregar_aniversarios,
    carregar_bp_log,
    carregar_compromissos_cruzados,
    carregar_excluse_matriz,
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
    alocar_ronda_dinamica,
    calcular_demanda_onda_expansiva,
    delimitar_uma_ronda,
    filtrar_slots_ja_preenchidos,
    necessidade_mensal_restante,
    ocorrencias_mensais_colaborador,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month,
    month_key,
    parse_date_ddmmyyyy,
    week_of_month,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

DEPARTAMENTO, FUNCAO, DIA = "D. MINISTROS", "MINISTRO", "DOMINGO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
BP_ALGORITMO_TITLE = "CLAUDE_BP ALGORITIMO"
COL_NOME = "MINISTRO"
COL_CEIA = "CEIA"


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=d,
        dia_da_semana=DIA,
        tema="",
        mes_key=month_key(d),
        semana_do_mes=week_of_month(d),
        is_ultima_ocorrencia_do_mes=is_last_occurrence_of_month(d),
        assiduidade=extrair_assiduidade_da_linha(row, idx),
        papeis=extrair_papeis_da_linha(row, idx),
    )


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)
    titulos = set(guard.list_worksheet_titles())

    regras_raw = guard.read_worksheet(BP_ALGORITMO_TITLE)
    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    auditoria_raw = guard.read_worksheet(NOME_ABA_AUDITORIA) if NOME_ABA_AUDITORIA in titulos else []
    excluse_header, excluse_rows = carregar_excluse_matriz(guard.read_worksheet("Excluse"))
    bp_log = carregar_bp_log(guard.read_worksheet("BP LOG"))
    bp_service_raw = guard.read_worksheet("BP SERVICE")
    aniversarios = carregar_aniversarios(bp_service_raw)

    idx = build_header_index(agenda_raw[0])
    regras = carregar_regras_colaboradores(regras_raw)
    grupo = []
    vistos: set[str] = set()
    for regra in regras:
        nome_key = regra.nome.strip().upper()
        if (
            regra.departamento == DEPARTAMENTO
            and regra.funcao == FUNCAO
            and DIA in regra.dia_da_semana
            and nome_key not in vistos
        ):
            grupo.append(regra)
            vistos.add(nome_key)
    regras_por_nome = {r.nome.strip().upper(): r for r in grupo}
    nomes_canonicos = {nome: regra.nome for nome, regra in regras_por_nome.items()}
    regras_por_nome_exato = {r.nome: r for r in grupo}

    ocorrencias_ceia = contar_ocorrencias_mensais_por_colaborador(
        agenda_raw, DIA, (COL_CEIA,), nomes_validos=nomes_canonicos
    )
    ocorrencias_agenda = contar_ocorrencias_mensais_por_colaborador(
        agenda_raw, DIA, (COL_CEIA, COL_NOME), nomes_validos=nomes_canonicos
    )
    cursor = resolver_ultimo_cursor_hierarquia(
        agenda_raw, auditoria_raw, grupo, DEPARTAMENTO, FUNCAO, DIA, COL_NOME
    )
    compromissos_cruzados = carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA)

    linhas_agenda: list[tuple[int, date, str]] = []
    for row_i, row in enumerate(agenda_raw[1:], start=1):
        dia = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if DIA not in dia:
            continue
        d = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if d is None:
            continue
        linhas_agenda.append((row_i, d, get(row, idx, COL_NOME).strip()))
    linhas_agenda.sort(key=lambda t: t[1])

    valor_por_data = {d: valor for _, d, valor in linhas_agenda}
    row_por_data = {d: row_i for row_i, d, _ in linhas_agenda}
    todas_as_datas = [d for _, d, _ in linhas_agenda]
    restantes = todas_as_datas[:]
    blocos: list[list[date]] = []
    while restantes:
        bloco = delimitar_uma_ronda(restantes, len(grupo))
        if not bloco:
            break
        blocos.append(bloco)
        restantes = [d for d in restantes if d > bloco[-1]]

    estado = EstadoExecucaoGrupo(
        historico_total={},
        zumbis_prioritarios=carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO),
        cursor_hierarquia=cursor.ancora,
    )

    def processar_bloco(datas: list[date], aplicar_cruzados: bool = False, ronda_aberta: bool = False):
        slots = [montar_slot(agenda_raw[row_por_data[d]], idx, row_por_data[d], d) for d in datas]
        if ronda_aberta:
            slots = filtrar_slots_ja_preenchidos(slots, valor_por_data)
        demanda = calcular_demanda_onda_expansiva(
            grupo, vagas_reais_no_periodo=len(slots), meses_tocados=len({s.mes_key for s in slots})
        )
        return alocar_grupo(
            grupo,
            slots,
            estado,
            demanda.mapa_limites_locais,
            excluse_header=excluse_header,
            excluse_rows=excluse_rows,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            compromissos_cruzados=compromissos_cruzados if aplicar_cruzados else None,
            aniversarios=aniversarios,
        )

    ronda_para_simular: list[date] | None = None
    for bloco in blocos:
        if all(valor_por_data[d] for d in bloco):
            processar_bloco(bloco, aplicar_cruzados=False)
            continue
        ronda_para_simular = bloco
        break

    if ronda_para_simular is None:
        print("Nenhuma Ronda aberta encontrada.")
        return

    estado.cursor_hierarquia = cursor.ancora
    estado.cursor_hierarquia_referencia = cursor.ancora
    estado.cursor_hierarquia_referencia_fixada = True
    estado.hierarquia_consumida_na_ronda.clear()
    estado.ocorrencias_mensais_externas = ocorrencias_ceia

    datas_abertas = [d for d in todas_as_datas if d >= ronda_para_simular[0]]
    slots_abertos = [montar_slot(agenda_raw[row_por_data[d]], idx, row_por_data[d], d) for d in datas_abertas]
    slots_abertos = filtrar_slots_ja_preenchidos(slots_abertos, valor_por_data)

    def alocar_slots_dinamicos(slots: list[SlotAgenda], estado_exec: EstadoExecucaoGrupo):
        demanda = calcular_demanda_onda_expansiva(
            grupo, vagas_reais_no_periodo=len(slots), meses_tocados=len({s.mes_key for s in slots})
        )
        return alocar_grupo(
            grupo,
            slots,
            estado_exec,
            demanda.mapa_limites_locais,
            excluse_header=excluse_header,
            excluse_rows=excluse_rows,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            compromissos_cruzados=compromissos_cruzados,
            aniversarios=aniversarios,
        )

    resultado = alocar_ronda_dinamica(
        grupo, slots_abertos, estado, len(grupo), alocar_slots_dinamicos
    )

    print("DATA | TIPO | COLABORADOR | REPETICAO MENSAL | LIMITE | OCORR ANTES | OCORR DEPOIS | CONSOME HIERARQUIA | MOTIVO")
    for decisao in resultado.decisoes:
        tipo = "CEIA" if decisao.motivo == "CEIA ALTERNADA" else "NORMAL"
        regra = regras_por_nome_exato.get(decisao.vencedor or "")
        repeticao = regra.repeticao_mensal if regra else ""
        print(
            f"{decisao.slot.data.isoformat()} | {tipo} | {decisao.vencedor or 'SEM ALOCAÇÃO'} | "
            f"{repeticao} | {decisao.limite_mensal if decisao.limite_mensal is not None else ''} | "
            f"{decisao.ocorrencias_mes_antes if decisao.ocorrencias_mes_antes is not None else ''} | "
            f"{decisao.ocorrencias_mes_depois if decisao.ocorrencias_mes_depois is not None else ''} | "
            f"{'SIM' if decisao.consome_hierarquia else 'NAO'} | {decisao.motivo}"
        )

    print("\nCandidatos com quota mensal cheia por CEIA na Ronda simulada:")
    houve_bloqueio = False
    meses_da_ronda = {s.mes_key for s in resultado.slots}
    ceia_simulada = {
        (decisao.vencedor, decisao.slot.mes_key)
        for decisao in resultado.decisoes
        if decisao.vencedor and decisao.motivo == "CEIA ALTERNADA"
    }
    primeiro_normal_por_mes = {}
    for decisao in resultado.decisoes:
        if decisao.vencedor and decisao.motivo != "CEIA ALTERNADA" and decisao.consome_hierarquia:
            primeiro_normal_por_mes.setdefault(decisao.slot.mes_key, decisao.vencedor)
    for regra in grupo:
        for mes in sorted(meses_da_ronda):
            ocorr = ocorrencias_mensais_colaborador(resultado.estado, regra.nome, mes)
            limite = regra.cota_base
            tem_ceia = (
                ocorrencias_ceia.get(regra.nome, {}).get(mes, 0) > 0
                or (regra.nome, mes) in ceia_simulada
            )
            if ocorr >= limite and tem_ceia:
                houve_bloqueio = True
                restante = necessidade_mensal_restante(resultado.estado, regra, mes, {regra.nome: limite})
                print(
                    f"{regra.nome} | {mes} | ocorrencias_mes={ocorr} | "
                    f"limite={limite} | necessidade_restante={restante} | "
                    f"candidato normal rejeitado se a hierarquia chegar nele: QUOTA MENSAL JA ATINGIDA | "
                    f"normal que consumiu hierarquia no mes={primeiro_normal_por_mes.get(mes, '(nenhum)')}"
                )
    if not houve_bloqueio:
        print("(nenhum nos meses simulados)")

    print("\nCursor final da simulacao:")
    print(f"Ancora inicial: {cursor.ancora or '(nenhuma)'}")
    print(f"Ancora final: {resultado.estado.cursor_hierarquia or '(nenhuma)'}")


if __name__ == "__main__":
    main()
