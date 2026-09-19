from datetime import date

from pastoreio_orquestrador.auditoria import (
    CABECALHO_AUDITORIA,
    CABECALHO_AUDITORIA_SEM_INTENCAO,
    construir_linhas_auditoria,
    carregar_registros_auditoria,
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

    assert linhas == [
        [
            "run-1",
            "2026-09-05T10:00:00",
            "D. MINISTROS/MINISTRO/QUARTA-FEIRA",
            "D. MINISTROS",
            "MINISTRO",
            "QUARTA-FEIRA",
            "2026-09-16",
            "QUARTA-FEIRA",
            "Fé",
            "P1",
            "Ana Lima",
            "",
            "ALOCAÇÃO NORMAL",
            "",
            "ALOCAÇÃO NORMAL",
            "",
            "FALSE",
            "TRUE",
            "",
            "",
            "",
            "",
            "",
            "Caio Lima",
            "Ana Lima; Caio Lima",
        ]
    ]


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

    assert linhas[0][10] == ""  # VENCEDOR vazio
    assert linhas[0][12] == "SEM ALOCAÇÃO"
    assert linhas[0][16] == "FALSE"
    assert linhas[0][17] == "FALSE"
    assert linhas[0][23] == ""  # RUNNER_UP vazio
    assert linhas[0][24] == ""  # nenhum candidato avaliado


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
