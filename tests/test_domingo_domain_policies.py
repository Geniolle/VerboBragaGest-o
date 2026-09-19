from pastoreio_orquestrador.domain.common.decisions import AllocationIntent
from pastoreio_orquestrador.domain.domingo.policies import (
    calcular_cursor_depois,
    classificar_intencao_decisao,
    classificar_intencao_mensal,
    classificar_tipo_alocacao,
    obrigacao_satisfeita_por_intencao,
)


def test_intencao_mensal_repeticao_nao_e_vaga_normal():
    intent = classificar_intencao_mensal(
        dia_da_semana="DOMINGO",
        slot_e_ceia=False,
        alocar_todos_os_meses=False,
        cota_base=2,
        limite_mensal=2,
        ocorrencias_no_mes=1,
        ja_consumiu_hierarquia_na_ronda=True,
        ja_participou_na_ronda=True,
    )

    assert intent == AllocationIntent.MONTHLY_REPEAT
    assert classificar_tipo_alocacao(intent, "ALOCAÇÃO NORMAL") == "REPETICAO_MENSAL"
    assert obrigacao_satisfeita_por_intencao(intent) == "REPETICAO_MENSAL"


def test_intencao_mensal_atm_aparece_somente_quando_ja_ha_participacao():
    primeira_tentativa = classificar_intencao_mensal(
        dia_da_semana="DOMINGO",
        slot_e_ceia=False,
        alocar_todos_os_meses=True,
        cota_base=2,
        limite_mensal=2,
        ocorrencias_no_mes=0,
        ja_consumiu_hierarquia_na_ronda=False,
        ja_participou_na_ronda=False,
    )
    obrigacao = classificar_intencao_mensal(
        dia_da_semana="DOMINGO",
        slot_e_ceia=False,
        alocar_todos_os_meses=True,
        cota_base=2,
        limite_mensal=2,
        ocorrencias_no_mes=1,
        ja_consumiu_hierarquia_na_ronda=True,
        ja_participou_na_ronda=True,
    )

    assert primeira_tentativa is None
    assert obrigacao == AllocationIntent.EVERY_MONTH_OBLIGATION


def test_ceia_conta_como_intencao_propria_e_nao_move_cursor():
    intent = classificar_intencao_decisao(
        motivo="CEIA ALTERNADA",
        consome_hierarquia=False,
        is_obrigacao_mensal=False,
        alocar_todos_os_meses=False,
    )

    assert intent == AllocationIntent.CEIA
    assert classificar_tipo_alocacao(intent, "CEIA ALTERNADA") == "CEIA"
    assert calcular_cursor_depois("Ancora", "Ceia", False) == "Ancora"


def test_normal_move_cursor_e_obrigacao_nao_move():
    normal = classificar_intencao_decisao(
        motivo="ALOCAÇÃO NORMAL",
        consome_hierarquia=True,
        is_obrigacao_mensal=False,
        alocar_todos_os_meses=False,
    )
    repeticao = classificar_intencao_decisao(
        motivo="ALOCAÇÃO NORMAL",
        consome_hierarquia=False,
        is_obrigacao_mensal=True,
        alocar_todos_os_meses=False,
    )

    assert normal == AllocationIntent.NORMAL_ROTATION
    assert repeticao == AllocationIntent.MONTHLY_REPEAT
    assert calcular_cursor_depois("P2", "P3", True) == "P3"
    assert calcular_cursor_depois("P2", "P1", False) == "P2"


def test_quarta_nao_gera_intencao_mensal_de_domingo():
    intent = classificar_intencao_mensal(
        dia_da_semana="QUARTA-FEIRA",
        slot_e_ceia=False,
        alocar_todos_os_meses=False,
        cota_base=2,
        limite_mensal=2,
        ocorrencias_no_mes=1,
        ja_consumiu_hierarquia_na_ronda=True,
        ja_participou_na_ronda=True,
    )

    assert intent is None
