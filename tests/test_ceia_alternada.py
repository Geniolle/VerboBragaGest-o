from datetime import date

from pastoreio_orquestrador.carregamento import (
    carregar_historico_ceia_persistido,
    carregar_historico_coluna_agenda,
)
from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    calcular_participantes_ciclo_ceia,
    esta_bloqueado_por_descanso_cruzado,
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


def _slot(row_index: int, d: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=d,
        dia_da_semana="DOMINGO",
        tema="",
        mes_key=f"{d.year:04d}-{d.month:02d}",
        semana_do_mes=week_of_month(d),
        is_ultima_ocorrencia_do_mes=False,
    )


def test_preenchimento_de_lacuna_nao_recoloca_quem_ja_cumpriu_quota_por_ceia():
    # X (prioridade 1) e Y (prioridade 2) sao os unicos dois candidatos,
    # ambos com ALOCACAO_EXTRA=True. Com so 4 domingos de novembro/2026 e
    # cota de 1/mes cada, a Fase 3 fecha o CEIA (slot 1) com X e o slot 2
    # com Y, esgotando o pool normal -- slots 3 e 4 caem para a Fase 4
    # (PREENCHIMENTO DE LACUNA). Antes da correcao (2026-09-07, pedido do
    # Clayton), a Fase 4 sempre escolhia X (maior prioridade) para as duas
    # lacunas. Com a regra atual, X nao volta porque ja cumpriu a quota pela
    # CEIA; Y so entra quando nao viola vizinhanca de datas.
    regras = [
        _regra("X", prioridade=1, alocacao_extra=1),
        _regra("Y", prioridade=2, alocacao_extra=1),
    ]
    slots = [
        _slot(1, date(2026, 11, 1)),
        _slot(2, date(2026, 11, 8)),
        _slot(3, date(2026, 11, 15)),
        _slot(4, date(2026, 11, 22)),
    ]
    estado = EstadoExecucaoGrupo()
    limites = {"X": 1, "Y": 1}

    decisoes = alocar_grupo(regras, slots, estado, limites)

    assert decisoes[0].vencedor == "X"
    assert decisoes[0].motivo == "CEIA ALTERNADA"
    assert decisoes[1].vencedor == "Y"
    assert decisoes[1].motivo == "ALOCAÇÃO NORMAL"
    assert decisoes[2].vencedor is None
    assert decisoes[2].sem_alocacao is True
    assert decisoes[3].vencedor == "Y"
    assert decisoes[3].motivo == "PREENCHIMENTO DE LACUNA"
    assert decisoes[3].tipo_dia == "DOMINGO_NORMAL"
    assert decisoes[3].intent == "GAP_FILL"
    assert decisoes[3].politica_selecao == "GAP_FILL_EXTRA_HIERARCHY"


def test_ceia_alternada_faz_rodizio_completo_entre_todos_os_elegiveis():
    # 3 elegiveis a CEIA (X prioridade 1, Y prioridade 2, Z prioridade 3).
    # Regra do rodizio completo (2026-09-07, pedido do Clayton): ninguem
    # repete a CEIA ate que TODOS os outros da hierarquia ja tenham sido
    # escolhidos desde a ultima vez -- nao basta excluir so o vencedor
    # imediatamente anterior. Com 3 elegiveis, a ordem tem que ser
    # estritamente X, Y, Z, X, Y, Z... (nunca X de novo logo depois de Y).
    regras = [
        _regra("X", prioridade=1),
        _regra("Y", prioridade=2),
        _regra("Z", prioridade=3),
    ]
    slots = [
        _slot(1, date(2026, 1, 4)),
        _slot(2, date(2026, 2, 1)),
        _slot(3, date(2026, 3, 1)),
        _slot(4, date(2026, 4, 5)),
    ]
    estado = EstadoExecucaoGrupo()
    limites = {"X": 10, "Y": 10, "Z": 10}

    decisoes = alocar_grupo(regras, slots, estado, limites)

    vencedores = [d.vencedor for d in decisoes]
    assert vencedores == ["X", "Y", "Z", "X"]


