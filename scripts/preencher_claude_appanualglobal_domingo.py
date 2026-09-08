# -*- coding: utf-8 -*-
"""Preenche a coluna MINISTRO da CLAUDE_AppAnualGlobal (D. MINISTROS / MINISTRO
/ DOMINGO) com EXATAMENTE UMA Ronda (ciclo completo) por execucao -- nunca
mais de uma. Respeita qualquer alocacao ja existente na coluna MINISTRO (nao
sobrescreve) e comeca a proxima Ronda a partir do primeiro domingo futuro
ainda vazio; para rodar a Ronda seguinte, execute o script de novo.

Correcao 2026-09-07 (pedido do Clayton): cada execucao roda num processo
separado e o `EstadoExecucaoGrupo` comecava sempre vazio, entao o rodizio
completo da CEIA ALTERNADA e do PREENCHIMENTO DE LACUNA nao enxergava as
Rondas ja gravadas na sheet -- toda Ronda nova recomecava do topo da
hierarquia. Agora o script reconstroi a sequencia de Rondas ja fechadas
(todas com MINISTRO preenchido) a partir da propria sheet e faz o "replay"
delas em ordem cronologica sobre o MESMO `estado`, sem escrever nada de
volta -- so para semear o historico real -- antes de calcular e escrever a
proxima Ronda (a primeira que ainda tiver domingos vazios).

So escreve na coluna MINISTRO -- a coluna CEIA pertence a outro grupo
(FUNCAO="CEIA" em BP ALGORITIMO, ainda nao processado nesta sessao) e fica
intocada de proposito.

Escreve exclusivamente na copia CLAUDE_AppAnualGlobal (guard bloqueia
qualquer tentativa em aba sem o prefixo).

Correcao 2026-09-07 (pedido do Clayton, caso real: Patricia Lopes nasceu em
25/10 e havia sido alocada em 25/10/2026): le tambem a aba "BP SERVICE"
(coluna DATA NASCIMENTO, casada por NOME) para bloquear qualquer
aniversariante de ser alocado no proprio dia -- ver `esta_bloqueado_por_
aniversario` em motor.py.

Correcao 2026-09-08 (pedido do Clayton: "e so para a quarta-feira seguir o
tema, aos domingos e tema livre"): removida toda a leitura/calculo de TEMA
(aba "Livros", `montar_requisito_tema_por_slot`) deste script -- domingo
nunca teve essa restricao de verdade (`is_tema_compativel` em motor.py ja
libera qualquer dia da semana que nao seja QUARTA-FEIRA), so nao fazia
sentido continuar carregando e calculando algo que nunca e usado aqui. A
logica de tema completa (coluna certa "TEMA", nao "TEMA DA MINISTRAÇÃO")
agora vive so em `preencher_claude_appanualglobal_quarta.py`.
"""
from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.carregamento import (
    build_header_index, carregar_aniversarios, carregar_bp_log,
    carregar_compromissos_cruzados, carregar_excluse_matriz,
    carregar_regras_colaboradores, carregar_zumbis_prioritarios,
    extrair_assiduidade_da_linha, extrair_papeis_da_linha, get,
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

DEPARTAMENTO, FUNCAO, DIA = "D. MINISTROS", "MINISTRO", "DOMINGO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
COL_NOME = "MINISTRO"


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=d,
        dia_da_semana=DIA,
        # Tema livre aos domingos (pedido do Clayton, 2026-09-08) -- nunca
        # lido nem exigido aqui, so QUARTA-FEIRA tem essa restricao.
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

    regras_raw = guard.read_worksheet("CLAUDE_BP ALGORITIMO")
    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    excluse_raw = guard.read_worksheet("Excluse")
    excluse_header, excluse_rows = carregar_excluse_matriz(excluse_raw)
    bp_log_raw = guard.read_worksheet("BP LOG")
    bp_service_raw = guard.read_worksheet("BP SERVICE")
    aniversarios = carregar_aniversarios(bp_service_raw)
    # Descanso minimo cruzado (2026-09-08, pedido do Clayton): a mesma
    # pessoa nao pode ser MINISTRO num domingo e de novo, poucos dias
    # depois (ou antes), na quarta-feira -- ver `esta_bloqueado_por_
    # descanso_cruzado` em motor.py. So afeta Rondas futuras ainda nao
    # escritas (uma Ronda ja gravada nunca e recalculada por este script).
    compromissos_cruzados = carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA)

    idx = build_header_index(agenda_raw[0])
    col_ministro = idx[COL_NOME]

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

    # Todos os domingos do grupo na sheet (passado e futuro), com o valor
    # MINISTRO atual -- preenchido (Ronda ja fechada) ou vazio.
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

    if not linhas_agenda:
        print("Nenhum domingo encontrado na sheet. Fim.")
        return

    valor_por_data = {d: m for _, d, m in linhas_agenda}
    row_por_data = {d: row_i for row_i, d, _ in linhas_agenda}
    n_ativos = len(grupo)

    # Recorta a sequencia inteira de Rondas (blocos de n_ativos domingos,
    # estendidos ate fechar o mes) na ordem em que foram/serao preenchidas.
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

    def processar_bloco(datas: list[date], aplicar_cruzados: bool = False) -> list:
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
            compromissos_cruzados=compromissos_cruzados if aplicar_cruzados else None,
            aniversarios=aniversarios,
        )

    ronda_para_escrever: list[date] | None = None
    for bloco in blocos:
        fechada = all(valor_por_data[d] for d in bloco)
        if fechada:
            # Replay: reproduz a Ronda ja gravada so para alimentar o
            # rodizio (historico_vencedores_ceia/lacuna, cotas, descanso
            # minimo etc.) -- nao escreve nada de volta. NAO aplica o
            # descanso minimo cruzado aqui (2026-09-08, descoberto ao
            # verificar): `compromissos_cruzados` reflete o estado ATUAL
            # inteiro da sheet (inclusive quartas-feiras escritas depois
            # desta Ronda ja ter sido fechada), entao usa-lo no replay
            # faria o algoritmo "reinventar" um vencedor diferente do que
            # ja esta gravado -- quebrando a premissa do replay (mesmos
            # inputs de entao => mesma saida) e corrompendo o historico/
            # rodizio reconstruido. So se aplica ao calculo da Ronda que
            # sera de fato escrita agora.
            processar_bloco(bloco, aplicar_cruzados=False)
            continue
        # Primeira Ronda com pelo menos um domingo vazio: e a que sera
        # calculada e escrita nesta execucao.
        ronda_para_escrever = bloco
        break

    if ronda_para_escrever is None:
        print("Nenhuma Ronda com domingos vazios encontrada (tudo ja preenchido ate onde ha dados). Fim.")
        return

    print(f"N (colaboradores ativos no grupo) = {n_ativos}")
    print(f"Ronda a escrever: {len(ronda_para_escrever)} domingos "
          f"({ronda_para_escrever[0]} a {ronda_para_escrever[-1]})\n")

    decisoes = processar_bloco(ronda_para_escrever, aplicar_cruzados=True)

    print(f"Escrevendo {DEPARTAMENTO}/{FUNCAO}/{DIA} na coluna "
          f"MINISTRO (col {col_ministro + 1}) de {AGENDA_TITLE}...\n")

    # Acumula todas as celulas da Ronda e escreve numa UNICA chamada de API
    # (2026-09-08, pedido do Clayton para economizar cota depois de bater em
    # rate limit rodando Rondas em sequencia) em vez de uma requisicao por
    # celula.
    updates: list[tuple[int, int, str]] = []
    for d in decisoes:
        if valor_por_data[d.slot.data]:
            print(f"  {d.slot.data} -> ja preenchida na sheet, nao escrita (esperado apenas se a Ronda ja estava fechada)")
            continue
        linha_sheet = d.slot.row_index + 1  # +1: header ocupa a linha 1
        if d.vencedor is None:
            # Pedido do Clayton (2026-09-07): "SEM ALOCAÇÃO" tambem precisa
            # ser escrito na celula (nao deixar em branco) -- e o resultado
            # correto quando e genuinamente impossivel alocar, nao uma
            # omissao do script.
            updates.append((linha_sheet, col_ministro + 1, "SEM ALOCAÇÃO"))
            print(f"  {d.slot.data} -> SEM ALOCAÇÃO (linha {linha_sheet})")
            continue
        updates.append((linha_sheet, col_ministro + 1, d.vencedor))
        print(f"  {d.slot.data} -> {d.vencedor} ({d.motivo}) (linha {linha_sheet})")

    guard.batch_update_cells(AGENDA_TITLE, updates)

    print(f"\n{len(updates)} celula(s) escrita(s) em lote (1 requisicao de API). Apenas a coluna"
          " MINISTRO foi escrita -- CEIA nao foi tocada (pertence a outro grupo/FUNCAO ainda"
          " nao processado).")


if __name__ == "__main__":
    main()
