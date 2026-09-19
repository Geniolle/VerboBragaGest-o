from datetime import date

from pastoreio_orquestrador.auditoria import (
    CABECALHO_AUDITORIA,
    CABECALHO_AUDITORIA_SEM_INTENCAO,
    construir_linhas_auditoria,
    carregar_registros_auditoria,
    _header_index,
)
from pastoreio_orquestrador.models import DecisaoAlocacao, SlotAgenda


def _slot(row_index: int, tema: str = "") -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=date(2026, 9, 16),
        dia_da_semana="QUARTA-FEIRA",
        tema=tema,
        mes_key="2026-09",
        semana_do_mes=3,
        is_ultima_ocorrencia_do_mes=False,
    )


def test_construir_linhas_auditoria_decisao_normal():
    decisao = DecisaoAlocacao(
        slot=_slot(1, tema="Fé"),
        vencedor="Ana Lima",
        motivo="ALOCAÇÃO NORMAL",
        candidatos_avaliados=["Ana Lima", "Caio Lima"],
        runner_up="Caio Lima",
        conta_repeticao_mensal=True,
    )

    linhas = construir_linhas_auditoria(
        [decisao],
        grupo_label="D. MINISTROS/MINISTRO/QUARTA-FEIRA",
        requisitos_tema_por_slot={1: "P1"},
        timestamp_execucao="2026-09-05T10:00:00",
        run_id="run-1",
        departamento="D. MINISTROS",
        funcao="MINISTRO",
        dia_da_semana_grupo="QUARTA-FEIRA",
    )

    idx = _header_index(CABECALHO_AUDITORIA)
    linha = linhas[0]
    assert linha[idx["RUN_ID"]] == "run-1"
    assert linha[idx["TEMA"]] == "Fé"
    assert linha[idx["REQUISITO_TEMA"]] == "P1"
    assert linha[idx["VENCEDOR"]] == "Ana Lima"
    assert linha[idx["MOTIVO"]] == "ALOCAÇÃO NORMAL"
    assert linha[idx["CONSOME_HIERARQUIA"]] == "FALSE"
    assert linha[idx["CONTA_REPETICAO_MENSAL"]] == "TRUE"
    assert linha[idx["RUNNER_UP"]] == "Caio Lima"
    assert linha[idx["CANDIDATOS_AVALIADOS"]] == "Ana Lima; Caio Lima"


def test_construir_linhas_auditoria_sem_alocacao():
    decisao = DecisaoAlocacao(
        slot=_slot(2),
        vencedor=None,
        motivo="SEM ALOCAÇÃO",
        sem_alocacao=True,
    )

    linhas = construir_linhas_auditoria(
        [decisao], grupo_label="G", timestamp_execucao="2026-09-05T10:00:00"
    )

    idx = _header_index(CABECALHO_AUDITORIA)
    assert linhas[0][idx["VENCEDOR"]] == ""
    assert linhas[0][idx["MOTIVO"]] == "SEM ALOCAÇÃO"
    assert linhas[0][idx["CONSOME_HIERARQUIA"]] == "FALSE"
    assert linhas[0][idx["CONTA_REPETICAO_MENSAL"]] == "FALSE"
    assert linhas[0][idx["RUNNER_UP"]] == ""
    assert linhas[0][idx["CANDIDATOS_AVALIADOS"]] == ""


def test_cabecalho_tem_uma_coluna_por_campo():
    decisao = DecisaoAlocacao(slot=_slot(3), vencedor="X", motivo="ALOCAÇÃO NORMAL")
    linha = construir_linhas_auditoria([decisao], grupo_label="G")[0]
    assert len(linha) == len(CABECALHO_AUDITORIA)


def test_carregar_auditoria_linhas_legadas_sem_intencao():
    linha_legada = [
        "run-1",
        "2026-09-05T10:00:00",
        "D. MINISTROS/MINISTRO/DOMINGO",
        "D. MINISTROS",
        "MINISTRO",
        "DOMINGO",
        "2026-12-20",
        "DOMINGO",
        "",
        "",
        "Patricia Lopes",
        "2",
        "ALOCAÇÃO NORMAL",
        "NORMAL",
        "TRUE",
        "TRUE",
        "0",
        "1",
        "1",
        "Caio Lima",
        "Patricia Lopes",
        "",
        "Patricia Lopes; Caio Lima",
    ]
    valores = [CABECALHO_AUDITORIA, linha_legada]

    registros = carregar_registros_auditoria(
        valores, "D. MINISTROS", "MINISTRO", "DOMINGO"
    )

    assert len(linha_legada) == len(CABECALHO_AUDITORIA_SEM_INTENCAO)
    assert registros[0].vencedor == "Patricia Lopes"
    assert registros[0].consome_hierarquia is True
