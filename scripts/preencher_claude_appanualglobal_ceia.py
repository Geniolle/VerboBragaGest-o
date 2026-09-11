# -*- coding: utf-8 -*-
"""Preenche a coluna CEIA da CLAUDE_AppAnualGlobal (D. MINISTROS / CEIA /
DOMINGO) com EXATAMENTE UMA Ronda (ciclo completo) por execucao -- nunca mais
de uma. Respeita qualquer alocacao ja existente na coluna CEIA (nao
sobrescreve) e comeca a proxima Ronda a partir do primeiro 1o-domingo-do-mes
futuro ainda vazio; para rodar a Ronda seguinte, execute o script de novo.

Processo novo (pedido do Clayton, 2026-09-11): FUNÇÃO="CEIA" e distinta de
FUNÇÃO="MINISTRO" (serve a Ceia do Senhor, nao prega) e so acontece no 1o
domingo de cada mes -- por isso os slots aqui sao filtrados por
`week_of_month(d) == 1`, ao contrario do script de MINISTRO/DOMINGO que
processa todos os domingos.

Descoberta e corrigida antes deste script existir (2026-09-11): o cabecalho
da coluna G em "CLAUDE_BP ALGORITIMO" estava em branco (deveria ser
"PRIORIDADE NA ALOCAÇÃO") -- um resto da mudanca de posicao da coluna
"SEMANA PREFERENCIAL" feita em 2026-09-08, que nunca teve o cabecalho
atualizado. Isso fazia `carregar_regras_colaboradores` devolver
prioridade=999 (default) para TODO MUNDO em TODOS os grupos, nao so CEIA --
so nao tinha quebrado nenhum resultado ate agora porque a ordem das linhas
na sheet ja coincidia com a ordem de prioridade pretendida (o desempate por
ordem de insercao do Python mascarava o problema). Corrigido escrevendo de
volta o texto do cabecalho na propria celula (nenhum dado de colaborador foi
alterado) -- ver `scratch/corrigir_header_prioridade.py`.

Nao usa `carregar_compromissos_cruzados` (descanso minimo cruzado entre
quarta-feira e domingo): esse conceito e especifico da FUNÇÃO="MINISTRO"
(mesma pessoa pregando duas vezes em poucos dias); CEIA nao tem par de
quarta-feira, entao a checagem nao se aplica aqui.

Escreve exclusivamente na copia CLAUDE_AppAnualGlobal (guard bloqueia
qualquer tentativa em aba sem o prefixo).
"""
from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.carregamento import (
    build_header_index, carregar_aniversarios, carregar_bp_log,
    carregar_excluse_matriz, carregar_regras_colaboradores,
    carregar_zumbis_prioritarios, extrair_assiduidade_da_linha,
    extrair_papeis_da_linha, get,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.models import SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo, alocar_grupo, calcular_demanda_onda_expansiva,
    delimitar_uma_ronda,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month, month_key, parse_date_ddmmyyyy, week_of_month,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

DEPARTAMENTO, FUNCAO, DIA = "D. MINISTROS", "CEIA", "DOMINGO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
COL_NOME = "CEIA"


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=d,
        dia_da_semana=DIA,
        tema="",  # tema livre, mesma regra do domingo comum
        mes_key=month_key(d),
        semana_do_mes=week_of_month(d),
        is_ultima_ocorrencia_do_mes=is_last_occurrence_of_month(d),
        assiduidade=extrair_assiduidade_da_linha(row, idx),
        papeis=extrair_papeis_da_linha(row, idx),
    )


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)

    regras_raw = guard.read_worksheet("CLAUDE_BP ALGORITIMO")
    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    excluse_raw = guard.read_worksheet("Excluse")
    excluse_header, excluse_rows = carregar_excluse_matriz(excluse_raw)
    bp_log_raw = guard.read_worksheet("BP LOG")
    bp_service_raw = guard.read_worksheet("BP SERVICE")
    aniversarios = carregar_aniversarios(bp_service_raw)

    idx = build_header_index(agenda_raw[0])
    col_ceia = idx[COL_NOME]

    regras = carregar_regras_colaboradores(regras_raw)
    nomes_vistos: set[str] = set()
    grupo = []
    for r in regras:
        if r.departamento == DEPARTAMENTO and r.funcao == FUNCAO and DIA in r.dia_da_semana:
            if r.nome in nomes_vistos:
                continue
            nomes_vistos.add(r.nome)
            grupo.append(r)

    bp_log = carregar_bp_log(bp_log_raw)
    zumbis = carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO)

    # So o 1o domingo de cada mes -- e quando a Ceia do Senhor acontece.
    linhas_agenda: list[tuple[int, date, str]] = []
    for row_i, row in enumerate(agenda_raw[1:], start=1):
        dia = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if DIA not in dia:
            continue
        d = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if d is None:
            continue
        if week_of_month(d) != 1:
            continue
        linhas_agenda.append((row_i, d, get(row, idx, COL_NOME).strip()))
    linhas_agenda.sort(key=lambda t: t[1])

    if not linhas_agenda:
        print("Nenhum 1o domingo do mes encontrado na sheet. Fim.")
        return

    valor_por_data = {d: m for _, d, m in linhas_agenda}
    row_por_data = {d: row_i for row_i, d, _ in linhas_agenda}
    n_ativos = len(grupo)

    todas_as_datas = [d for _, d, _ in linhas_agenda]
    restantes = todas_as_datas[:]
    blocos: list[list[date]] = []
    while restantes:
        bloco = delimitar_uma_ronda(restantes, n_colaboradores_ativos=n_ativos)
        if not bloco:
            break
        blocos.append(bloco)
        restantes = [d for d in restantes if d > bloco[-1]]

    estado = EstadoExecucaoGrupo(historico_total={}, zumbis_prioritarios=zumbis)

    def processar_bloco(datas: list[date]) -> list:
        slots = [
            montar_slot(agenda_raw[row_por_data[d]], idx, row_por_data[d], d)
            for d in datas
        ]
        meses_tocados = len({s.mes_key for s in slots})
        demanda = calcular_demanda_onda_expansiva(
            grupo, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
        )
        return alocar_grupo(
            grupo, slots, estado, demanda.mapa_limites_locais,
            excluse_header=excluse_header, excluse_rows=excluse_rows,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            aniversarios=aniversarios,
        )

    ronda_para_escrever: list[date] | None = None
    for bloco in blocos:
        fechada = all(valor_por_data[d] for d in bloco)
        if fechada:
            # Replay: alimenta o rodizio (CEIA ALTERNADA exclui o vencedor
            # do mes anterior) sem escrever nada de volta.
            processar_bloco(bloco)
            continue
        ronda_para_escrever = bloco
        break

    if ronda_para_escrever is None:
        print("Nenhuma Ronda com CEIA vazia encontrada (tudo ja preenchido ate onde ha dados). Fim.")
        return

    print(f"N (colaboradores ativos no grupo) = {n_ativos}")
    print(f"Ronda a escrever: {len(ronda_para_escrever)} 1o-domingo(s) do mes "
          f"({ronda_para_escrever[0]} a {ronda_para_escrever[-1]})\n")

    decisoes = processar_bloco(ronda_para_escrever)

    print(f"Escrevendo {DEPARTAMENTO}/{FUNCAO}/{DIA} na coluna "
          f"CEIA (col {col_ceia + 1}) de {AGENDA_TITLE}...\n")

    updates: list[tuple[int, int, str]] = []
    for d in decisoes:
        if valor_por_data[d.slot.data]:
            print(f"  {d.slot.data} -> ja preenchida na sheet, nao escrita (esperado apenas se a Ronda ja estava fechada)")
            continue
        linha_sheet = d.slot.row_index + 1  # +1: header ocupa a linha 1
        if d.vencedor is None:
            updates.append((linha_sheet, col_ceia + 1, "SEM ALOCAÇÃO"))
            print(f"  {d.slot.data} -> SEM ALOCAÇÃO (linha {linha_sheet})")
            continue
        updates.append((linha_sheet, col_ceia + 1, d.vencedor))
        print(f"  {d.slot.data} -> {d.vencedor} ({d.motivo}) (linha {linha_sheet})")

    guard.batch_update_cells(AGENDA_TITLE, updates)

    print(f"\n{len(updates)} celula(s) escrita(s) em lote (1 requisicao de API). Apenas a coluna"
          " CEIA foi escrita.")


if __name__ == "__main__":
    main()
