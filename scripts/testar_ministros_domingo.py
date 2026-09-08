"""Teste de integracao real (proposta F) para o grupo D. MINISTROS /
MINISTRO / DOMINGO, a partir de outubro/2026.

Diferente de `testar_ministros_quarta.py`, este script NAO duplica as abas
originais de novo -- reaproveita as copias `CLAUDE_BP ALGORITIMO` /
`CLAUDE_AppAnualGlobal` ja existentes (criadas pelo teste de quarta-feira),
para nao perder o resultado ja gravado la. So escreve em abas `CLAUDE_*`.

Uso:
    uv run python scripts/testar_ministros_domingo.py
"""

from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.auditoria import (
    CABECALHO_AUDITORIA,
    NOME_ABA_AUDITORIA,
    construir_linhas_auditoria,
)
from pastoreio_orquestrador.carregamento import (
    build_header_index,
    carregar_bp_log,
    carregar_excluse_matriz,
    carregar_historico_alocacoes,
    carregar_regras_colaboradores,
    carregar_temas,
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
DIA_DA_SEMANA = "DOMINGO"
COL_NOME = "MINISTRO"
COL_TEMA = "TEMA DA MINISTRAÇÃO"
INICIO = date(2026, 10, 1)

TITULO_BP_ALGORITIMO = "CLAUDE_BP ALGORITIMO"
TITULO_APP_ANUAL_GLOBAL = "CLAUDE_AppAnualGlobal"


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)

    titulos = guard.list_worksheet_titles()
    for titulo in (TITULO_BP_ALGORITIMO, TITULO_APP_ANUAL_GLOBAL):
        if titulo not in titulos:
            raise RuntimeError(
                f"'{titulo}' nao existe. Rode primeiro um teste que a crie "
                f"(ex.: scripts/testar_ministros_quarta.py) antes deste."
            )

    print(f"Reaproveitando copias de teste existentes: '{TITULO_BP_ALGORITIMO}' e '{TITULO_APP_ANUAL_GLOBAL}'.")

    regras_raw = guard.read_worksheet(TITULO_BP_ALGORITIMO)
    agenda_raw = guard.read_worksheet(TITULO_APP_ANUAL_GLOBAL)
    livros_raw = guard.read_worksheet("Livros")  # leitura, aba original OK
    excluse_raw = guard.read_worksheet("Excluse")  # leitura, aba original OK
    excluse_header, excluse_rows = carregar_excluse_matriz(excluse_raw)
    bp_log_raw = guard.read_worksheet("BP LOG")  # leitura, aba original OK
    log_alg_raw = guard.read_worksheet("LOG ALGORITIMO")  # leitura, aba original OK

    regras = carregar_regras_colaboradores(regras_raw)
    grupo = [
        r for r in regras
        if r.departamento == DEPARTAMENTO and r.funcao == FUNCAO and DIA_DA_SEMANA in r.dia_da_semana
    ]
    print(f"\nRegras ativas no grupo {DEPARTAMENTO}/{FUNCAO}/{DIA_DA_SEMANA}: {len(grupo)}")
    for r in grupo:
        print(f"  - {r.nome}")

    idx_agenda = build_header_index(agenda_raw[0])

    slots: list[SlotAgenda] = []
    for row_i, row in enumerate(agenda_raw[1:], start=1):
        dia = get(row, idx_agenda, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if DIA_DA_SEMANA not in dia:
            continue
        data_txt = get(row, idx_agenda, ColAppAnualGlobal.DATA).strip()
        d = parse_date_ddmmyyyy(data_txt)
        if d is None or d < INICIO:
            continue
        valor_atual = get(row, idx_agenda, COL_NOME).strip()
        if valor_atual:
            continue  # respeita alocacoes ja existentes na copia de teste

        slot = SlotAgenda(
            row_index=row_i,
            data=d,
            dia_da_semana=dia,
            tema=get(row, idx_agenda, COL_TEMA).strip(),
            mes_key=month_key(d),
            semana_do_mes=week_of_month(d),
            is_ultima_ocorrencia_do_mes=is_last_occurrence_of_month(d),
            assiduidade=extrair_assiduidade_da_linha(row, idx_agenda),
            papeis=extrair_papeis_da_linha(row, idx_agenda),
        )
        slots.append(slot)

    print(f"Slots de {DIA_DA_SEMANA} a partir de {INICIO.isoformat()}, vazios: {len(slots)}")
    if not slots:
        print("Nada para alocar (sem slots vazios no periodo). Fim.")
        return

    meses_tocados = len({s.mes_key for s in slots})
    demanda = calcular_demanda_onda_expansiva(grupo, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados)
    print(
        f"\nDemanda: capacidade_base={demanda.capacidade_base} "
        f"capacidade_total={demanda.capacidade_total} "
        f"demanda_calculada={demanda.demanda_calculada} "
        f"usa_cota_extra={demanda.usa_cota_extra}"
    )

    temas_livros = carregar_temas(livros_raw)
    requisitos_tema = montar_requisito_tema_por_slot(slots, temas_livros)

    bp_log = carregar_bp_log(bp_log_raw)
    historico_total = carregar_historico_alocacoes(log_alg_raw, FUNCAO)
    zumbis = carregar_zumbis_prioritarios(bp_log, DEPARTAMENTO, FUNCAO)
    print(f"\nHistorico real carregado: {len(historico_total)} colaboradores com alocacoes passadas")
    print(f"Zumbis prioritarios (BP LOG, ainda pendentes de recuperacao): {sorted(zumbis)}")

    estado = EstadoExecucaoGrupo(historico_total=historico_total, zumbis_prioritarios=zumbis)
    decisoes = alocar_grupo(
        grupo, slots, estado, demanda.mapa_limites_locais,
        requisitos_tema_por_slot=requisitos_tema,
        excluse_header=excluse_header, excluse_rows=excluse_rows,
    )

    print("\nDecisoes propostas:")
    for d in decisoes:
        if d.sem_alocacao:
            print(f"  {d.slot.data} (tema={d.slot.tema!r}) -> SEM ALOCAÇÃO")
        else:
            req = requisitos_tema.get(d.slot.row_index, "-")
            print(f"  {d.slot.data} (tema={d.slot.tema!r}, requisito={req}) -> {d.vencedor} [{d.motivo}]")

    print(f"\nEscrevendo resultado em '{TITULO_APP_ANUAL_GLOBAL}' (copia de teste)...")
    idx_col_nome = idx_agenda[COL_NOME] + 1  # gspread e 1-based
    for d in decisoes:
        if d.vencedor is None:
            continue
        linha_sheet = d.slot.row_index + 1  # row_index=1 (1a linha de dados) -> linha 2 na sheet (apos cabecalho)
        guard.update_cell(TITULO_APP_ANUAL_GLOBAL, linha_sheet, idx_col_nome, d.vencedor)

    print(f"\nRegistando auditoria em '{NOME_ABA_AUDITORIA}'...")
    guard.ensure_worksheet_with_header(NOME_ABA_AUDITORIA, CABECALHO_AUDITORIA)
    linhas_auditoria = construir_linhas_auditoria(
        decisoes,
        grupo_label=f"{DEPARTAMENTO}/{FUNCAO}/{DIA_DA_SEMANA}",
        requisitos_tema_por_slot=requisitos_tema,
    )
    for linha in linhas_auditoria:
        guard.append_row(NOME_ABA_AUDITORIA, linha)

    print("Concluido. Nenhuma aba original foi alterada.")


if __name__ == "__main__":
    main()
