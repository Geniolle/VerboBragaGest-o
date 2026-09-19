from datetime import date

from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    alocar_ronda_dinamica,
    calcular_demanda_base_grupo,
    calcular_demanda_onda_expansiva,
    necessidade_mensal_restante,
    ocorrencias_mensais_colaborador,
    ronda_esta_completa,
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
    regras = [_regra(f"Colab_{i}", prioridade=i, ceia_alternada=False) for i in range(1, 9)]

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


def _alocar_dinamico_padrao(regras, slots, estado):
    meses_tocados = len({s.mes_key for s in slots})
    demanda = calcular_demanda_onda_expansiva(
        regras, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
    )
    return alocar_grupo(
        regras,
        slots,
        estado,
        demanda.mapa_limites_locais,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
    )


def test_ronda_nao_encerra_com_colaborador_base_pendente():
    regras = [
        _regra("Ceia", prioridade=4, ceia_alternada=True),
        _regra("Mensal", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=True, ceia_alternada=False),
        _regra("Pendente", prioridade=2, semana_preferencial=3, ceia_alternada=False),
        _regra("Apoio", prioridade=3, ceia_alternada=False),
    ]
    slots_nov = [
        _slot(1, date(2026, 11, 15)),
        _slot(2, date(2026, 11, 22)),
        _slot(3, date(2026, 11, 29)),
    ]
    slots_dez = [
        _slot(4, date(2026, 12, 6)),
        _slot(5, date(2026, 12, 13)),
        _slot(6, date(2026, 12, 20)),
        _slot(7, date(2026, 12, 27)),
    ]
    aniversarios = {"PENDENTE": date(2000, 11, 15)}

    def alocar(slots, estado):
        meses_tocados = len({s.mes_key for s in slots})
        demanda = calcular_demanda_onda_expansiva(
            regras, vagas_reais_no_periodo=len(slots), meses_tocados=meses_tocados
        )
        return alocar_grupo(
            regras,
            slots,
            estado,
            demanda.mapa_limites_locais,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            aniversarios=aniversarios,
        )

    resultado = alocar_ronda_dinamica(
        regras, slots_nov + slots_dez, EstadoExecucaoGrupo(), 1, alocar
    )

    assert any("Pendente" in evento and "participacao-base pendente" in evento for evento in resultado.eventos)
    assert any(slot.mes_key == "2026-12" for slot in resultado.slots)
    assert resultado.completude.completa is True


def test_novo_mes_cria_obrigacao_para_alocar_todos_os_meses():
    regras = [
        _regra("Ceia", prioridade=4, ceia_alternada=True),
        _regra("Mensal", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=True, ceia_alternada=False),
        _regra("Pendente", prioridade=2, semana_preferencial=3, ceia_alternada=False),
        _regra("Apoio", prioridade=3, ceia_alternada=False),
    ]
    slots = [
        _slot(1, date(2026, 11, 15)),
        _slot(2, date(2026, 11, 22)),
        _slot(3, date(2026, 11, 29)),
        _slot(4, date(2026, 12, 6)),
        _slot(5, date(2026, 12, 13)),
        _slot(6, date(2026, 12, 20)),
        _slot(7, date(2026, 12, 27)),
    ]
    aniversarios = {"PENDENTE": date(2000, 11, 15)}

    def alocar(slots_do_bloco, estado):
        meses_tocados = len({s.mes_key for s in slots_do_bloco})
        demanda = calcular_demanda_onda_expansiva(
            regras, vagas_reais_no_periodo=len(slots_do_bloco), meses_tocados=meses_tocados
        )
        return alocar_grupo(
            regras,
            slots_do_bloco,
            estado,
            demanda.mapa_limites_locais,
            mapa_limites_mensais=demanda.mapa_limites_mensais,
            aniversarios=aniversarios,
        )

    resultado = alocar_ronda_dinamica(regras, slots, EstadoExecucaoGrupo(), 1, alocar)
    status_mensal_dez = [
        s for s in resultado.completude.status_por_colaborador
        if s.nome == "Mensal" and s.mes_key == "2026-12"
    ][0]

    assert status_mensal_dez.alocar_todos_os_meses_aplica is True
    assert status_mensal_dez.alocacoes_no_mes == 2
    assert status_mensal_dez.necessidade_restante_no_mes == 0
    assert any("obrigacao 2026-12 = 2" in evento for evento in resultado.eventos)


