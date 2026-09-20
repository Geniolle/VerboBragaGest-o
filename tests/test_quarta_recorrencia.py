from datetime import date

import pytest

from pastoreio_orquestrador.domain.quarta.recorrencia import (
    ConflitoFixoRecorrenteError,
    avaliar_regra_fixa_na_data,
    regra_fixa_aplica_na_data,
    reserva_fixa_para_data,
)
from pastoreio_orquestrador.models import RegraColaborador
from pastoreio_orquestrador.parsing_utils import week_of_month


def _regra(nome: str = "Centro de Cura", **overrides) -> RegraColaborador:
    base = dict(
        id_table="1",
        nome=nome,
        departamento="D. MINISTROS",
        funcao="MINISTRO",
        dia_da_semana="QUARTA-FEIRA",
        prioridade=1,
        repeticao_mensal=1,
        alocar_todos_os_meses=False,
        semana_preferencial=3,
        ceia_alternada=False,
        semana_alternada=False,
        alocacao_extra=0,
        atribuir_aos_recados=False,
        perfil_autorizacao=False,
        sinc_colaborador=None,
        sinc_sem_alocacao=False,
        temas=["P1"],
        ativo=True,
        row_index_bp=1,
        tipo_alocacao="FIXO_RECORRENTE",
        intervalo_meses=2,
        data_inicio_recorrencia=date(2026, 9, 16),
    )
    base.update(overrides)
    return RegraColaborador(**base)


def test_centro_de_cura_aplica_so_na_terceira_quarta_do_mes_recorrente():
    regra = _regra()

    resultados = {
        date(2026, 10, 7): False,
        date(2026, 10, 14): False,
        date(2026, 10, 21): False,
        date(2026, 10, 28): False,
        date(2026, 11, 4): False,
        date(2026, 11, 11): False,
        date(2026, 11, 18): True,
        date(2026, 11, 25): False,
        date(2026, 12, 2): False,
        date(2026, 12, 9): False,
        date(2026, 12, 16): False,
        date(2026, 12, 23): False,
        date(2026, 12, 30): False,
        date(2027, 1, 20): True,
    }

    assert {data: regra_fixa_aplica_na_data(regra, data) for data in resultados} == resultados


def test_recorrencia_depende_da_ancora_e_nao_de_mes_par_ou_impar():
    ancora_setembro = _regra(data_inicio_recorrencia=date(2026, 9, 16))
    ancora_outubro = _regra(data_inicio_recorrencia=date(2026, 10, 21))

    assert regra_fixa_aplica_na_data(ancora_setembro, date(2026, 11, 18))
    assert regra_fixa_aplica_na_data(ancora_setembro, date(2027, 1, 20))
    assert not regra_fixa_aplica_na_data(ancora_setembro, date(2026, 12, 16))

    assert regra_fixa_aplica_na_data(ancora_outubro, date(2026, 12, 16))
    assert regra_fixa_aplica_na_data(ancora_outubro, date(2027, 2, 17))
    assert not regra_fixa_aplica_na_data(ancora_outubro, date(2026, 11, 18))


def test_terceira_quarta_usando_week_of_month():
    assert week_of_month(date(2026, 9, 16)) == 3
    assert week_of_month(date(2026, 11, 18)) == 3
    assert week_of_month(date(2027, 1, 20)) == 3


def test_avaliacao_explica_delta_mes_e_semana():
    avaliacao = avaliar_regra_fixa_na_data(_regra(), date(2026, 11, 18))

    assert avaliacao.delta_meses == 2
    assert avaliacao.mes_da_recorrencia is True
    assert avaliacao.semana_exigida == 3
    assert avaliacao.semana_da_data == 3
    assert avaliacao.aplica is True


def test_conflito_entre_duas_reservas_fixas_e_erro_de_configuracao():
    regras = [_regra("Evento A"), _regra("Evento B", row_index_bp=2)]

    with pytest.raises(ConflitoFixoRecorrenteError, match="Conflito FIXO_RECORRENTE"):
        reserva_fixa_para_data(regras, date(2026, 11, 18))
