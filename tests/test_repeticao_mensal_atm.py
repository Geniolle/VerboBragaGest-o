from datetime import date

from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    calcular_demanda_base_grupo,
    calcular_demanda_onda_expansiva,
)
from pastoreio_orquestrador.parsing_utils import week_of_month


def _regra(nome: str, **overrides) -> RegraColaborador:
    base = dict(
        id_table="1",
        nome=nome,
        departamento="D. MINISTROS",
        funcao="MINISTRO",
        dia_da_semana="DOMINGO",
        prioridade=10,
        repeticao_mensal=1,
        alocar_todos_os_meses=False,
        semana_preferencial=0,
        ceia_alternada=True,
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


def _slot(row_index: int, d: date, dia: str = "DOMINGO", tema: str = "") -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=d,
        dia_da_semana=dia,
        tema=tema,
        mes_key=f"{d.year:04d}-{d.month:02d}",
        semana_do_mes=week_of_month(d),
        is_ultima_ocorrencia_do_mes=False,
    )


# ===========================================================================
# CENÁRIO A:
# 8 colaboradores, nenhum ATM (ATM=False), todos repeticao_mensal=1
# - Demanda base = 8 alocações
# - Cada colaborador aparece 1x
# ===========================================================================
def test_cenario_a_oito_colaboradores_sem_atm_repeticao_1():
    regras = [_regra(f"Colab_{i}", prioridade=i) for i in range(1, 9)]

    # 2 meses: Outubro/2026 (4 domingos) e Novembro/2026 (4 domingos usados)
    slots = [
        _slot(1, date(2026, 10, 4)),
        _slot(2, date(2026, 10, 11)),
        _slot(3, date(2026, 10, 18)),
        _slot(4, date(2026, 10, 25)),
        _slot(5, date(2026, 11, 1)),
        _slot(6, date(2026, 11, 8)),
        _slot(7, date(2026, 11, 15)),
        _slot(8, date(2026, 11, 22)),
    ]
    meses_tocados = len({s.mes_key for s in slots})
    assert meses_tocados == 2

    demanda_base = calcular_demanda_base_grupo(regras, meses_tocados=meses_tocados)
    assert demanda_base == 8

    demanda = calcular_demanda_onda_expansiva(
        regras, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
    )
    assert demanda.capacidade_base == 8
    assert demanda.demanda_calculada == 8

    estado = EstadoExecucaoGrupo()
    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        demanda.mapa_limites_locais,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
    )

    vencedores = [d.vencedor for d in decisoes]
    assert None not in vencedores

    # Cada um dos 8 colaboradores aparece exatamente 1x
    contagem = {r.nome: vencedores.count(r.nome) for r in regras}
    assert all(c == 1 for c in contagem.values())

    # 4 colaboradores em outubro, 4 colaboradores diferentes em novembro
    vencedores_out = [d.vencedor for d in decisoes if d.slot.mes_key == "2026-10"]
    vencedores_nov = [d.vencedor for d in decisoes if d.slot.mes_key == "2026-11"]
    assert len(set(vencedores_out)) == 4
    assert len(set(vencedores_nov)) == 4
    assert set(vencedores_out).isdisjoint(set(vencedores_nov))


# ===========================================================================
# CENÁRIO B:
# 8 colaboradores, 1 com repeticao_mensal=2 e ATM=False, 7 com repeticao=1 e ATM=False
# - Demanda = 8 base + 1 adicional = 9 alocações
# - Colaborador com repeticao=2 aparece 2x APENAS no seu mês natural, 0x nos outros
# ===========================================================================
def test_cenario_b_oito_colaboradores_um_repeticao_2_sem_atm():
    # Colab_1 tem repeticao_mensal=2, ATM=False (vez natural em outubro)
    regras = [_regra("Colab_1", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=False)]
    regras += [_regra(f"Colab_{i}", prioridade=i, repeticao_mensal=1, alocar_todos_os_meses=False) for i in range(2, 9)]

    slots = [
        _slot(1, date(2026, 10, 4)),
        _slot(2, date(2026, 10, 11)),
        _slot(3, date(2026, 10, 18)),
        _slot(4, date(2026, 10, 25)),
        _slot(5, date(2026, 11, 1)),
        _slot(6, date(2026, 11, 8)),
        _slot(7, date(2026, 11, 15)),
        _slot(8, date(2026, 11, 22)),
    ]
    meses_tocados = len({s.mes_key for s in slots})
    assert meses_tocados == 2

    # Demanda base = 8 base + 1 adicional = 9
    demanda_base = calcular_demanda_base_grupo(regras, meses_tocados=meses_tocados)
    assert demanda_base == 9

    demanda = calcular_demanda_onda_expansiva(
        regras, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
    )
    assert demanda.capacidade_base == 9

    estado = EstadoExecucaoGrupo()
    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        demanda.mapa_limites_locais,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
    )

    vencedores = [d.vencedor for d in decisoes]
    assert None not in vencedores

    # Colab_1 aparece exatamente 2x no total, e AMBAS em outubro (mês natural)
    vencedores_out = [d.vencedor for d in decisoes if d.slot.mes_key == "2026-10"]
    vencedores_nov = [d.vencedor for d in decisoes if d.slot.mes_key == "2026-11"]

    assert vencedores_out.count("Colab_1") == 2
    assert vencedores_nov.count("Colab_1") == 0
    assert vencedores.count("Colab_1") == 2


