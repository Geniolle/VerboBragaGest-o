from datetime import date

from pastoreio_orquestrador.models import DecisaoAlocacao, RegistroBpLog, SlotAgenda
from pastoreio_orquestrador.zumbi_writeback import montar_atualizacoes_zumbis_recuperados


def _slot(row_index: int) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=date(2026, 9, 16),
        dia_da_semana="QUARTA-FEIRA",
        tema="",
        mes_key="2026-09",
        semana_do_mes=3,
        is_ultima_ocorrencia_do_mes=False,
    )


def _registro(nome: str, disponibilidade: bool, departamento="D. MINISTROS", processo="MINISTRO") -> RegistroBpLog:
    return RegistroBpLog(
        departamento=departamento,
        processo=processo,
        nome=nome,
        mes_nao_alocados="",
        disponibilidade=disponibilidade,
        timestamp_utilizacao="",
    )


def test_zumbi_vencedor_e_marcado_para_recuperacao():
    decisoes = [DecisaoAlocacao(slot=_slot(1), vencedor="Edna Souza", motivo="ALOCAÇÃO NORMAL")]
    bp_log = [_registro("Edna Souza", disponibilidade=True)]

    atualizacoes = montar_atualizacoes_zumbis_recuperados(
        decisoes, bp_log, departamento="D. MINISTROS", processo="MINISTRO"
    )

    assert len(atualizacoes) == 1
    assert atualizacoes[0].nome == "Edna Souza"
    assert atualizacoes[0].row_index_bp_log == 1


def test_vencedor_sem_registro_pendente_nao_gera_atualizacao():
    decisoes = [DecisaoAlocacao(slot=_slot(1), vencedor="Ana Lima", motivo="ALOCAÇÃO NORMAL")]
    bp_log = [_registro("Edna Souza", disponibilidade=True)]

    atualizacoes = montar_atualizacoes_zumbis_recuperados(
        decisoes, bp_log, departamento="D. MINISTROS", processo="MINISTRO"
    )
    assert atualizacoes == []


def test_registro_ja_recuperado_nao_e_atualizado_de_novo():
    decisoes = [DecisaoAlocacao(slot=_slot(1), vencedor="Edna Souza", motivo="ALOCAÇÃO NORMAL")]
    bp_log = [_registro("Edna Souza", disponibilidade=False)]

    atualizacoes = montar_atualizacoes_zumbis_recuperados(
        decisoes, bp_log, departamento="D. MINISTROS", processo="MINISTRO"
    )
    assert atualizacoes == []


def test_registro_de_outro_departamento_ou_processo_e_ignorado():
    decisoes = [DecisaoAlocacao(slot=_slot(1), vencedor="Edna Souza", motivo="ALOCAÇÃO NORMAL")]
    bp_log = [
        _registro("Edna Souza", disponibilidade=True, departamento="D. DIACONATO"),
        _registro("Edna Souza", disponibilidade=True, processo="AUXILIAR"),
    ]

    atualizacoes = montar_atualizacoes_zumbis_recuperados(
        decisoes, bp_log, departamento="D. MINISTROS", processo="MINISTRO"
    )
    assert atualizacoes == []


def test_decisao_sem_alocacao_nao_gera_atualizacao():
    decisoes = [DecisaoAlocacao(slot=_slot(1), vencedor=None, motivo="SEM ALOCAÇÃO", sem_alocacao=True)]
    bp_log = [_registro("Edna Souza", disponibilidade=True)]

    atualizacoes = montar_atualizacoes_zumbis_recuperados(
        decisoes, bp_log, departamento="D. MINISTROS", processo="MINISTRO"
    )
    assert atualizacoes == []
