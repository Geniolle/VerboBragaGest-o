from datetime import date

from pastoreio_orquestrador.alerta_sem_alocacao import montar_alerta_sem_alocacao
from pastoreio_orquestrador.models import DecisaoAlocacao, SlotAgenda


def _slot(row_index: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=d,
        dia_da_semana="QUARTA-FEIRA",
        tema="",
        mes_key="2026-09",
        semana_do_mes=3,
        is_ultima_ocorrencia_do_mes=False,
    )


def test_sem_decisoes_sem_alocacao_nao_gera_alerta():
    decisoes = [
        DecisaoAlocacao(slot=_slot(1, date(2026, 9, 16)), vencedor="Ana Lima", motivo="ALOCAÇÃO NORMAL")
    ]
    alerta = montar_alerta_sem_alocacao(decisoes, grupo_label="G", email_lider="lider@x.com")
    assert alerta is None


def test_decisoes_sem_alocacao_geram_alerta_com_datas_e_destinatario():
    decisoes = [
        DecisaoAlocacao(slot=_slot(1, date(2026, 9, 16)), vencedor="Ana Lima", motivo="ALOCAÇÃO NORMAL"),
        DecisaoAlocacao(slot=_slot(2, date(2026, 9, 23)), vencedor=None, motivo="SEM ALOCAÇÃO", sem_alocacao=True),
        DecisaoAlocacao(slot=_slot(3, date(2026, 9, 30)), vencedor=None, motivo="SEM ALOCAÇÃO", sem_alocacao=True),
    ]
    alerta = montar_alerta_sem_alocacao(
        decisoes, grupo_label="D. MINISTROS/MINISTRO/QUARTA-FEIRA", email_lider="lider@x.com"
    )

    assert alerta is not None
    assert alerta.email_lider == "lider@x.com"
    assert alerta.datas_sem_alocacao == ["2026-09-23", "2026-09-30"]
    assert "2" in alerta.assunto
    assert "2026-09-23" in alerta.corpo
    assert "2026-09-30" in alerta.corpo