# ===========================================================================
# CENÁRIO C:
# 8 colaboradores, 1 com repeticao_mensal=2 e ATM=True, 7 com repeticao=1 e ATM=False
# - Ronda abrange 2 meses
# - Demanda = 8 base + 3 adicionais = 11 alocações
# - Colaborador com ATM aparece 2x no Mês A e 2x no Mês B (4 no total)
# ===========================================================================
def test_cenario_c_oito_colaboradores_um_repeticao_2_com_atm():
    regras = [_regra("Colab_1", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=True)]
    regras += [_regra(f"Colab_{i}", prioridade=i, repeticao_mensal=1, alocar_todos_os_meses=False) for i in range(2, 9)]

    slots = [
        _slot(1, date(2026, 10, 4)),
        _slot(2, date(2026, 10, 11)),
        _slot(3, date(2026, 10, 18)),
        _slot(4, date(2026, 10, 25)),
        _slot(5, date(2026, 11, 1)),
        _slot(6, date(2026, 11, 8)),
        _slot(7, date(2026, 11, 15)),
        _slot(8, date(2026, 11, 22)),
    ]
    meses_tocados = len({s.mes_key for s in slots})
    assert meses_tocados == 2

    # Demanda base = 7*1 + 1*(2*2) = 11 (8 base + 3 adicionais)
    demanda_base = calcular_demanda_base_grupo(regras, meses_tocados=meses_tocados)
    assert demanda_base == 11

    demanda = calcular_demanda_onda_expansiva(
        regras, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
    )
    assert demanda.capacidade_base == 11

    estado = EstadoExecucaoGrupo()
    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        demanda.mapa_limites_locais,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
    )

    vencedores = [d.vencedor for d in decisoes]
    assert None not in vencedores

    # Colab_1 aparece 2x em outubro E 2x em novembro (4 alocações no total)
    vencedores_out = [d.vencedor for d in decisoes if d.slot.mes_key == "2026-10"]
    vencedores_nov = [d.vencedor for d in decisoes if d.slot.mes_key == "2026-11"]

    assert vencedores_out.count("Colab_1") == 2
    assert vencedores_nov.count("Colab_1") == 2
    assert vencedores.count("Colab_1") == 4


# ===========================================================================
# CENÁRIO D:
# Colaborador com repeticao_mensal=3 e ATM=False
# - Aparece 3x no mês aplicável
# ===========================================================================
def test_cenario_d_colaborador_repeticao_3_sem_atm():
    # Num mês com 5 domingos (Novembro/2026), posições 1, 3, 5 respeitam descanso e vizinhança
    regras = [
        _regra("Colab_1", prioridade=1, repeticao_mensal=3, alocar_todos_os_meses=False),
        _regra("Colab_2", prioridade=2, repeticao_mensal=1, alocar_todos_os_meses=False),
        _regra("Colab_3", prioridade=3, repeticao_mensal=1, alocar_todos_os_meses=False),
    ]
    slots = [
        _slot(1, date(2026, 11, 1)),   # 1o domingo: CEIA
        _slot(2, date(2026, 11, 8)),   # 2o domingo
        _slot(3, date(2026, 11, 15)),  # 3o domingo
        _slot(4, date(2026, 11, 22)),  # 4o domingo
        _slot(5, date(2026, 11, 29)),  # 5o domingo
    ]
    demanda_base = calcular_demanda_base_grupo(regras, meses_tocados=1)
    assert demanda_base == 5  # 3 (Colab_1) + 1 (Colab_2) + 1 (Colab_3)

    estado = EstadoExecucaoGrupo()
    mapa_mensal = {"Colab_1": 3, "Colab_2": 1, "Colab_3": 1}
    decisoes = alocar_grupo(regras, slots, estado, {}, mapa_limites_mensais=mapa_mensal)

    vencedores = [d.vencedor for d in decisoes]
    assert None not in vencedores
    # Colab_1 aparece exatamente 3x em novembro (em 01/11, 15/11 e 29/11)
    assert vencedores.count("Colab_1") == 3
    assert decisoes[0].vencedor == "Colab_1"  # 01/11 (CEIA)
    assert decisoes[2].vencedor == "Colab_1"  # 15/11 (normal)
    assert decisoes[4].vencedor == "Colab_1"  # 29/11 (normal)