def test_sequencia_dezembro_ceia_mensal_pendente_mensal():
    regras = [
        _regra("Ceia", prioridade=1, ceia_alternada=True),
        _regra("Mensal", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=True, ceia_alternada=False),
        _regra("Pendente", prioridade=2, semana_preferencial=3, ceia_alternada=False),
    ]
    slots = [
        _slot(1, date(2026, 12, 6)),
        _slot(2, date(2026, 12, 13)),
        _slot(3, date(2026, 12, 20)),
        _slot(4, date(2026, 12, 27)),
    ]
    estado = EstadoExecucaoGrupo()
    demanda = calcular_demanda_onda_expansiva(regras, len(slots), 1)
    decisoes = alocar_grupo(
        regras, slots, estado, demanda.mapa_limites_locais,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
    )

    assert [d.vencedor for d in decisoes] == ["Ceia", "Mensal", "Pendente", "Mensal"]


def test_quinta_semana_nao_vai_automaticamente_para_quota_ja_cumprida():
    regras = [
        _regra("Ceia", prioridade=1, ceia_alternada=True),
        _regra("Mensal", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=True, ceia_alternada=False),
        _regra("Pendente", prioridade=2, semana_preferencial=3, ceia_alternada=False),
        _regra("Restante", prioridade=3, ceia_alternada=False),
    ]
    slots = [
        _slot(1, date(2026, 3, 1)),
        _slot(2, date(2026, 3, 8)),
        _slot(3, date(2026, 3, 15)),
        _slot(4, date(2026, 3, 22)),
        _slot(5, date(2026, 3, 29)),
    ]
    estado = EstadoExecucaoGrupo()
    demanda = calcular_demanda_onda_expansiva(regras, len(slots), 1)
    decisoes = alocar_grupo(
        regras, slots, estado, demanda.mapa_limites_locais,
        mapa_limites_mensais=demanda.mapa_limites_mensais,
    )

    assert [d.vencedor for d in decisoes[:4]] == ["Ceia", "Mensal", "Pendente", "Mensal"]
    assert decisoes[4].vencedor == "Restante"


def test_repeticao_sem_atm_nao_cria_obrigacao_no_novo_mes():
    regras = [
        _regra("MensalLocal", prioridade=1, repeticao_mensal=2, alocar_todos_os_meses=False, ceia_alternada=False),
        _regra("Outro", prioridade=2, ceia_alternada=False),
    ]
    slots = [
        _slot(1, date(2026, 11, 8)),
        _slot(2, date(2026, 11, 15)),
        _slot(3, date(2026, 12, 13)),
    ]
    decisoes = [
        type("D", (), {"vencedor": "MensalLocal", "slot": slots[0]})(),
        type("D", (), {"vencedor": "Outro", "slot": slots[1]})(),
        type("D", (), {"vencedor": "Outro", "slot": slots[2]})(),
    ]

    completude = ronda_esta_completa(regras, decisoes, slots)
    status_dez = [
        s for s in completude.status_por_colaborador
        if s.nome == "MensalLocal" and s.mes_key == "2026-12"
    ][0]

    assert status_dez.necessidade_restante_no_mes == 0
    assert status_dez.alocar_todos_os_meses_aplica is False


def test_obrigacao_ja_cumprida_tem_necessidade_zero():
    regras = [_regra("Mensal", repeticao_mensal=2, alocar_todos_os_meses=True)]
    slots = [_slot(1, date(2026, 12, 13)), _slot(2, date(2026, 12, 27))]
    decisoes = [
        type("D", (), {"vencedor": "Mensal", "slot": slots[0]})(),
        type("D", (), {"vencedor": "Mensal", "slot": slots[1]})(),
    ]

    completude = ronda_esta_completa(regras, decisoes, slots)
    status = completude.status_por_colaborador[0]

    assert status.alocacoes_no_mes == 2
    assert status.necessidade_restante_no_mes == 0
    assert status.repeticao_mensal_satisfeita is True


def test_ronda_dinamica_nao_entra_em_loop_quando_obrigacao_mensal_e_impossivel():
    regras = [_regra("Mensal", repeticao_mensal=2, alocar_todos_os_meses=True)]
    slots = [_slot(1, date(2026, 12, 6))]

    resultado = alocar_ronda_dinamica(
        regras,
        slots,
        EstadoExecucaoGrupo(),
        1,
        lambda bloco, estado: _alocar_dinamico_padrao(regras, bloco, estado),
    )

    assert resultado.completude.completa is False
    assert resultado.diagnostico is not None
    assert "nenhuma participacao-base pendente" in resultado.diagnostico