def test_preenchimento_de_lacuna_faz_rodizio_entre_execucoes_com_mesmo_estado():
    # Simula duas "Rondas" separadas (duas chamadas a alocar_grupo)
    # reaproveitando o mesmo `estado` -- exatamente como o replay entre
    # execucoes precisa fazer. X e Y (ATM=false, extra=true) esgotam o pool
    # normal em cada Ronda (3 datas para 2 pessoas), empurrando a 3a data
    # de cada Ronda para a Fase 4. mapa_limites_mensais reseta a cota por
    # mes-calendario (Ronda 1=novembro, Ronda 2=dezembro), entao a cota nao
    # bloqueia em dezembro e nao aciona resgate antes da Fase 4. Antes da
    # correcao, o anti-repeticao da Fase 4 vivia num `set` local que
    # reiniciava a cada chamada -- a Ronda 2 podia repetir quem tinha
    # acabado de fechar a lacuna na Ronda 1. Com o historico no `estado`,
    # o rodizio continua entre chamadas.
    regras = [
        _regra("X", prioridade=1, alocacao_extra=1),
        _regra("Y", prioridade=2, alocacao_extra=1),
    ]
    estado = EstadoExecucaoGrupo()
    mapa_mensal = {"X": 1, "Y": 1}

    slots_ronda1 = [
        _slot(1, date(2026, 11, 8)), _slot(2, date(2026, 11, 15)), _slot(3, date(2026, 11, 22)),
    ]
    decisoes_ronda1 = alocar_grupo(
        regras, slots_ronda1, estado, {}, mapa_limites_mensais=mapa_mensal
    )
    assert decisoes_ronda1[2].motivo == "PREENCHIMENTO DE LACUNA"
    vencedor_lacuna_ronda1 = decisoes_ronda1[2].vencedor

    slots_ronda2 = [
        _slot(4, date(2026, 12, 13)), _slot(5, date(2026, 12, 20)), _slot(6, date(2026, 12, 27)),
    ]
    decisoes_ronda2 = alocar_grupo(
        regras, slots_ronda2, estado, {}, mapa_limites_mensais=mapa_mensal
    )
    assert decisoes_ronda2[2].motivo == "PREENCHIMENTO DE LACUNA"
    # CORRECAO 2026-09-07 (mesmo dia, pedido do Clayton -- "a regra da
    # vizinhanca... esse doi e sobre a datas"): a "vizinhanca de datas" (nao
    # repetir em datas CONSECUTIVAS da propria sequencia do grupo) agora e
    # obrigatoria e tem PRECEDENCIA sobre o rodizio de justica entre
    # execucoes. Nesta Ronda 2, a data imediatamente anterior a lacuna
    # (Dec/20) foi vencida por quem o rodizio favorecia (o "outro" desde a
    # Ronda 1) -- reaproveita-lo aqui violaria a vizinhanca de datas, entao
    # a Fase 4 reorganiza e usa quem NAO e vizinho da data anterior, mesmo
    # que isso repita o vencedor da lacuna da Ronda 1 (Nov/22 e Dez/27 nao
    # sao datas consecutivas -- so o rodizio de justica, um criterio mais
    # fraco, teria evitado essa repeticao).
    assert decisoes_ronda2[2].vencedor == vencedor_lacuna_ronda1


def test_preenchimento_de_lacuna_nao_repete_unico_extra_quando_quota_foi_cumprida_por_ceia():
    # So um candidato com ALOCACAO_EXTRA=True.
    #
    # CORRECAO 2026-09-07 (mesmo dia, pedido do Clayton -- "a regra da
    # vizinhanca... esse doi e sobre a datas", "SEM ALOCACAO e quando e
    # impossivel alguma alocacao"): antes, a Fase 4 repetia o unico
    # candidato mesmo em datas consecutivas por falta de alternativa. Agora,
    # como a CEIA conta para REPETICAO MENSAL, um unico candidato com cota 1
    # ja esta satisfeito no primeiro domingo e nao volta nas datas normais.
    regras = [_regra("X", prioridade=1, alocacao_extra=1)]
    slots = [
        _slot(1, date(2026, 11, 1)),
        _slot(2, date(2026, 11, 15)),
        _slot(3, date(2026, 11, 22)),
    ]
    estado = EstadoExecucaoGrupo()
    limites = {"X": 1}

    decisoes = alocar_grupo(regras, slots, estado, limites)

    assert decisoes[0].vencedor == "X"
    assert decisoes[0].motivo == "CEIA ALTERNADA"
    assert decisoes[1].vencedor is None
    assert decisoes[1].sem_alocacao is True
    assert decisoes[2].vencedor is None
    assert decisoes[2].sem_alocacao is True