# ===========================================================================
# CENÁRIO E:
# Colaborador com repeticao_mensal=3 e ATM=True, Ronda com 2 meses
# - Aparece 3x no Mês A e 3x no Mês B (total 6x)
# ===========================================================================
def test_cenario_e_colaborador_repeticao_3_com_atm():
    # Colaborador com repeticao_mensal=3 e ATM=True em 2 meses (ex.: Novembro/2026 e Maio/2027)
    # Colab_1 precisa ser alocado 3x em Novembro e 3x em Maio (total = 6 alocacoes).
    regras = [
        _regra("Colab_1", prioridade=1, repeticao_mensal=3, alocar_todos_os_meses=True, ceia_alternada=True),
        _regra("Colab_2", prioridade=2, repeticao_mensal=1, alocar_todos_os_meses=False, ceia_alternada=False),
        _regra("Colab_3", prioridade=3, repeticao_mensal=1, alocar_todos_os_meses=False, ceia_alternada=False),
        _regra("Colab_4", prioridade=4, repeticao_mensal=1, alocar_todos_os_meses=False, ceia_alternada=False),
        _regra("Colab_5", prioridade=5, repeticao_mensal=1, alocar_todos_os_meses=False, ceia_alternada=False),
        _regra("Colab_6", prioridade=6, repeticao_mensal=1, alocar_todos_os_meses=False, ceia_alternada=False),
    ]
    slots_nov = [
        _slot(1, date(2026, 11, 1)),
        _slot(2, date(2026, 11, 8)),
        _slot(3, date(2026, 11, 15)),
        _slot(4, date(2026, 11, 22)),
        _slot(5, date(2026, 11, 29)),
        _slot(6, date(2026, 11, 30)),
    ]
    slots_mai = [
        _slot(7, date(2027, 5, 2)),
        _slot(8, date(2027, 5, 9)),
        _slot(9, date(2027, 5, 16)),
        _slot(10, date(2027, 5, 23)),
        _slot(11, date(2027, 5, 30)),
    ]
    slots = slots_nov + slots_mai
    meses_tocados = len({s.mes_key for s in slots})
    assert meses_tocados == 2

    demanda_base = calcular_demanda_base_grupo(regras, meses_tocados=2)
    # Colab_1: 3*2 = 6, Colab_2..6: 5*1 = 5 => total 11
    assert demanda_base == 11

    estado = EstadoExecucaoGrupo()
    mapa_mensal = {r.nome: r.repeticao_mensal for r in regras}
    decisoes = alocar_grupo(regras, slots, estado, {}, mapa_limites_mensais=mapa_mensal)

    vencedores = [d.vencedor for d in decisoes]
    assert None not in vencedores

    vencedores_nov = [d.vencedor for d in decisoes if d.slot.mes_key == "2026-11"]
    vencedores_mai = [d.vencedor for d in decisoes if d.slot.mes_key == "2027-05"]

    # 3x em Novembro e 3x em Maio = 6x no total para Colab_1
    assert vencedores_nov.count("Colab_1") == 3
    assert vencedores_mai.count("Colab_1") == 3
    assert vencedores.count("Colab_1") == 6