def test_ceia_persistida_conta_para_repeticao_1_e_bloqueia_ministro_normal():
    regras = [
        _regra(
            "ParticipanteCeia",
            prioridade=1,
            repeticao_mensal=1,
            ceia_alternada=True,
            alocacao_extra=True,
        ),
        _regra("ProximoNormal", prioridade=2, repeticao_mensal=1, ceia_alternada=False),
    ]
    estado = EstadoExecucaoGrupo(
        ocorrencias_mensais_externas={"ParticipanteCeia": {"2026-12": 1}},
        cursor_hierarquia="Anterior",
    )
    slot = _slot(2, date(2026, 12, 13))

    decisoes = alocar_grupo(
        regras,
        [slot],
        estado,
        {"ParticipanteCeia": 10, "ProximoNormal": 10},
        mapa_limites_mensais={"ParticipanteCeia": 2, "ProximoNormal": 1},
    )

    assert decisoes[0].vencedor == "ProximoNormal"
    assert decisoes[0].consome_hierarquia is True
    assert estado.cursor_hierarquia == "ProximoNormal"
    assert ocorrencias_mensais_colaborador(estado, "ParticipanteCeia", "2026-12") == 1


def test_ceia_da_mesma_ronda_conta_para_repeticao_1_mesmo_com_alocacao_extra():
    regras = [
        _regra(
            "ParticipanteCeia",
            prioridade=1,
            repeticao_mensal=1,
            ceia_alternada=True,
            alocacao_extra=True,
        ),
        _regra("ProximoNormal", prioridade=2, repeticao_mensal=1, ceia_alternada=False),
    ]
    estado = EstadoExecucaoGrupo()
    slots = [_slot(1, date(2026, 12, 6)), _slot(2, date(2026, 12, 13))]

    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        {"ParticipanteCeia": 10, "ProximoNormal": 10},
        mapa_limites_mensais={"ParticipanteCeia": 2, "ProximoNormal": 1},
    )

    assert decisoes[0].vencedor == "ParticipanteCeia"
    assert decisoes[0].motivo == "CEIA ALTERNADA"
    assert decisoes[0].consome_hierarquia is False
    assert decisoes[1].vencedor == "ProximoNormal"
    assert decisoes[1].consome_hierarquia is True
    assert ocorrencias_mensais_colaborador(estado, "ParticipanteCeia", "2026-12") == 1


def test_ceia_persistida_com_repeticao_2_permita_uma_normal_e_depois_bloqueia():
    regras = [
        _regra("ParticipanteCeia", prioridade=1, repeticao_mensal=2, ceia_alternada=True),
        _regra("OutroA", prioridade=2, repeticao_mensal=1, ceia_alternada=False),
        _regra("OutroB", prioridade=3, repeticao_mensal=1, ceia_alternada=False),
    ]
    estado = EstadoExecucaoGrupo(
        ocorrencias_mensais_externas={"ParticipanteCeia": {"2026-12": 1}},
    )
    slots = [_slot(2, date(2026, 12, 13)), _slot(3, date(2026, 12, 20))]

    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={"ParticipanteCeia": 2, "OutroA": 1, "OutroB": 1},
    )

    assert decisoes[0].vencedor == "ParticipanteCeia"
    assert decisoes[0].ocorrencias_mes_antes == 1
    assert decisoes[0].ocorrencias_mes_depois == 2
    assert decisoes[1].vencedor == "OutroA"
    assert ocorrencias_mensais_colaborador(estado, "ParticipanteCeia", "2026-12") == 2
    assert necessidade_mensal_restante(estado, regras[0], "2026-12", {"ParticipanteCeia": 2}) == 0