def test_lacuna_nao_reorganiza_para_recolocar_quem_ja_cumpriu_quota_por_ceia():
    # Reproduz o cenario real (Andre Luiz/Caio Lima, 22 e 29/11) que motivou
    # a "vizinhanca de datas" (2026-09-07, pedido do Clayton). A hierarquia
    # de PREENCHIMENTO DE LACUNA (X, Y -- ALOCAR_TODOS_OS_MESES=false E
    # ALOCACAO_EXTRA=true) tem 2 pessoas; ambas ja gastaram sua cota normal
    # em datas anteriores (Y na 2a semana, W -- fora da hierarquia -- na 3a),
    # deixando as duas ULTIMAS datas (consecutivas entre si) sem fechar na
    # Fase 3 -> caem na Fase 4. Ali a escolha gulosa por prioridade coloca X
    # nas DUAS (violando a vizinhanca), e Y fica bloqueado por Excluse so na
    # SEGUNDA.
    #
    # CORRECAO 2026-09-07 (mesmo dia, pedido do Clayton apos eu ter ampliado
    # erradamente para o GRUPO INTEIRO -- "era so preciso reorganizar os
    # mesmos colaboradores que tinhas na linha... reordenar os dias daquela
    # rotacao"): em vez de puxar alguem de fora da hierarquia, o motor
    # Antes a Fase 4 podia reorganizar para recolocar X. Agora X fica
    # bloqueado porque ja cumpriu a quota pela CEIA; Y cobre a primeira
    # lacuna e a segunda fica sem alocacao quando Y esta em Excluse.
    regras = [
        _regra("X", prioridade=1, alocacao_extra=1),
        _regra("Y", prioridade=2, alocacao_extra=1),
        _regra("W", prioridade=3, alocacao_extra=0),  # fora da hierarquia de lacuna; so preenche a normal.
    ]
    excluse_header = {"COLUNAS": 0, "ID_MINISTROS": 1}
    excluse_rows = [["MINISTRO", "BLOQUEIO_Y"]]

    def _slot_domingo(row_index, d, semana_do_mes, papeis=None):
        return SlotAgenda(
            row_index=row_index, data=d, dia_da_semana="DOMINGO", tema="",
            mes_key="2026-01", semana_do_mes=semana_do_mes,
            is_ultima_ocorrencia_do_mes=False, papeis=papeis or {},
        )

    slots = [
        _slot_domingo(1, date(2026, 1, 4), 1),    # CEIA -- X vence (prioridade 1).
        _slot_domingo(2, date(2026, 1, 11), 2),   # normal -- Y vence (prioridade 2, cota propria).
        _slot_domingo(3, date(2026, 1, 18), 3),   # normal -- W vence (unico que sobra com cota).
        # As duas datas seguintes, consecutivas entre si, ficam sem fechar
        # na Fase 3 (ninguem mais tem cota disponivel) e caem na Fase 4. Y
        # so e bloqueado por Excluse na SEGUNDA delas.
        _slot_domingo(4, date(2026, 1, 25), 4),
        _slot_domingo(5, date(2026, 2, 1), 5, papeis={"BLOQUEIO_Y": "Y"}),
    ]
    estado = EstadoExecucaoGrupo()
    mapa_mensal = {"X": 1, "Y": 1, "W": 1}

    decisoes = alocar_grupo(
        regras, slots, estado, {}, mapa_limites_mensais=mapa_mensal,
        excluse_header=excluse_header, excluse_rows=excluse_rows,
    )

    assert decisoes[0].vencedor == "X" and decisoes[0].motivo == "CEIA ALTERNADA"
    assert decisoes[1].vencedor == "Y" and decisoes[1].motivo == "ALOCAÇÃO NORMAL"
    assert decisoes[2].vencedor == "W" and decisoes[2].motivo == "ALOCAÇÃO NORMAL"
    # A primeira lacuna ainda pode ser preenchida por Y. Na segunda, Y esta
    # bloqueado por Excluse e X nao pode voltar porque ja cumpriu a quota
    # mensal pela CEIA.
    assert decisoes[3].vencedor == "Y" and decisoes[3].motivo == "PREENCHIMENTO DE LACUNA"
    assert decisoes[4].vencedor is None and decisoes[4].sem_alocacao is True


def test_aniversariante_nao_pode_ser_alocado_no_proprio_dia():
    # Caso real (2026-09-07, pedido do Clayton): Patricia Lopes nasceu em
    # 25/10 e havia sido alocada em 25/10/2026 antes desta regra existir.
    # X (prioridade 1) nasceu no mesmo dia do unico slot (o CEIA); mesmo
    # sendo o candidato de maior prioridade e o unico com CEIA_ALTERNADA
    # nesta hierarquia reduzida, o aniversario bloqueia X e Y (prioridade 2)
    # vence em seu lugar -- so o ANO do nascimento e ignorado (X nasceu em
    # 1974, o slot e de 2026).
    regras = [
        _regra("X", prioridade=1),
        _regra("Y", prioridade=2),
    ]
    slots = [_slot(1, date(2026, 11, 1))]
    estado = EstadoExecucaoGrupo()
    aniversarios = {"X": date(1974, 11, 1)}

    decisoes = alocar_grupo(regras, slots, estado, {}, aniversarios=aniversarios)

    assert decisoes[0].vencedor == "Y"


def test_aniversariante_fica_sem_alocacao_quando_e_o_unico_candidato():
    # Se o unico candidato elegivel faz aniversario justamente na data do
    # slot, o resultado correto e SEM ALOCACAO -- nao ha ninguem para
    # substitui-lo.
    regras = [_regra("X", prioridade=1)]
    slots = [_slot(1, date(2026, 11, 1))]
    estado = EstadoExecucaoGrupo()
    aniversarios = {"X": date(1974, 11, 1)}

    decisoes = alocar_grupo(regras, slots, estado, {}, aniversarios=aniversarios)

    assert decisoes[0].vencedor is None
    assert decisoes[0].motivo == "SEM ALOCAÇÃO"


