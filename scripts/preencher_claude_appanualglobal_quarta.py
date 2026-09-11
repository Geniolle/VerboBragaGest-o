# -*- coding: utf-8 -*-
"""Preenche a coluna MINISTRO da CLAUDE_AppAnualGlobal (D. MINISTROS / MINISTRO
/ QUARTA-FEIRA) com EXATAMENTE UMA Ronda (ciclo completo) por execucao -- nunca
mais de uma. Respeita qualquer alocacao ja existente na coluna MINISTRO (nao
sobrescreve) e comeca a proxima Ronda a partir da primeira quarta-feira futura
ainda vazia; para rodar a Ronda seguinte, execute o script de novo.

Irmao de `preencher_claude_appanualglobal_domingo.py` -- mesmo padrao de
"replay das Rondas ja fechadas + escreve so a primeira Ronda aberta" -- mas
para D. MINISTROS/MINISTRO/QUARTA-FEIRA em vez de DOMINGO. Diferencas em
relacao ao irmao DOMINGO (pedido do Clayton, 2026-09-07):

  - Nao existe o conceito CEIA ALTERNADA na quarta-feira (todas as 15 regras
    do grupo tem `ceia_alternada=False`) -- e estrutural: `alocar_grupo` em
    motor.py so entra no algoritmo em fases quando
    `eh_grupo_domingo and usa_ceia_alternada`, e `eh_grupo_domingo` exige
    "DOMINGO" no `dia_da_semana` do slot, o que nunca ocorre aqui. Ou seja,
    este grupo cai sempre no caminho cronologico simples de `alocar_grupo`,
    sem precisar de nenhum parametro/flag extra para "desligar" a CEIA.
  - A validacao NOVA que a quarta-feira tem e o DOMINGO nao: compatibilidade
    de TEMA (coluna "TEMA" em AppAnualGlobal -- o nome do livro/tema do
    trimestre, ex.: "VIDA DE LOUVOR", "ALIANÇA DE SANGUE" -- vs. P1/P2/P3 de
    cada colaborador, classificados a partir da aba "Livros") -- so existe
    para QUARTA-FEIRA (`is_tema_compativel` em motor.py sempre libera
    qualquer outro dia da semana; por pedido explicito do Clayton em
    2026-09-08, o script do DOMINGO nem chama mais essa logica, "e so para
    a quarta-feira seguir o tema, aos domingos e tema livre").
  - CORRECAO 2026-09-08 (pedido do Clayton): a coluna certa e "TEMA", nao
    "TEMA DA MINISTRAÇÃO" (um campo de texto livre para o titulo especifico
    da pregacao daquela semana, quase sempre vazio -- usa-lo desligava
    silenciosamente o filtro de compatibilidade, mesmo com "TEMA" totalmente
    preenchido na sheet para o ano inteiro). Ver `montar_slot` abaixo.

Validado do zero (pedido explicito do Clayton, 2026-09-07: "Utilize o CLAUDE_
quero validar do zero") -- NAO sincroniza CLAUDE_AppAnualGlobal com a aba real
antes de rodar; a copia CLAUDE_ e tratada como sandbox vazio a partir de
07/10/2026 no que toca a MINISTRO (nao tem nenhuma quarta-feira preenchida
nessa coluna), mas a coluna "TEMA" em si ja vinha preenchida para o ano
inteiro desde o inicio -- so nao estava sendo lida da coluna certa (ver
correcao acima).

So escreve na coluna MINISTRO. Escreve exclusivamente na copia
CLAUDE_AppAnualGlobal (guard bloqueia qualquer tentativa em aba sem o
prefixo).

Email automatico (pedido do Clayton, 2026-09-11): sempre que um nome e
escrito na coluna MINISTRO, o email correspondente (aba "BP SERVICE",
coluna EMAIL, casado por NOME) e escrito junto na coluna "EMAIL MINISTRO"
-- o padrao e sempre "EMAIL <nome da coluna de alocacao>". Nomes sem email
cadastrado (ex.: placeholders como "Culto de Oração") ficam com a celula de
email em branco, sem erro.
"""
from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.carregamento import (
    build_header_index, carregar_aniversarios, carregar_bp_log,
    carregar_compromissos_cruzados, carregar_emails, carregar_excluse_matriz,
    carregar_regras_colaboradores, carregar_temas,
    carregar_zumbis_prioritarios, extrair_assiduidade_da_linha,
    extrair_papeis_da_linha, get,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.models import SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo, alocar_grupo, calcular_demanda_onda_expansiva,
    delimitar_uma_ronda, montar_requisito_tema_por_slot,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month, month_key, parse_date_ddmmyyyy, week_of_month,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

DEPARTAMENTO, FUNCAO, DIA = "D. MINISTROS", "MINISTRO", "QUARTA-FEIRA"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
COL_NOME = "MINISTRO"


def montar_slot(row: list[str], idx: dict[str, int], row_i: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_i,
        data=d,
        dia_da_semana=DIA,
        # Correcao 2026-09-08 (pedido do Clayton): a coluna que precisa ser
        # lida e "TEMA" (o nome do livro/tema do trimestre, ex.: "VIDA DE
        # LOUVOR", "ALIANÇA DE SANGUE" -- e o que bate literalmente com a
        # coluna TEMA da aba Livros e alimenta `montar_requisito_tema_por_
        # slot`), NAO "TEMA DA MINISTRAÇÃO" (um campo de texto livre para o
        # titulo especifico da pregacao daquela semana, quase sempre vazio
        # -- usa-lo aqui desligava silenciosamente o filtro de
        # compatibilidade de tema P1/P2/P3 na pratica, mesmo com a coluna
        # certa totalmente preenchida na sheet).
        tema=get(row, idx, ColAppAnualGlobal.TEMA).strip(),
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
    livros_raw = guard.read_worksheet("Livros")
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
    # descanso_cruzado` em motor.py. Le TODOS os dias da semana diferentes
    # de QUARTA-FEIRA (na pratica, so DOMINGO existe hoje para MINISTRO).
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

    temas_livros = carregar_temas(livros_raw)
    bp_log = carregar_bp_log(bp_log_raw)
    zumbis = carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO)

    # Todas as quartas-feiras do grupo na sheet (passado e futuro), com o
    # valor MINISTRO atual -- preenchido (Ronda ja fechada) ou vazio.
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
        print("Nenhuma quarta-feira encontrada na sheet. Fim.")
        return

    valor_por_data = {d: m for _, d, m in linhas_agenda}
    row_por_data = {d: row_i for row_i, d, _ in linhas_agenda}
    n_ativos = len(grupo)

    # Recorta a sequencia inteira de Rondas (blocos de n_ativos quartas,
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
        requisitos_tema = montar_requisito_tema_por_slot(slots, temas_livros)
        meses_tocados = len({s.mes_key for s in slots})
        demanda = calcular_demanda_onda_expansiva(
            grupo, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
        )
        return alocar_grupo(
            grupo, slots, estado, demanda.mapa_limites_locais,
            requisitos_tema_por_slot=requisitos_tema,
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
            # descanso minimo cruzado aqui (2026-09-08, mesmo motivo do
            # irmao DOMINGO): `compromissos_cruzados` reflete o estado
            # ATUAL inteiro da sheet, entao usa-lo no replay quebraria a
            # premissa de que o replay reproduz exatamente o que ja foi
            # gravado. So se aplica ao calculo da Ronda que sera escrita
            # agora.
            processar_bloco(bloco, aplicar_cruzados=False)
            continue
        # Primeira Ronda com pelo menos uma quarta vazia: e a que sera
        # calculada e escrita nesta execucao.
        ronda_para_escrever = bloco
        break

    if ronda_para_escrever is None:
        print("Nenhuma Ronda com quartas vazias encontrada (tudo ja preenchido ate onde ha dados). Fim.")
        return

    print(f"N (colaboradores ativos no grupo) = {n_ativos}")
    print(f"Ronda a escrever: {len(ronda_para_escrever)} quartas-feiras "
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
            # Mesmo criterio ja validado no script do DOMINGO (pedido do
            # Clayton, 2026-09-07): "SEM ALOCAÇÃO" tambem precisa ser escrito
            # na celula (nao deixar em branco) quando e genuinamente
            # impossivel alocar.
            updates.append((linha_sheet, col_ministro + 1, "SEM ALOCAÇÃO"))
            updates.append((linha_sheet, col_email + 1, ""))
            print(f"  {d.slot.data} -> SEM ALOCAÇÃO (linha {linha_sheet})")
            continue
        email = emails.get(d.vencedor.strip().upper(), "")
        updates.append((linha_sheet, col_ministro + 1, d.vencedor))
        updates.append((linha_sheet, col_email + 1, email))
        print(f"  {d.slot.data} -> {d.vencedor} ({d.motivo}) (linha {linha_sheet}) "
              f"[EMAIL MINISTRO={email or '(sem email cadastrado)'}]")

    guard.batch_update_cells(AGENDA_TITLE, updates)

    print(f"\n{len(updates)} celula(s) escrita(s) em lote (1 requisicao de API)."
          " Colunas MINISTRO e EMAIL MINISTRO foram escritas.")


if __name__ == "__main__":
    main()
