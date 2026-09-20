# -*- coding: utf-8 -*-
"""Preenche a coluna MINISTRO da AppAnualGlobal/CLAUDE_AppAnualGlobal (D. MINISTROS / MINISTRO
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

Por padrao escreve na copia `CLAUDE_AppAnualGlobal`. Como DOMINGO ja foi
validado para produtivo, este mesmo script aceita `--produtivo`; nesse modo,
escreve em `AppAnualGlobal` e `LOG_AUDITORIA` por allowlist explicita no
SpreadsheetGuard. Os demais processos continuam bloqueados para escrita
produtiva ate serem promovidos separadamente.

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

Email automatico (pedido do Clayton, 2026-09-11): sempre que um nome e
escrito na coluna MINISTRO, o email correspondente (aba "BP SERVICE",
coluna EMAIL, casado por NOME) e escrito junto na coluna "EMAIL MINISTRO"
-- o padrao e sempre "EMAIL <nome da coluna de alocacao>". Nomes sem email
cadastrado (ex.: placeholders como "Culto de Oração") ficam com a celula de
email em branco, sem erro.
"""
from __future__ import annotations

import argparse
from datetime import date

from pastoreio_orquestrador.auditoria import (
    CABECALHO_AUDITORIA,
    construir_linhas_auditoria,
    resolver_ultimo_cursor_hierarquia,
)
from pastoreio_orquestrador.carregamento import (
    build_header_index, carregar_aniversarios, carregar_bp_log,
    carregar_compromissos_cruzados, carregar_emails, carregar_excluse_matriz,
    carregar_historico_ceia_persistido, carregar_regras_colaboradores, carregar_zumbis_prioritarios,
    contar_ocorrencias_mensais_por_colaborador,
    extrair_assiduidade_da_linha, extrair_papeis_da_linha, get,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.models import SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo, alocar_grupo, alocar_ronda_dinamica, calcular_demanda_onda_expansiva,
    delimitar_uma_ronda, filtrar_slots_ja_preenchidos,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month, month_key, parse_date_ddmmyyyy, week_of_month,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

DEPARTAMENTO, FUNCAO, DIA = "D. MINISTROS", "MINISTRO", "DOMINGO"
COL_NOME = "MINISTRO"

AGENDA_CLAUDE_TITLE = "CLAUDE_AppAnualGlobal"
BP_ALGORITMO_CLAUDE_TITLE = "CLAUDE_BP ALGORITIMO"
AUDITORIA_CLAUDE_TITLE = "CLAUDE_LOG_AUDITORIA"

AGENDA_PROD_TITLE = "AppAnualGlobal"
BP_ALGORITMO_PROD_TITLE = "BP ALGORITIMO"
AUDITORIA_PROD_TITLE = "LOG_AUDITORIA"


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
    parser = argparse.ArgumentParser(description="Preenche uma Ronda de DOMINGO.")
    parser.add_argument(
        "--produtivo",
        action="store_true",
        help="Escreve em AppAnualGlobal/LOG_AUDITORIA. Sem esta flag, usa CLAUDE_*.",
    )
    args = parser.parse_args()

    agenda_title = AGENDA_PROD_TITLE if args.produtivo else AGENDA_CLAUDE_TITLE
    bp_algoritmo_title = BP_ALGORITMO_PROD_TITLE if args.produtivo else BP_ALGORITMO_CLAUDE_TITLE
    auditoria_title = AUDITORIA_PROD_TITLE if args.produtivo else AUDITORIA_CLAUDE_TITLE
    writable_original_titles = {agenda_title, auditoria_title} if args.produtivo else set()

    settings = load_settings()
    data_corte_historico = settings.data_corte_historico
    guard = SpreadsheetGuard(
        settings,
        writable_original_titles=writable_original_titles,
    )

    modo = "PRODUTIVO" if args.produtivo else "CLAUDE"
    print(f"Modo de escrita: {modo}")
    print(f"Agenda: {agenda_title}")
    print(f"Auditoria: {auditoria_title}\n")
    print(f"DATA CORTE DO HISTORICO: {data_corte_historico.strftime('%d/%m/%Y')}")
    print("Estado rotacional anterior a data de corte sera ignorado.\n")

    regras_raw = guard.read_worksheet(bp_algoritmo_title)
    agenda_raw = guard.read_worksheet(agenda_title)
    titulos = set(guard.list_worksheet_titles())
    auditoria_raw = guard.read_worksheet(auditoria_title) if auditoria_title in titulos else []
    excluse_raw = guard.read_worksheet("Excluse")
    excluse_header, excluse_rows = carregar_excluse_matriz(excluse_raw)
    bp_log_raw = guard.read_worksheet("BP LOG")
    bp_service_raw = guard.read_worksheet("BP SERVICE")
    aniversarios = carregar_aniversarios(bp_service_raw)
    # Email automatico (pedido do Clayton, 2026-09-11): quem for escrito em
    # MINISTRO tem o email escrito em "EMAIL MINISTRO", casado por NOME em
    # BP SERVICE.
    emails = carregar_emails(bp_service_raw)
    # Descanso minimo cruzado (2026-09-08, pedido do Clayton): a mesma
    # pessoa nao pode ser MINISTRO num domingo e de novo, poucos dias
    # depois (ou antes), na quarta-feira -- ver `esta_bloqueado_por_
    # descanso_cruzado` em motor.py. So afeta Rondas futuras ainda nao
    # escritas (uma Ronda ja gravada nunca e recalculada por este script).
    compromissos_cruzados = carregar_compromissos_cruzados(agenda_raw, COL_NOME, DIA)

    idx = build_header_index(agenda_raw[0])
    col_ministro = idx[COL_NOME]
    col_email = idx["EMAIL " + COL_NOME]

    regras = carregar_regras_colaboradores(regras_raw)
    nomes_vistos: set[str] = set()
    grupo = []
    for r in regras:
        if r.departamento == DEPARTAMENTO and r.funcao == FUNCAO and DIA in r.dia_da_semana:
            if r.nome in nomes_vistos:
                continue
            nomes_vistos.add(r.nome)
            grupo.append(r)
    regras_por_nome = {r.nome.strip().upper(): r for r in grupo}
    ocorrencias_ceia_persistida = contar_ocorrencias_mensais_por_colaborador(
        agenda_raw,
        DIA,
        ("CEIA",),
        nomes_validos={nome: regra.nome for nome, regra in regras_por_nome.items()},
        data_corte_historico=data_corte_historico,
    )

    bp_log = carregar_bp_log(bp_log_raw)
    zumbis = carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO)
    cursor = resolver_ultimo_cursor_hierarquia(
        agenda_raw,
        auditoria_raw,
        grupo,
        DEPARTAMENTO,
        FUNCAO,
        DIA,
        COL_NOME,
        falhar_em_inconsistencia=not args.produtivo,
        data_corte_historico=data_corte_historico,
    )

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
    datas_rotacionais = [d for d in todas_as_datas if d >= data_corte_historico]
    if not datas_rotacionais:
        print("Nenhum domingo dentro do historico do novo motor. Fim.")
        return
    restantes = datas_rotacionais[:]
    blocos: list[list[date]] = []
    while restantes:
        bloco = delimitar_uma_ronda(restantes, n_colaboradores_ativos=n_ativos)
        if not bloco:
            break
        blocos.append(bloco)
        restantes = [d for d in restantes if d > bloco[-1]]

    estado = EstadoExecucaoGrupo(
        historico_total={},
        zumbis_prioritarios=zumbis,
        cursor_hierarquia=cursor.ancora,
    )

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
    if cursor.ancora:
        print("Continuidade da hierarquia:")
        print(f"  Ultima alocacao normal que consumiu a hierarquia: {cursor.ancora}.")
        print(f"  Posicao atual da ancora: {cursor.prioridade_ancora_atual}.")
        proximo_nome = cursor.proximo_candidato.nome if cursor.proximo_candidato else "(sem candidato)"
        print(f"  Proximo candidato inicial: {proximo_nome}.\n")
    else:
        print(
            "Continuidade da hierarquia: nenhuma ancora persistida valida apos a data de corte; "
            "inicio pela hierarquia atual.\n"
        )
    for diagnostico in cursor.diagnosticos:
        print(f"  Diagnostico cursor: {diagnostico}")
    if cursor.registros_ignorados_antes_corte:
        print(
            "  Diagnostico cursor: "
            f"{cursor.registros_ignorados_antes_corte} registro(s) rotacional(is) antes da data de corte ignorado(s)."
        )
    primeira_data_aberta = min(d for d in ronda_para_escrever if not valor_por_data[d])
    historico_ceia_persistido = carregar_historico_ceia_persistido(
        agenda_raw,
        auditoria_raw,
        dia_da_semana=DIA,
        coluna_alocacao=COL_NOME,
        nomes_validos={nome: regra.nome for nome, regra in regras_por_nome.items()},
        antes_de=primeira_data_aberta,
        data_corte_historico=data_corte_historico,
    )
    print(f"CEIA: historico considerado a partir de {data_corte_historico.strftime('%d/%m/%Y')}.")
    print(f"HIERARQUIA NORMAL: ancora considerada a partir de {data_corte_historico.strftime('%d/%m/%Y')}.\n")
    # O replay acima continua alimentando lacuna, cotas e descanso a partir
    # das Rondas fechadas. A CEIA historica, porem, vem dos vencedores reais
    # persistidos em agenda + auditoria, para que uma regra nova nunca
    # reescreva conceitualmente o passado nem duplique CEIAs ja gravadas.
    estado.historico_vencedores_ceia = historico_ceia_persistido
    # Para a hierarquia normal mensal, a fonte de verdade e agenda +
    # auditoria; portanto restauramos a ancora reconstruida antes de calcular
    # a Ronda aberta.
    estado.cursor_hierarquia = cursor.ancora
    estado.cursor_hierarquia_referencia = cursor.ancora
    estado.cursor_hierarquia_referencia_fixada = True
    estado.hierarquia_consumida_na_ronda.clear()
    estado.ocorrencias_mensais_externas = ocorrencias_ceia_persistida
    print(f"Ronda candidata inicial: {len(ronda_para_escrever)} domingos "
          f"({ronda_para_escrever[0]} a {ronda_para_escrever[-1]})\n")

    datas_abertas = [d for d in datas_rotacionais if d >= ronda_para_escrever[0]]
    slots_abertos = [
        montar_slot(agenda_raw[row_por_data[d]], idx, row_por_data[d], d)
        for d in datas_abertas
    ]
    slots_abertos = filtrar_slots_ja_preenchidos(slots_abertos, valor_por_data)

    def alocar_slots_dinamicos(slots: list[SlotAgenda], estado_exec: EstadoExecucaoGrupo) -> list:
        meses_tocados = len({s.mes_key for s in slots})
        demanda = calcular_demanda_onda_expansiva(
            grupo, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
        )
        return alocar_grupo(
            grupo, slots, estado_exec, demanda.mapa_limites_locais,
            excluse_header=excluse_header, excluse_rows=excluse_rows,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            compromissos_cruzados=compromissos_cruzados,
            aniversarios=aniversarios,
        )

    resultado_ronda = alocar_ronda_dinamica(
        grupo, slots_abertos, estado, n_ativos, alocar_slots_dinamicos
    )
    estado = resultado_ronda.estado
    decisoes = resultado_ronda.decisoes
    if resultado_ronda.eventos:
        print("Estado da Ronda:")
        for evento in resultado_ronda.eventos:
            print(f"  - {evento}")
        print()
    if resultado_ronda.diagnostico:
        print(f"Diagnostico controlado: {resultado_ronda.diagnostico}\n")

    print(f"Ronda a escrever: {len(resultado_ronda.slots)} domingos "
          f"({resultado_ronda.slots[0].data} a {resultado_ronda.slots[-1].data})\n")

    print(f"Escrevendo {DEPARTAMENTO}/{FUNCAO}/{DIA} na coluna "
          f"MINISTRO (col {col_ministro + 1}) de {agenda_title}...\n")

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
            updates.append((linha_sheet, col_email + 1, ""))
            print(f"  {d.slot.data} -> SEM ALOCAÇÃO (linha {linha_sheet})")
            continue
        email = emails.get(d.vencedor.strip().upper(), "")
        updates.append((linha_sheet, col_ministro + 1, d.vencedor))
        updates.append((linha_sheet, col_email + 1, email))
        print(f"  {d.slot.data} -> {d.vencedor} ({d.motivo}) (linha {linha_sheet}) "
              f"[EMAIL MINISTRO={email or '(sem email cadastrado)'}]")

    guard.batch_update_cells(agenda_title, updates)
    linhas_auditoria = construir_linhas_auditoria(
        decisoes,
        grupo_label=f"{DEPARTAMENTO}/{FUNCAO}/{DIA}",
        departamento=DEPARTAMENTO,
        funcao=FUNCAO,
        dia_da_semana_grupo=DIA,
        regras_por_nome=regras_por_nome,
    )
    if linhas_auditoria:
        guard.ensure_worksheet_with_header(auditoria_title, CABECALHO_AUDITORIA, rows=1000)
        guard.append_rows(auditoria_title, linhas_auditoria)

    print(f"\n{len(updates)} celula(s) escrita(s) em lote (1 requisicao de API). Colunas MINISTRO"
          " e EMAIL MINISTRO foram escritas -- CEIA nao foi tocada (pertence a outro grupo/FUNCAO).")
    print(f"{len(linhas_auditoria)} linha(s) adicionada(s) em {auditoria_title}.")


if __name__ == "__main__":
    main()