def test_cenario_1_primeiro_domingo_ceia_prevalece_sobre_semana_preferencial_1_ja_participada():
    # CENARIO 1:
    # - primeiro domingo;
    # - existem varios CEIA ALTERNADA = TRUE;
    # - um deles tem SEMANA PREFERENCIAL = 1;
    # - ele ja participou no ciclo;
    # - outro ainda nao participou;
    # RESULTADO:
    # deve escolher quem ainda nao participou.
    # A semana preferencial nao pode vencer o rodizio da CEIA.
    colab_a = _regra("ColabA", prioridade=1, ceia_alternada=True, semana_preferencial=1)
    colab_b = _regra("ColabB", prioridade=2, ceia_alternada=True, semana_preferencial=0)
    slots = [_slot(1, date(2026, 2, 1))]  # 1o domingo de fevereiro
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=["ColabA"])
    limites = {"ColabA": 10, "ColabB": 10}

    decisoes = alocar_grupo([colab_a, colab_b], slots, estado, limites)

    assert decisoes[0].vencedor == "ColabB"
    assert decisoes[0].motivo == "CEIA ALTERNADA"


def test_cenario_2_primeiro_domingo_proximo_bloqueado_por_excluse_mantem_pendente_no_ciclo():
    # CENARIO 2:
    # - primeiro domingo;
    # - proximo da rotacion esta bloqueado por Excluse;
    # RESULTADO:
    # deve escolher o proximo elegivel sem considerar o bloqueado como tendo cumprido a vez.
    colab_a = _regra("ColabA", prioridade=1, ceia_alternada=True)
    colab_b = _regra("ColabB", prioridade=2, ceia_alternada=True)
    colab_c = _regra("ColabC", prioridade=3, ceia_alternada=True)
    regras = [colab_a, colab_b, colab_c]
    limites = {"ColabA": 10, "ColabB": 10, "ColabC": 10}

    # Mes 1: ColabA participa
    slots_mes1 = [_slot(1, date(2026, 1, 4))]
    estado = EstadoExecucaoGrupo()
    decisoes_mes1 = alocar_grupo(regras, slots_mes1, estado, limites)
    assert decisoes_mes1[0].vencedor == "ColabA"

    # Mes 2: ColabB (proximo da rotacao) esta bloqueado por Excluse
    excluse_header = {"COLUNAS": 0, "ID_MINISTROS": 1}
    excluse_rows = [["MINISTRO", "BLOQUEIO_B"]]
    slots_mes2 = [
        SlotAgenda(
            row_index=2,
            data=date(2026, 2, 1),
            dia_da_semana="DOMINGO",
            tema="",
            mes_key="2026-02",
            semana_do_mes=1,
            is_ultima_ocorrencia_do_mes=False,
            papeis={"BLOQUEIO_B": "ColabB"},
        )
    ]
    decisoes_mes2 = alocar_grupo(
        regras, slots_mes2, estado, limites,
        excluse_header=excluse_header, excluse_rows=excluse_rows,
    )
    # Deve escolher ColabC (proximo elegivel)
    assert decisoes_mes2[0].vencedor == "ColabC"

    # Mes 3: ColabB agora esta desbloqueado.
    # ColabA e ColabC ja participaram no ciclo; ColabB continua pendente!
    slots_mes3 = [_slot(3, date(2026, 3, 1))]
    decisoes_mes3 = alocar_grupo(regras, slots_mes3, estado, limites)
    # ColabB deve ser o escolhido, pois nao cumpriu a vez no mes 2
    assert decisoes_mes3[0].vencedor == "ColabB"


def test_cenario_3_todos_participantes_ceia_ja_participaram_inicia_novo_ciclo():
    # CENARIO 3:
    # - todos os participantes elegiveis da CEIA ja participaram;
    # RESULTADO:
    # pode iniciar um novo ciclo de CEIA.
    colab_a = _regra("ColabA", prioridade=1, ceia_alternada=True)
    colab_b = _regra("ColabB", prioridade=2, ceia_alternada=True)
    colab_c = _regra("ColabC", prioridade=3, ceia_alternada=True)
    regras = [colab_a, colab_b, colab_c]
    limites = {"ColabA": 10, "ColabB": 10, "ColabC": 10}

    # Todos os 3 ja participaram no historico
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=["ColabA", "ColabB", "ColabC"])
    slots = [_slot(1, date(2026, 4, 5))]  # 1o domingo de abril

    decisoes = alocar_grupo(regras, slots, estado, limites)

    # Novo ciclo inicia: o de maior prioridade (ColabA) e escolhido
    assert decisoes[0].vencedor == "ColabA"
    assert decisoes[0].motivo == "CEIA ALTERNADA"


