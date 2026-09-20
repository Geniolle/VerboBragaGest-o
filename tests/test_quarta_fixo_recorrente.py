from datetime import date

from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import EstadoExecucaoGrupo, alocar_grupo
from pastoreio_orquestrador.parsing_utils import month_key, week_of_month
from pastoreio_orquestrador.domain.quarta.recorrencia import (
    delimitar_ronda_quarta_com_fixos,
    montar_decisao_fixa,
    separar_regras_quarta,
)


def _regra(nome: str, **overrides) -> RegraColaborador:
    base = dict(
        id_table="1",
        nome=nome,
        departamento="D. MINISTROS",
        funcao="MINISTRO",
        dia_da_semana="QUARTA-FEIRA",
        prioridade=10,
        repeticao_mensal=1,
        alocar_todos_os_meses=False,
        semana_preferencial=0,
        ceia_alternada=False,
        semana_alternada=False,
        alocacao_extra=0,
        atribuir_aos_recados=False,
        perfil_autorizacao=False,
        sinc_colaborador=None,
        sinc_sem_alocacao=False,
        temas=[],
        ativo=True,
        row_index_bp=1,
    )
    base.update(overrides)
    return RegraColaborador(**base)


def _slot(row_index: int, data_slot: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=data_slot,
        dia_da_semana="QUARTA-FEIRA",
        tema="",
        mes_key=month_key(data_slot),
        semana_do_mes=week_of_month(data_slot),
        is_ultima_ocorrencia_do_mes=False,
    )


def _centro_de_cura() -> RegraColaborador:
    return _regra(
        "Centro de Cura",
        prioridade=1,
        semana_preferencial=3,
        tipo_alocacao="FIXO_RECORRENTE",
        intervalo_meses=2,
        data_inicio_recorrencia=date(2026, 9, 16),
    )


def test_fixo_recorrente_nao_participa_do_pool_normal_em_data_nao_recorrente():
    grupo_normal, regras_fixas = separar_regras_quarta(
        [_centro_de_cura(), _regra("A", prioridade=2), _regra("B", prioridade=3)]
    )

    assert [r.nome for r in regras_fixas] == ["Centro de Cura"]
    assert [r.nome for r in grupo_normal] == ["A", "B"]

    decisoes = alocar_grupo(
        grupo_normal,
        [_slot(1, date(2026, 10, 14))],
        EstadoExecucaoGrupo(),
        {"A": 1, "B": 1},
    )

    assert decisoes[0].vencedor == "A"


def test_fixo_recorrente_tem_precedencia_na_data_reservada():
    decisao = montar_decisao_fixa(_slot(1, date(2026, 11, 18)), _centro_de_cura())

    assert decisao.vencedor == "Centro de Cura"
    assert decisao.intent == "FIXED_RECURRENCE"
    assert decisao.consome_hierarquia is False
    assert decisao.conta_repeticao_mensal is False


def test_reserva_fixa_nao_avanca_o_rodizio_normal():
    regras_normais = [_regra("A", prioridade=1), _regra("B", prioridade=2)]
    estado = EstadoExecucaoGrupo()

    primeira = alocar_grupo(
        regras_normais,
        [_slot(1, date(2026, 11, 11))],
        estado,
        {"A": 1, "B": 1},
    )[0]
    fixa = montar_decisao_fixa(_slot(2, date(2026, 11, 18)), _centro_de_cura())
    segunda = alocar_grupo(
        regras_normais,
        [_slot(3, date(2026, 11, 25))],
        estado,
        {"A": 1, "B": 1},
    )[0]

    assert primeira.vencedor == "A"
    assert fixa.vencedor == "Centro de Cura"
    assert segunda.vencedor == "B"


def test_ronda_conta_reserva_fixa_como_calendario_mas_nao_como_participacao_base():
    datas = [
        date(2026, 11, 4),
        date(2026, 11, 11),
        date(2026, 11, 18),
        date(2026, 11, 25),
        date(2026, 12, 2),
    ]

    ronda = delimitar_ronda_quarta_com_fixos(
        datas,
        n_colaboradores_normais=3,
        regras_fixas=[_centro_de_cura()],
    )

    assert ronda == [
        date(2026, 11, 4),
        date(2026, 11, 11),
        date(2026, 11, 18),
        date(2026, 11, 25),
    ]
