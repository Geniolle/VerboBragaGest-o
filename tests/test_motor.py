from datetime import date

from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    calcular_demanda_onda_expansiva,
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
        sinc_colaborador=None,
        sinc_sem_alocacao=False,
        temas=[],
        ativo=True,
        row_index_bp=1,
    )
    base.update(overrides)
    return RegraColaborador(**base)


def _slot(row_index: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=d,
        dia_da_semana="QUARTA-FEIRA",
        tema="",
        mes_key=f"{d.year:04d}-{d.month:02d}",
        semana_do_mes=1,
        is_ultima_ocorrencia_do_mes=False,
    )


def test_demanda_ativa_cota_extra_quando_vagas_excedem_capacidade_base():
    candidatos = [_regra("Ana", repeticao_mensal=1, alocacao_extra=2), _regra("Bia", repeticao_mensal=1)]
    resultado = calcular_demanda_onda_expansiva(candidatos, vagas_reais_no_periodo=4, meses_tocados=1)

    assert resultado.capacidade_base == 2
    assert resultado.usa_cota_extra is True
    assert resultado.capacidade_total == 4  # (1+2) + (1+0)
    assert resultado.demanda_calculada == 4


def test_demanda_nao_ativa_extra_quando_vagas_cabem_na_base():
    candidatos = [_regra("Ana"), _regra("Bia")]
    resultado = calcular_demanda_onda_expansiva(candidatos, vagas_reais_no_periodo=2, meses_tocados=1)

    assert resultado.usa_cota_extra is False
    assert resultado.demanda_calculada == 2


def test_alocar_grupo_distribui_entre_dois_candidatos_respeitando_descanso():
    regras = [_regra("Ana"), _regra("Bia")]
    slots = [
        _slot(1, date(2026, 1, 7)),
        _slot(2, date(2026, 1, 14)),
        _slot(3, date(2026, 1, 21)),
        _slot(4, date(2026, 1, 28)),
    ]
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 2, "Bia": 2}

    decisoes = alocar_grupo(regras, slots, estado, limites)

    assert all(d.vencedor is not None for d in decisoes)
    vencedores = [d.vencedor for d in decisoes]
    assert vencedores.count("Ana") == 2
    assert vencedores.count("Bia") == 2
    # O 2o slot alterna obrigatoriamente (desempate por menor uso no mes
    # favorece quem ainda nao foi escalado). A partir do 3o, ambos ja tem
    # historico igual (1 uso cada) e o desempate final e aleatorio por
    # empate legitimo — nao ha mais criterio determinista para decidir.
    assert vencedores[0] != vencedores[1]


def test_alocar_grupo_marca_sem_alocacao_quando_quota_esgotada():
    regras = [_regra("Ana", repeticao_mensal=1)]
    slots = [_slot(1, date(2026, 1, 7)), _slot(2, date(2026, 1, 14))]
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 1}  # so uma vaga liberada para Ana neste periodo

    decisoes = alocar_grupo(regras, slots, estado, limites)

    assert decisoes[0].vencedor == "Ana"
    assert decisoes[1].sem_alocacao is True
    assert decisoes[1].vencedor is None


def test_alocar_grupo_sincronizacao_ignora_descanso_minimo():
    regras = [
        _regra("Ana", sinc_colaborador="Bia", repeticao_mensal=4),
        _regra("Bia", sinc_colaborador="Ana", repeticao_mensal=4),
    ]
    # Duas quartas seguidas (menos de 7 dias de intervalo nao seria possivel
    # aqui pois sao semanais = 7 dias exatos; forcamos um caso de <7 dias
    # simulando um slot extra no meio da semana).
    slots = [
        _slot(1, date(2026, 1, 7)),
        _slot(2, date(2026, 1, 9)),  # 2 dias depois: violaria descanso minimo
    ]
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 4, "Bia": 4}

    decisoes = alocar_grupo(regras, slots, estado, limites)

    # Ambas as linhas devem ter vencedor (SINC permite ignorar o descanso).
    assert decisoes[0].vencedor is not None
    assert decisoes[1].vencedor is not None