def test_ceia_ultimo_pendente_fecha_ciclo():
    regras = [
        _regra("A", prioridade=1),
        _regra("B", prioridade=2),
        _regra("C", prioridade=3),
        _regra("D", prioridade=4),
    ]
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=["A", "B", "C"])

    decisoes = alocar_grupo(regras, [_slot(1, date(2027, 4, 4))], estado, {})

    assert decisoes[0].vencedor == "D"
    assert calcular_participantes_ciclo_ceia(
        {"A", "B", "C", "D"}, estado.historico_vencedores_ceia
    ) == set()


def test_ceia_ciclo_completo_recomeca_no_primeiro_da_ordem():
    regras = [
        _regra("A", prioridade=1),
        _regra("B", prioridade=2),
        _regra("C", prioridade=3),
        _regra("D", prioridade=4),
    ]
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=["A", "B", "C", "D"])

    decisoes = alocar_grupo(regras, [_slot(1, date(2027, 5, 2))], estado, {})

    assert decisoes[0].vencedor == "A"
    assert decisoes[0].motivo == "CEIA ALTERNADA"


def test_ceia_dois_ciclos_completos_sem_repetir_ultimo_no_reset():
    regras = [
        _regra("A", prioridade=1),
        _regra("B", prioridade=2),
        _regra("C", prioridade=3),
        _regra("D", prioridade=4),
    ]
    slots = [
        _slot(1, date(2027, 1, 3)),
        _slot(2, date(2027, 2, 7)),
        _slot(3, date(2027, 3, 7)),
        _slot(4, date(2027, 4, 4)),
        _slot(5, date(2027, 5, 2)),
        _slot(6, date(2027, 6, 6)),
        _slot(7, date(2027, 7, 4)),
        _slot(8, date(2027, 8, 1)),
    ]

    limites = {"A": 10, "B": 10, "C": 10, "D": 10}

    decisoes = alocar_grupo(regras, slots, EstadoExecucaoGrupo(), limites)

    assert [d.vencedor for d in decisoes] == ["A", "B", "C", "D", "A", "B", "C", "D"]


def test_ceia_cenario_real_davi_fecha_ciclo_maio_recomeca_primeiro():
    regras = [
        _regra("Clayton Lopes", prioridade=1),
        _regra("Patricia Lopes", prioridade=2),
        _regra("Caio Lima", prioridade=3),
        _regra("Ana Lima", prioridade=4),
        _regra("Andre Luiz", prioridade=5),
        _regra("Suzana Fonseca", prioridade=6),
        _regra("Davi Fenner", prioridade=7),
    ]
    estado = EstadoExecucaoGrupo(
        historico_vencedores_ceia=[
            "Clayton Lopes",
            "Patricia Lopes",
            "Caio Lima",
            "Ana Lima",
            "Andre Luiz",
            "Suzana Fonseca",
        ]
    )

    abril = alocar_grupo(regras, [_slot(1, date(2027, 4, 4))], estado, {})
    maio = alocar_grupo(regras, [_slot(2, date(2027, 5, 2))], estado, {})

    assert abril[0].vencedor == "Davi Fenner"
    assert maio[0].vencedor == "Clayton Lopes"


def test_ceia_processo_reiniciado_reconstroi_ciclo_completo_da_agenda():
    agenda = [
        ["DATA", "DIA DA SEMANA", "CEIA"],
        ["03/01/2027", "DOMINGO", "A"],
        ["07/02/2027", "DOMINGO", "B"],
        ["07/03/2027", "DOMINGO", "C"],
        ["04/04/2027", "DOMINGO", "D"],
        ["02/05/2027", "DOMINGO", ""],
    ]
    historico = carregar_historico_coluna_agenda(
        agenda,
        dia_da_semana="DOMINGO",
        coluna_participacao="CEIA",
        nomes_validos={"A": "A", "B": "B", "C": "C", "D": "D"},
        somente_primeiro_domingo=True,
        antes_de=date(2027, 5, 2),
    )
    regras = [
        _regra("A", prioridade=1),
        _regra("B", prioridade=2),
        _regra("C", prioridade=3),
        _regra("D", prioridade=4),
    ]
    assert historico == ["A", "B", "C", "D"]
    estado_novo_processo = EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico))

    decisoes = alocar_grupo(regras, [_slot(5, date(2027, 5, 2))], estado_novo_processo, {})

    assert decisoes[0].vencedor == "A"


