from datetime import date

from pastoreio_orquestrador.models import SlotAgenda, TemaClassificado
from pastoreio_orquestrador.motor import (
    is_tema_compativel,
    montar_requisito_tema_por_slot,
    nivel_senioridade,
)


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


def test_nivel_senioridade_por_classificacao_maxima():
    assert nivel_senioridade(["P1", "P2", "P3"]) == "SENIOR"
    assert nivel_senioridade(["P1"]) == "SENIOR"
    assert nivel_senioridade(["P1", "P3"]) == "SENIOR"  # senior mesmo sem P2
    assert nivel_senioridade(["P2", "P3"]) == "PLENO"
    assert nivel_senioridade(["P2"]) == "PLENO"
    assert nivel_senioridade(["P3"]) == "JUNIOR"
    assert nivel_senioridade([]) == "JUNIOR"


def test_bloco_p1_exige_senior_em_toda_semana():
    slots = [
        _slot(1, date(2026, 1, 7), "SUBMISSÃO E AUTORIDADE"),
        _slot(2, date(2026, 1, 14), "SUBMISSÃO E AUTORIDADE"),
        _slot(3, date(2026, 1, 21), "SUBMISSÃO E AUTORIDADE"),
    ]
    temas = [TemaClassificado("QUARTA-FEIRA", "SUBMISSÃO E AUTORIDADE", "P1")]

    requisito = montar_requisito_tema_por_slot(slots, temas)

    assert requisito[1] == "SENIOR"
    assert requisito[2] == "SENIOR"
    assert requisito[3] == "SENIOR"


def test_bloco_p2_com_varias_semanas_pontas_senior_meio_pleno():
    slots = [
        _slot(1, date(2026, 1, 7), "AUTORIDADE DO CRENTE"),
        _slot(2, date(2026, 1, 14), "AUTORIDADE DO CRENTE"),
        _slot(3, date(2026, 1, 21), "AUTORIDADE DO CRENTE"),
        _slot(4, date(2026, 1, 28), "AUTORIDADE DO CRENTE"),
    ]
    temas = [TemaClassificado("QUARTA-FEIRA", "AUTORIDADE DO CRENTE", "P2")]

    requisito = montar_requisito_tema_por_slot(slots, temas)

    assert requisito[1] == "SENIOR"
    assert requisito[2] == "PLENO"
    assert requisito[3] == "PLENO"
    assert requisito[4] == "SENIOR"


def test_bloco_p3_so_abertura_senior_2a_semana_pleno_e_o_restante_junior():
    slots = [
        _slot(1, date(2026, 1, 7), "ALIANÇA DE SANGUE"),
        _slot(2, date(2026, 1, 14), "ALIANÇA DE SANGUE"),
        _slot(3, date(2026, 1, 21), "ALIANÇA DE SANGUE"),
        _slot(4, date(2026, 1, 28), "ALIANÇA DE SANGUE"),
    ]
    temas = [TemaClassificado("QUARTA-FEIRA", "ALIANÇA DE SANGUE", "P3")]

    requisito = montar_requisito_tema_por_slot(slots, temas)

    # Correcao 2026-09-10 (pedido do Clayton): P3 e o tema mais facil, so
    # precisa de 1 SENIOR (abertura) -- nao 2 como o P2 -- seguido de 1
    # PLENO fixo na 2a semana e JUNIOR no restante do bloco.
    assert requisito[1] == "SENIOR"
    assert requisito[2] == "PLENO"
    assert requisito[3] == "JUNIOR"
    assert requisito[4] == "JUNIOR"


def test_bloco_p3_com_5_semanas_promove_a_ultima_de_junior_para_pleno():
    slots = [
        _slot(1, date(2026, 1, 7), "DOUTRINAS BÁSICAS DA BÍBLIA"),
        _slot(2, date(2026, 1, 14), "DOUTRINAS BÁSICAS DA BÍBLIA"),
        _slot(3, date(2026, 1, 21), "DOUTRINAS BÁSICAS DA BÍBLIA"),
        _slot(4, date(2026, 1, 28), "DOUTRINAS BÁSICAS DA BÍBLIA"),
        _slot(5, date(2026, 2, 4), "DOUTRINAS BÁSICAS DA BÍBLIA"),
    ]
    temas = [TemaClassificado("QUARTA-FEIRA", "DOUTRINAS BÁSICAS DA BÍBLIA", "P3")]

    requisito = montar_requisito_tema_por_slot(slots, temas)

    # Excecao da 5a semana (2026-09-10, pedido do Clayton): bloco P3 de 5
    # semanas so tem capacidade para 2 semanas JUNIOR no grupo real (2
    # colaboradores JUNIOR, cota de 1/mes cada) -- a 5a semana promove para
    # PLENO ("sempre dar preferencia a classificacao maior") em vez dos 3
    # JUNIOR que geravam SEM ALOCAÇÃO.
    assert requisito[1] == "SENIOR"
    assert requisito[2] == "PLENO"
    assert requisito[3] == "JUNIOR"
    assert requisito[4] == "JUNIOR"
    assert requisito[5] == "PLENO"


def test_bloco_de_semana_unica_exige_senior_como_fallback_seguro():
    slots = [_slot(1, date(2026, 1, 7), "AUTORIDADE DO CRENTE")]
    temas = [TemaClassificado("QUARTA-FEIRA", "AUTORIDADE DO CRENTE", "P2")]

    requisito = montar_requisito_tema_por_slot(slots, temas)

    assert requisito[1] == "SENIOR"


def test_tema_sem_classificacao_nao_gera_requisito():
    slots = [_slot(1, date(2026, 1, 7), "TEMA DESCONHECIDO")]
    requisito = montar_requisito_tema_por_slot(slots, temas_livros=[])
    assert 1 not in requisito


def test_is_tema_compativel_exige_correspondencia_exata_de_nivel():
    # Senior (tem P1) NAO cobre vaga de PLENO nem JUNIOR.
    assert not is_tema_compativel(["P1", "P2", "P3"], "PLENO", "QUARTA-FEIRA")
    assert not is_tema_compativel(["P1", "P2", "P3"], "JUNIOR", "QUARTA-FEIRA")
    assert is_tema_compativel(["P1", "P2", "P3"], "SENIOR", "QUARTA-FEIRA")
    # Pleno (P2, sem P1) so cobre vaga de PLENO.
    assert is_tema_compativel(["P2", "P3"], "PLENO", "QUARTA-FEIRA")
    assert not is_tema_compativel(["P2", "P3"], "SENIOR", "QUARTA-FEIRA")
    # Junior (so P3) so cobre vaga de JUNIOR.
    assert is_tema_compativel(["P3"], "JUNIOR", "QUARTA-FEIRA")
    assert not is_tema_compativel(["P3"], "PLENO", "QUARTA-FEIRA")


def test_is_tema_compativel_sempre_livre_fora_de_quarta_feira():
    assert is_tema_compativel(["P3"], "SENIOR", "DOMINGO")
    assert is_tema_compativel([], "SENIOR", "DOMINGO")
