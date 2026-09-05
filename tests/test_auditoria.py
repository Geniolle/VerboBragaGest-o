from datetime import date

from pastoreio_orquestrador.auditoria import (
    CABECALHO_AUDITORIA,
    construir_linhas_auditoria,
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
    )

    linhas = construir_linhas_auditoria(
        [decisao],
        grupo_label="D. MINISTROS/MINISTRO/QUARTA-FEIRA",
        requisitos_tema_por_slot={1: "P1"},
        timestamp_execucao="2026-09-05T10:00:00",
    )

    assert linhas == [
        [
            "2026-09-05T10:00:00",
            "D. MINISTROS/MINISTRO/QUARTA-FEIRA",
            "2026-09-16",
            "QUARTA-FEIRA",
            "Fé",
            "P1",
            "Ana Lima",
            "ALOCAÇÃO NORMAL",
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

    assert linhas[0][6] == ""  # VENCEDOR vazio
    assert linhas[0][7] == "SEM ALOCAÇÃO"
    assert linhas[0][8] == ""  # RUNNER_UP vazio
    assert linhas[0][9] == ""  # nenhum candidato avaliado


def test_cabecalho_tem_uma_coluna_por_campo():
    decisao = DecisaoAlocacao(slot=_slot(3), vencedor="X", motivo="ALOCAÇÃO NORMAL")
    linha = construir_linhas_auditoria([decisao], grupo_label="G")[0]
    assert len(linha) == len(CABECALHO_AUDITORIA)