def test_ceia_domingo_reiniciado_usa_historico_persistido_e_nao_replay_incompleto():
    agenda = [
        ["DATA", "DIA DA SEMANA", "MINISTRO", "CEIA"],
        ["04/10/2026", "DOMINGO", "A", ""],
        ["01/11/2026", "DOMINGO", "B", ""],
        ["06/12/2026", "DOMINGO", "C", ""],
        ["03/01/2027", "DOMINGO", "D", ""],
        ["07/02/2027", "DOMINGO", "E", ""],
        ["07/03/2027", "DOMINGO", "F", ""],
        ["04/04/2027", "DOMINGO", "G", ""],
        ["02/05/2027", "DOMINGO", "", ""],
    ]
    auditoria = [
        ["DATA_SLOT", "VENCEDOR", "MOTIVO", "INTENCAO_ALOCACAO", "TIPO_ALOCACAO"],
        ["2026-10-04", "A", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2026-11-01", "B", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2026-12-06", "C", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2027-01-03", "D", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2027-02-07", "E", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2027-03-07", "F", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2027-04-04", "G", "CEIA ALTERNADA", "CEIA", "CEIA"],
    ]
    regras = [_regra(nome, prioridade=i) for i, nome in enumerate("ABCDEFG", start=1)]

    historico = carregar_historico_ceia_persistido(
        agenda,
        auditoria,
        dia_da_semana="DOMINGO",
        coluna_alocacao="MINISTRO",
        nomes_validos={r.nome: r.nome for r in regras},
        antes_de=date(2027, 5, 2),
    )
    assert historico == list("ABCDEFG")
    estado_novo_processo = EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico))

    usados = calcular_participantes_ciclo_ceia(
        {r.nome for r in regras if r.ceia_alternada},
        estado_novo_processo.historico_vencedores_ceia,
    )
    decisoes = alocar_grupo(regras, [_slot(8, date(2027, 5, 2))], estado_novo_processo, {})

    assert usados == set()
    assert decisoes[0].vencedor == "A"
    assert decisoes[0].vencedor != "G"


def test_ceia_historico_antes_da_data_corte_nao_entra_no_novo_motor():
    agenda = [
        ["DATA", "DIA DA SEMANA", "MINISTRO"],
        ["02/08/2026", "DOMINGO", "Davi"],
        ["06/09/2026", "DOMINGO", "Andre"],
        ["04/10/2026", "DOMINGO", ""],
    ]
    auditoria = [
        ["DATA_SLOT", "VENCEDOR", "MOTIVO", "INTENCAO_ALOCACAO", "TIPO_ALOCACAO"],
        ["2026-08-02", "Davi", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2026-09-06", "Andre", "CEIA ALTERNADA", "CEIA", "CEIA"],
    ]
    regras = [_regra("Clayton", prioridade=1), _regra("Andre", prioridade=2), _regra("Davi", prioridade=3)]

    historico = carregar_historico_ceia_persistido(
        agenda,
        auditoria,
        dia_da_semana="DOMINGO",
        coluna_alocacao="MINISTRO",
        nomes_validos={r.nome.upper(): r.nome for r in regras},
        antes_de=date(2026, 10, 4),
        data_corte_historico=date(2026, 10, 1),
    )
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico))
    decisoes = alocar_grupo(regras, [_slot(1, date(2026, 10, 4))], estado, {})

    assert historico == []
    assert decisoes[0].vencedor == "Clayton"


def test_ceia_ciclo_completo_depois_da_data_corte_recomeca_no_primeiro():
    agenda = [
        ["DATA", "DIA DA SEMANA", "MINISTRO"],
        ["06/09/2026", "DOMINGO", "D"],
        ["04/10/2026", "DOMINGO", "A"],
        ["01/11/2026", "DOMINGO", "B"],
        ["06/12/2026", "DOMINGO", "C"],
        ["03/01/2027", "DOMINGO", "D"],
        ["07/02/2027", "DOMINGO", ""],
    ]
    auditoria = [
        ["DATA_SLOT", "VENCEDOR", "MOTIVO", "INTENCAO_ALOCACAO", "TIPO_ALOCACAO"],
        ["2026-09-06", "D", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2026-10-04", "A", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2026-11-01", "B", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2026-12-06", "C", "CEIA ALTERNADA", "CEIA", "CEIA"],
        ["2027-01-03", "D", "CEIA ALTERNADA", "CEIA", "CEIA"],
    ]
    regras = [_regra(nome, prioridade=i) for i, nome in enumerate("ABCD", start=1)]

    historico = carregar_historico_ceia_persistido(
        agenda,
        auditoria,
        dia_da_semana="DOMINGO",
        coluna_alocacao="MINISTRO",
        nomes_validos={r.nome: r.nome for r in regras},
        antes_de=date(2027, 2, 7),
        data_corte_historico=date(2026, 10, 1),
    )
    usados = calcular_participantes_ciclo_ceia({r.nome for r in regras}, historico)
    decisoes = alocar_grupo(
        regras,
        [_slot(1, date(2027, 2, 7))],
        EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico)),
        {},
    )

    assert historico == list("ABCD")
    assert usados == set()
    assert decisoes[0].vencedor == "A"


def test_descanso_cruzado_consulta_fato_real_anterior_ao_corte():
    bloqueado = esta_bloqueado_por_descanso_cruzado(
        "Pessoa A",
        date(2026, 10, 4),
        {"PESSOA A": [date(2026, 9, 30)]},
    )

    assert bloqueado is True


