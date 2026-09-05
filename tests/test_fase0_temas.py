from datetime import date

from pastoreio_orquestrador.models import SlotAgenda, TemaClassificado
from pastoreio_orquestrador.motor import montar_requisito_tema_por_slot


def _slot(row_index: int, d: date, tema: str) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=d,
        dia_da_semana="QUARTA-FEIRA",
        tema=tema,
        mes_key=f"{d.year:04d}-{d.month:02d}",
        semana_do_mes=1,
        is_ultima_ocorrencia_do_mes=False,
    )


def test_bloco_p3_com_varias_semanas_divide_em_p1_meio_p2():
    slots = [
        _slot(1, date(2026, 1, 7), "ALIANÇA DE SANGUE"),
        _slot(2, date(2026, 1, 14), "ALIANÇA DE SANGUE"),
        _slot(3, date(2026, 1, 21), "ALIANÇA DE SANGUE"),
        _slot(4, date(2026, 1, 28), "ALIANÇA DE SANGUE"),
    ]
    temas = [TemaClassificado("QUARTA-FEIRA", "ALIANÇA DE SANGUE", "P3")]

    requisito = montar_requisito_tema_por_slot(slots, temas)

    assert requisito[1] == "P1"
    assert requisito[2] == "P3"
    assert requisito[3] == "P3"
    assert requisito[4] == "P2"


def test_bloco_p2_de_semana_unica_exige_p2_em_todo_o_bloco():
    slots = [_slot(1, date(2026, 1, 7), "AUTORIDADE DO CRENTE")]
    temas = [TemaClassificado("QUARTA-FEIRA", "AUTORIDADE DO CRENTE", "P2")]

    requisito = montar_requisito_tema_por_slot(slots, temas)

    assert requisito[1] == "P2"


def test_tema_sem_classificacao_nao_gera_requisito():
    slots = [_slot(1, date(2026, 1, 7), "TEMA DESCONHECIDO")]
    requisito = montar_requisito_tema_por_slot(slots, temas_livros=[])
    assert 1 not in requisito