def test_ceia_persistida_com_repeticao_3_deixa_faltar_uma_apos_normal():
    regra = _regra("ParticipanteCeia", prioridade=1, repeticao_mensal=3, ceia_alternada=True)
    estado = EstadoExecucaoGrupo(
        ocorrencias_mensais_externas={"ParticipanteCeia": {"2026-12": 1}},
    )
    slot = _slot(2, date(2026, 12, 13))

    decisoes = alocar_grupo(
        [regra],
        [slot],
        estado,
        {"ParticipanteCeia": 10},
        mapa_limites_mensais={"ParticipanteCeia": 3},
    )

    assert decisoes[0].vencedor == "ParticipanteCeia"
    assert ocorrencias_mensais_colaborador(estado, "ParticipanteCeia", "2026-12") == 2
    assert necessidade_mensal_restante(estado, regra, "2026-12", {"ParticipanteCeia": 3}) == 1


def test_candidato_pulado_por_quota_de_ceia_nao_consumiu_cursor():
    regras = [
        _regra("P3QuotaCheia", prioridade=3, repeticao_mensal=1, ceia_alternada=True),
        _regra("P4Elegivel", prioridade=4, repeticao_mensal=1, ceia_alternada=False),
    ]
    estado = EstadoExecucaoGrupo(
        cursor_hierarquia="P2Ancora",
        ocorrencias_mensais_externas={"P3QuotaCheia": {"2026-12": 1}},
    )
    slot = _slot(2, date(2026, 12, 13))

    decisoes = alocar_grupo(
        regras,
        [slot],
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={"P3QuotaCheia": 1, "P4Elegivel": 1},
    )

    assert decisoes[0].vencedor == "P4Elegivel"
    assert decisoes[0].consome_hierarquia is True
    assert estado.cursor_hierarquia == "P4Elegivel"
    assert "P3QuotaCheia" not in estado.hierarquia_consumida_na_ronda


def test_ceia_persistida_nao_consumiu_hierarquia_quando_outro_ministro_e_escolhido():
    regras = [_regra("CeiaExterna", prioridade=1), _regra("Normal", prioridade=2)]
    estado = EstadoExecucaoGrupo(
        cursor_hierarquia="CeiaExterna",
        ocorrencias_mensais_externas={"CeiaExterna": {"2026-12": 1}},
    )

    decisao = alocar_grupo(
        regras,
        [_slot(2, date(2026, 12, 13))],
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={"CeiaExterna": 1, "Normal": 1},
    )[0]

    assert decisao.vencedor == "Normal"
    assert decisao.consome_hierarquia is True
    assert estado.cursor_hierarquia == "Normal"


def test_ceia_persistida_com_atm_repeticao_2_deixa_necessidade_um():
    regra = _regra(
        "MensalTodoMes",
        prioridade=1,
        repeticao_mensal=2,
        alocar_todos_os_meses=True,
        ceia_alternada=True,
    )
    estado = EstadoExecucaoGrupo(
        ocorrencias_mensais_externas={"MensalTodoMes": {"2026-12": 1}},
    )

    assert necessidade_mensal_restante(estado, regra, "2026-12", {"MensalTodoMes": 2}) == 1


def test_ceia_persistida_com_atm_repeticao_1_satisfaz_obrigacao_mensal():
    regra = _regra(
        "MensalTodoMes",
        prioridade=1,
        repeticao_mensal=1,
        alocar_todos_os_meses=True,
        ceia_alternada=True,
    )
    slots = [_slot(1, date(2026, 12, 6))]
    completude = ronda_esta_completa(
        [regra],
        [],
        slots,
        ocorrencias_mensais_externas={"MensalTodoMes": {"2026-12": 1}},
    )

    assert completude.completa is True
    status = completude.status_por_colaborador[0]
    assert status.alocacoes_no_mes == 1
    assert status.necessidade_restante_no_mes == 0


def test_quota_cheia_por_ceia_nao_volta_mesmo_se_proximo_tem_outro_bloqueio():
    regras = [
        _regra("QuotaCheia", prioridade=1, repeticao_mensal=1, ceia_alternada=True),
        _regra("BloqueadoSemana", prioridade=2, semana_preferencial=5, ceia_alternada=False),
        _regra("TerceiroElegivel", prioridade=3, ceia_alternada=False),
    ]
    estado = EstadoExecucaoGrupo(
        ocorrencias_mensais_externas={"QuotaCheia": {"2026-12": 1}},
    )

    decisao = alocar_grupo(
        regras,
        [_slot(2, date(2026, 12, 13))],
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={r.nome: r.cota_base for r in regras},
    )[0]

    assert decisao.vencedor == "TerceiroElegivel"
    assert ocorrencias_mensais_colaborador(estado, "QuotaCheia", "2026-12") == 1