def test_ceia_historico_persistido_de_dois_ciclos_completos_recomeca():
    regras = [_regra(nome, prioridade=i) for i, nome in enumerate("ABCD", start=1)]
    historico = list("ABCDABCD")
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico))

    usados = calcular_participantes_ciclo_ceia({r.nome for r in regras}, historico)
    decisoes = alocar_grupo(regras, [_slot(9, date(2027, 9, 5))], estado, {})

    assert usados == set()
    assert decisoes[0].vencedor == "A"


def test_ceia_historico_persistido_incompleto_mantem_pendente():
    regras = [_regra(nome, prioridade=i) for i, nome in enumerate("ABCD", start=1)]
    historico = list("ABC")
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico))

    usados = calcular_participantes_ciclo_ceia({r.nome for r in regras}, historico)
    decisoes = alocar_grupo(regras, [_slot(10, date(2027, 4, 4))], estado, {})

    assert usados == {"A", "B", "C"}
    assert decisoes[0].vencedor == "D"


def test_ceia_historico_com_novo_participante_configurado_pede_o_novo_nome():
    # O passado A-B-C-D nao e reescrito. Com E ativo hoje, o ciclo vigente e
    # avaliado contra o conjunto atual A-B-C-D-E, entao E fica pendente.
    regras = [_regra(nome, prioridade=i) for i, nome in enumerate("ABCDE", start=1)]
    historico = list("ABCD")
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico))

    usados = calcular_participantes_ciclo_ceia({r.nome for r in regras}, historico)
    decisoes = alocar_grupo(regras, [_slot(11, date(2027, 5, 2))], estado, {})

    assert usados == {"A", "B", "C", "D"}
    assert decisoes[0].vencedor == "E"


def test_ceia_historico_com_participante_desativado_nao_quebra_e_usa_conjunto_atual():
    # D participou no passado, mas nao esta no conjunto CEIA atual. O ciclo e
    # calculado contra A-B-C; ao ler A-B-C o ciclo atual fecha e a proxima
    # CEIA comeca de novo pela ordem vigente.
    regras = [_regra(nome, prioridade=i) for i, nome in enumerate("ABC", start=1)]
    historico = list("ABCD")
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=list(historico))

    usados = calcular_participantes_ciclo_ceia({r.nome for r in regras}, historico)
    decisoes = alocar_grupo(regras, [_slot(12, date(2027, 5, 2))], estado, {})

    assert usados == set()
    assert decisoes[0].vencedor == "A"


def test_ceia_primeiro_do_novo_ciclo_bloqueado_nao_e_marcado_como_usado():
    regras = [
        _regra("A", prioridade=1),
        _regra("B", prioridade=2),
        _regra("C", prioridade=3),
        _regra("D", prioridade=4),
    ]
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=["A", "B", "C", "D"])
    excluse_header = {"COLUNAS": 0, "ID_MINISTROS": 1}
    excluse_rows = [["MINISTRO", "BLOQUEIO_A"]]
    slot_bloqueado = SlotAgenda(
        row_index=10,
        data=date(2027, 5, 2),
        dia_da_semana="DOMINGO",
        tema="",
        mes_key="2027-05",
        semana_do_mes=1,
        is_ultima_ocorrencia_do_mes=False,
        papeis={"BLOQUEIO_A": "A"},
    )

    decisoes = alocar_grupo(
        regras,
        [slot_bloqueado],
        estado,
        {},
        excluse_header=excluse_header,
        excluse_rows=excluse_rows,
    )

    assert decisoes[0].vencedor == "B"
    usados = calcular_participantes_ciclo_ceia({"A", "B", "C", "D"}, estado.historico_vencedores_ceia)
    assert usados == {"B"}
    assert "A" not in usados


def test_ceia_novo_ciclo_usa_ordem_atual_quando_configuracao_muda():
    estado = EstadoExecucaoGrupo(historico_vencedores_ceia=["A", "B", "C", "D"])
    regras_ordem_atual = [
        _regra("C", prioridade=1),
        _regra("A", prioridade=2),
        _regra("B", prioridade=3),
        _regra("D", prioridade=4),
    ]

    decisoes = alocar_grupo(regras_ordem_atual, [_slot(1, date(2027, 5, 2))], estado, {})

    assert decisoes[0].vencedor == "C"


def test_cenario_4_domingo_nao_primeiro_semana_preferencial_vence_prioridade():
    # CENARIO 4:
    # - domingo que NAO e o primeiro domingo;
    # - existe colaborador elegivel com SEMANA PREFERENCIAL correspondente;
    # RESULTADO:
    # semana preferencial vence prioridade.
    colab_a = _regra("ColabA", prioridade=1, semana_preferencial=0)
    colab_b = _regra("ColabB", prioridade=10, semana_preferencial=2)
    slots = [_slot(1, date(2026, 1, 11))]  # 2o domingo (semana_do_mes == 2)
    estado = EstadoExecucaoGrupo()
    limites = {"ColabA": 10, "ColabB": 10}

    decisoes = alocar_grupo([colab_a, colab_b], slots, estado, limites)

    assert decisoes[0].vencedor == "ColabB"


