# -*- coding: utf-8 -*-
"""Preenche a coluna AUXILIAR da CLAUDE_AppAnualGlobal (D. AUXILIAR / AUXILIAR
/ DOMINGO) com EXATAMENTE UMA Ronda (ciclo completo) por execucao -- nunca
mais de uma. Respeita qualquer alocacao ja existente na coluna AUXILIAR (nao
sobrescreve) e comeca a proxima Ronda a partir do primeiro domingo futuro
ainda vazio; para rodar a Ronda seguinte, execute o script de novo.

Irmao de `preencher_claude_appanualglobal_domingo.py` (D. MINISTROS/MINISTRO/
DOMINGO) -- mesmo padrao de "replay das Rondas ja fechadas + escreve so a
primeira Ronda aberta", mesmo mecanismo de CEIA ALTERNADA (que aqui tambem se
aplica: varios colaboradores AUXILIAR/DOMINGO tem `CEIA ALTERNADA=TRUE`
cadastrado, entao `alocar_grupo` entra sozinho no algoritmo em 4 fases -- ver
CONCEITO_CEIA_ALTERNADA.md) e mesmo descanso minimo cruzado com a
quarta-feira. Nao ha compatibilidade de TEMA aqui -- esse conceito (aba
"Livros") e exclusivo de D. MINISTROS/MINISTRO.

Diferenca pedida pelo Clayton, 2026-09-11: D. AUXILIAR tem uma coluna extra
em BP ALGORITIMO, "ATRIBUIR AOS RECADOS". Sempre que o vencedor de um slot
tem essa marcacao TRUE, o MESMO colaborador tambem e escrito na coluna
RECADOS (e "EMAIL RECADOS") daquela mesma linha/data -- alem de AUXILIAR e
"EMAIL AUXILIAR". Quando a marcacao e FALSE (ou nao ha vencedor), a coluna
RECADOS nao e tocada. Confirmado que "D. RECADOS" em BP ALGORITIMO nao e um
processo proprio (todas as linhas de lá tem FUNÇÃO/DIA DA SEMANA em branco,
ignoradas por `carregar_regras_colaboradores`) -- RECADOS so e preenchida por
este mecanismo, nunca por um grupo/processo independente.

Email automatico (mesmo padrao dos demais processos, pedido do Clayton,
2026-09-11): o email de quem e escrito em AUXILIAR vai para "EMAIL AUXILIAR"
e o de quem e escrito em RECADOS vai para "EMAIL RECADOS", ambos casados por
NOME na aba "BP SERVICE".

Escreve exclusivamente na copia CLAUDE_AppAnualGlobal (guard bloqueia
qualquer tentativa em aba sem o prefixo).
"""
from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.carregamento import (
    build_header_index, carregar_aniversarios, carregar_bp_log,
    carregar_compromissos_cruzados, carregar_emails, carregar_excluse_matriz,
    carregar_regras_colaboradores, carregar_zumbis_prioritarios,
    extrair_assiduidade_da_linha, extrair_papeis_da_linha, get,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.models import SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo, alocar_grupo, calcular_demanda_onda_expansiva,
    delimitar_uma_ronda, filtrar_slots_ja_preenchidos,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month, month_key, parse_date_ddmmyyyy, week_of_month,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

DEPARTAMENTO, FUNCAO, DIA = "D. AUXILIAR", "AUXILIAR", "DOMINGO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
COL_NOME = "AUXILIAR"
COL_RECADOS = "RECADOS"


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=d,
        dia_da_semana=DIA,
        tema="",  # AUXILIAR nao tem conceito de tema (exclusivo de MINISTRO)
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
    # Email automatico (pedido do Clayton, 2026-09-11): quem for escrito em
    # AUXILIAR tem o email escrito em "EMAIL AUXILIAR", e quem for escrito em
    # RECADOS tem o email escrito em "EMAIL RECADOS", casados por NOME em
    # BP SERVICE.
    emails = carregar_emails(bp_service_raw)
    # Descanso minimo cruzado (mesmo mecanismo do irmao D. MINISTROS/MINISTRO):
    # o mesmo colaborador nao pode ser AUXILIAR num domingo e de novo, poucos
    # dias depois (ou antes), na quarta-feira.
    compromissos_cruzados = carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA)

    idx = build_header_index(agenda_raw[0])
    col_auxiliar = idx[COL_NOME]
    col_email = idx["EMAIL " + COL_NOME]
    col_recados = idx[COL_RECADOS]
    col_email_recados = idx["EMAIL " + COL_RECADOS]

    regras = carregar_regras_colaboradores(regras_raw)
    nomes_vistos: set[str] = set()
    grupo = []
    for r in regras:
        if r.departamento == DEPARTAMENTO and r.funcao == FUNCAO and DIA in r.dia_da_semana:
            if r.nome in nomes_vistos:
                continue
            nomes_vistos.add(r.nome)
            grupo.append(r)
    # Pedido do Clayton (2026-09-11): consultar ATRIBUIR AOS RECADOS de quem
    # vence cada slot -- ver `RegraColaborador.atribuir_aos_recados`.
    regras_por_nome = {r.nome: r for r in grupo}

    bp_log = carregar_bp_log(bp_log_raw)
    zumbis = carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO)

    # Todos os domingos do grupo na sheet (passado e futuro), com o valor
    # AUXILIAR atual -- preenchido (Ronda ja fechada) ou vazio.
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

    def processar_bloco(
        datas: list[date], aplicar_cruzados: bool = False, ronda_aberta: bool = False,
    ) -> list:
        slots = [
            montar_slot(agenda_raw[row_por_data[d]], idx, row_por_data[d], d)
            for d in datas
        ]
        if ronda_aberta:
            # Regra global (ver motor.filtrar_slots_ja_preenchidos): datas ja
            # preenchidas dentro da Ronda aberta (ex.: feriado marcado a
            # mao) nao contam como vaga real -- nunca aplicar no replay de
            # uma Ronda fechada.
            slots = filtrar_slots_ja_preenchidos(slots, valor_por_data)
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
            # rodizio -- nao escreve nada de volta. Nao aplica o descanso
            # minimo cruzado aqui (mesmo motivo do irmao MINISTRO/DOMINGO):
            # `compromissos_cruzados` reflete o estado ATUAL inteiro da
            # sheet, entao usa-lo no replay quebraria a premissa de que ele
            # reproduz exatamente o que ja foi gravado.
            processar_bloco(bloco, aplicar_cruzados=False)
            continue
        ronda_para_escrever = bloco
        break

    if ronda_para_escrever is None:
        print("Nenhuma Ronda com domingos vazios encontrada (tudo ja preenchido ate onde ha dados). Fim.")
        return

    print(f"N (colaboradores ativos no grupo) = {n_ativos}")
    print(f"Ronda a escrever: {len(ronda_para_escrever)} domingos "
          f"({ronda_para_escrever[0]} a {ronda_para_escrever[-1]})\n")

    decisoes = processar_bloco(ronda_para_escrever, aplicar_cruzados=True, ronda_aberta=True)

    print(f"Escrevendo {DEPARTAMENTO}/{FUNCAO}/{DIA} na coluna "
          f"AUXILIAR (col {col_auxiliar + 1}) de {AGENDA_TITLE}...\n")

    updates: list[tuple[int, int, str]] = []
    for d in decisoes:
        if valor_por_data[d.slot.data]:
            print(f"  {d.slot.data} -> ja preenchida na sheet, nao escrita (esperado apenas se a Ronda ja estava fechada)")
            continue
        linha_sheet = d.slot.row_index + 1  # +1: header ocupa a linha 1
        if d.vencedor is None:
            updates.append((linha_sheet, col_auxiliar + 1, "SEM ALOCAÇÃO"))
            updates.append((linha_sheet, col_email + 1, ""))
            print(f"  {d.slot.data} -> SEM ALOCAÇÃO (linha {linha_sheet})")
            continue
        email = emails.get(d.vencedor.strip().upper(), "")
        updates.append((linha_sheet, col_auxiliar + 1, d.vencedor))
        updates.append((linha_sheet, col_email + 1, email))
        info_recados = ""
        regra_vencedor = regras_por_nome.get(d.vencedor)
        if regra_vencedor is not None and regra_vencedor.atribuir_aos_recados:
            updates.append((linha_sheet, col_recados + 1, d.vencedor))
            updates.append((linha_sheet, col_email_recados + 1, email))
            info_recados = " [+ RECADOS]"
        print(f"  {d.slot.data} -> {d.vencedor} ({d.motivo}) (linha {linha_sheet}) "
              f"[EMAIL AUXILIAR={email or '(sem email cadastrado)'}]{info_recados}")

    guard.batch_update_cells(AGENDA_TITLE, updates)

    print(f"\n{len(updates)} celula(s) escrita(s) em lote (1 requisicao de API). Colunas"
          " AUXILIAR, EMAIL AUXILIAR e (quando aplicavel) RECADOS/EMAIL RECADOS foram escritas.")


if __name__ == "__main__":
    main()