# ===========================================================================
# CENÁRIO F:
# Colaborador com repeticao_mensal=2 bloqueado por Excluse numa das datas
# - Motor encontra outra data elegível dentro do mesmo mês para a 2ª alocação
# ===========================================================================
def test_cenario_f_repeticao_2_bloqueado_por_excluse_encontra_outra_data():
    regras = [
        _regra("Colab_1", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=False),
        _regra("Colab_2", prioridade=2, repeticao_mensal=1, alocar_todos_os_meses=False),
        _regra("Colab_3", prioridade=3, repeticao_mensal=1, alocar_todos_os_meses=False),
        _regra("Colab_4", prioridade=4, repeticao_mensal=1, alocar_todos_os_meses=False),
    ]
    slots = [
        _slot(1, date(2026, 10, 4)),   # 1o dom (CEIA): Colab_1 vence
        _slot(2, date(2026, 10, 11)),  # 2o dom: Colab_1 bloqueado por vizinhanca com 04/10; Colab_2 vence
        _slot(3, date(2026, 10, 18)),  # 3o dom: Colab_1 BLOQUEADO POR EXCLUSE! Colab_3 vence
        _slot(4, date(2026, 10, 25)),  # 4o dom: Colab_1 elegivel! Motor aloca Colab_1 aqui
    ]
    # Matriz Excluse: Colab_1 bloqueado em 18/10/2026
    excluse_header = {
        "NOME": 0,
        "DEPARTAMENTO": 1,
        "FUNÇÃO": 2,
        "ID_MINISTROS": 3,
        "COLUNAS": 4,
    }
    # Bloqueia Colab_1 na data 18/10/2026 simulando que ele tem papel naquela data
    slots[2].papeis["OUTRO_PAPEL"] = "Colab_1"
    excluse_rows = [
        ["Colab_1", "D. MINISTROS", "MINISTRO", "OUTRO_PAPEL", "OUTRO_PAPEL"],
    ]

    estado = EstadoExecucaoGrupo()
    mapa_mensal = {"Colab_1": 2, "Colab_2": 1, "Colab_3": 1, "Colab_4": 1}
    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        {},
        excluse_header=excluse_header,
        excluse_rows=excluse_rows,
        mapa_limites_mensais=mapa_mensal,
    )

    vencedores = [d.vencedor for d in decisoes]
    assert None not in vencedores

    # Colab_1 venceu em 04/10 e 25/10 (encontrou outra data apos ser bloqueado em 18/10)
    assert decisoes[0].vencedor == "Colab_1"  # 04/10
    assert decisoes[1].vencedor == "Colab_2"  # 11/10
    assert decisoes[2].vencedor == "Colab_3"  # 18/10 (Colab_1 bloqueado por Excluse)
    assert decisoes[3].vencedor == "Colab_1"  # 25/10 (2a alocacao encontrada com sucesso)
    assert vencedores.count("Colab_1") == 2


# ===========================================================================
# CENÁRIO G:
# Garantir que a lógica de CEIA ALTERNADA NÃO foi alterada
# ===========================================================================
def test_cenario_g_garantir_ceia_alternada_intocada():
    # 1. No 1o domingo, CEIA ALTERNADA sobrepoe SEMANA PREFERENCIAL e PRIORIDADE
    colab_a = _regra("ColabA", prioridade=2, ceia_alternada=True, semana_preferencial=0)
    colab_b = _regra("ColabB", prioridade=1, ceia_alternada=False, semana_preferencial=1)
    slots = [_slot(1, date(2026, 1, 4))]  # 1o domingo
    estado = EstadoExecucaoGrupo()
    limites = {"ColabA": 10, "ColabB": 10}

    decisoes = alocar_grupo([colab_a, colab_b], slots, estado, limites)
    assert decisoes[0].vencedor == "ColabA"
    assert decisoes[0].motivo == "CEIA ALTERNADA"

    # 2. Rodizio completo de CEIA entre multiplos elegiveis
    regras = [
        _regra("X", prioridade=1, ceia_alternada=True),
        _regra("Y", prioridade=2, ceia_alternada=True),
    ]
    slots_ceia = [
        _slot(1, date(2026, 1, 4)),
        _slot(2, date(2026, 2, 1)),
        _slot(3, date(2026, 3, 1)),
    ]
    estado2 = EstadoExecucaoGrupo()
    decisoes2 = alocar_grupo(regras, slots_ceia, estado2, {"X": 10, "Y": 10})
    assert [d.vencedor for d in decisoes2] == ["X", "Y", "X"]


# ===========================================================================
# CENÁRIO H:
# Garantir que a lógica de QUARTA-FEIRA NÃO foi alterada
# ===========================================================================
def test_cenario_h_garantir_quarta_feira_intocada():
    colab_senior = _regra(
        "Senior_1", prioridade=1, dia_da_semana="QUARTA-FEIRA", temas=["P1"]
    )
    colab_pleno = _regra(
        "Pleno_1", prioridade=2, dia_da_semana="QUARTA-FEIRA", temas=["P2"]
    )
    slot_quarta = _slot(1, date(2026, 1, 7), dia="QUARTA-FEIRA", tema="Licao 1")
    estado = EstadoExecucaoGrupo()
    requisitos = {1: "SENIOR"}

    decisoes = alocar_grupo(
        [colab_senior, colab_pleno],
        [slot_quarta],
        estado,
        {"Senior_1": 10, "Pleno_1": 10},
        requisitos_tema_por_slot=requisitos,
    )
    assert decisoes[0].vencedor == "Senior_1"
    assert decisoes[0].motivo == "ALOCAÇÃO NORMAL"
    # Quarta-feira nao preenche historico de CEIA
    assert len(estado.historico_vencedores_ceia) == 0