def test_cenario_5_domingo_normal_sem_semana_preferencial_usa_prioridade():
    # CENARIO 5:
    # - domingo normal;
    # - ninguem tem semana preferencial correspondente;
    # RESULTADO:
    # usa PRIORIDADE NA ALOCACAO.
    colab_a = _regra("ColabA", prioridade=1, semana_preferencial=0)
    colab_b = _regra("ColabB", prioridade=2, semana_preferencial=0)
    colab_c = _regra("ColabC", prioridade=3, semana_preferencial=2)  # pref semana 2, mas slot e semana 3
    slots = [_slot(1, date(2026, 1, 18))]  # 3o domingo (semana_do_mes == 3)
    estado = EstadoExecucaoGrupo()
    limites = {"ColabA": 10, "ColabB": 10, "ColabC": 10}

    decisoes = alocar_grupo([colab_a, colab_b, colab_c], slots, estado, limites)

    assert decisoes[0].vencedor == "ColabA"


def test_cenario_6_garantir_que_alteracao_nao_muda_logica_de_quarta_feira():
    # CENARIO 6:
    # - garantir que a alteracao nao muda a logica de quarta-feira.
    # Quarta-feira nao tem CEIA mesmo na 1a semana do mes.
    colab_a = _regra(
        "ColabA",
        prioridade=1,
        dia_da_semana="QUARTA-FEIRA",
        ceia_alternada=True,
        temas=["P1"],
    )
    colab_b = _regra(
        "ColabB",
        prioridade=2,
        dia_da_semana="QUARTA-FEIRA",
        ceia_alternada=False,
        temas=["P1"],
    )
    slot_quarta = SlotAgenda(
        row_index=1,
        data=date(2026, 1, 7),  # 1a quarta-feira do mes
        dia_da_semana="QUARTA-FEIRA",
        tema="Tema Teste",
        mes_key="2026-01",
        semana_do_mes=1,
        is_ultima_ocorrencia_do_mes=False,
    )
    estado = EstadoExecucaoGrupo()
    limites = {"ColabA": 10, "ColabB": 10}
    requisitos = {1: "SENIOR"}

    decisoes = alocar_grupo(
        [colab_a, colab_b],
        [slot_quarta],
        estado,
        limites,
        requisitos_tema_por_slot=requisitos,
    )

    assert decisoes[0].vencedor == "ColabA"
    assert decisoes[0].motivo == "ALOCAÇÃO NORMAL"  # Nao e "CEIA ALTERNADA"
    # Historico de CEIA nao pode ter sido preenchido por quarta-feira
    assert len(estado.historico_vencedores_ceia) == 0


def test_primeiro_domingo_ceia_nao_descarta_candidato_com_semana_preferencial_diferente():
    # Colaborador com CEIA_ALTERNADA=True e SEMANA_PREFERENCIAL=2 (ou outra != 1)
    # NAO e descartado no 1o domingo, pois a CEIA sobrepoe a semana preferencial.
    colab_a = _regra("ColabA", prioridade=1, ceia_alternada=True, semana_preferencial=2)
    colab_b = _regra("ColabB", prioridade=2, ceia_alternada=True, semana_preferencial=0)
    slots = [_slot(1, date(2026, 1, 4))]  # 1o domingo de janeiro (semana_do_mes == 1)
    estado = EstadoExecucaoGrupo()
    limites = {"ColabA": 10, "ColabB": 10}

    decisoes = alocar_grupo([colab_a, colab_b], slots, estado, limites)

    assert decisoes[0].vencedor == "ColabA"
    assert decisoes[0].motivo == "CEIA ALTERNADA"


def test_primeiro_domingo_ceia_descarta_candidato_sem_ceia_alternada_mesmo_com_pref_1():
    # Colaborador com CEIA_ALTERNADA=False e SEMANA_PREFERENCIAL=1 NAO pode vencer
    # a CEIA no 1o domingo quando ha candidatos com CEIA_ALTERNADA=True no grupo.
    colab_a = _regra("ColabA", prioridade=1, ceia_alternada=False, semana_preferencial=1)
    colab_b = _regra("ColabB", prioridade=2, ceia_alternada=True, semana_preferencial=0)
    slots = [_slot(1, date(2026, 1, 4))]  # 1o domingo de janeiro (semana_do_mes == 1)
    estado = EstadoExecucaoGrupo()
    limites = {"ColabA": 10, "ColabB": 10}

    decisoes = alocar_grupo([colab_a, colab_b], slots, estado, limites)

    assert decisoes[0].vencedor == "ColabB"
    assert decisoes[0].motivo == "CEIA ALTERNADA"
