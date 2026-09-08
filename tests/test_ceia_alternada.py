from datetime import date

from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import EstadoExecucaoGrupo, alocar_grupo
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


def test_preenchimento_de_lacuna_nao_repete_o_mesmo_extra_quando_ha_outro_disponivel():
    # X (prioridade 1) e Y (prioridade 2) sao os unicos dois candidatos,
    # ambos com ALOCACAO_EXTRA=True. Com so 4 domingos de novembro/2026 e
    # cota de 1/mes cada, a Fase 3 fecha o CEIA (slot 1) com X e o slot 2
    # com Y, esgotando o pool normal -- slots 3 e 4 caem para a Fase 4
    # (PREENCHIMENTO DE LACUNA). Antes da correcao (2026-09-07, pedido do
    # Clayton), a Fase 4 sempre escolhia X (maior prioridade) para as duas
    # lacunas, repetindo-o dentro do mesmo ciclo mesmo com Y disponivel e
    # respeitando o descanso minimo. A regra correta e: dentro do mesmo
    # ciclo, se ha outro colaborador da hierarquia ALOCACAO_EXTRA ainda nao
    # usado no preenchimento de lacuna, usa o diferente; so repete se nao
    # sobrar ninguem mais.
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
    assert decisoes[2].vencedor == "X"
    assert decisoes[2].motivo == "PREENCHIMENTO DE LACUNA"
    assert decisoes[3].vencedor == "Y"
    assert decisoes[3].motivo == "PREENCHIMENTO DE LACUNA"


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


def test_preenchimento_de_lacuna_repete_quando_nao_ha_outro_extra_disponivel():
    # So um candidato com ALOCACAO_EXTRA=True.
    #
    # CORRECAO 2026-09-07 (mesmo dia, pedido do Clayton -- "a regra da
    # vizinhanca... esse doi e sobre a datas", "SEM ALOCACAO e quando e
    # impossivel alguma alocacao"): antes, a Fase 4 repetia o unico
    # candidato mesmo em datas consecutivas por falta de alternativa. Agora
    # a "vizinhanca de datas" (nao repetir em datas CONSECUTIVAS da propria
    # sequencia do grupo) e um filtro obrigatorio, aplicado mesmo no ultimo
    # nivel de reorganizacao (grupo inteiro) -- com um UNICO candidato no
    # grupo inteiro, nao ha ninguem para reorganizar, entao a data
    # imediatamente seguinte a CEIA (que ele venceu) fica corretamente SEM
    # ALOCACAO: e genuinamente impossivel alocar ali sem violar a
    # vizinhanca. A data seguinte (nao mais adjacente a CEIA, ja que a do
    # meio ficou sem vencedor) volta a aceita-lo normalmente.
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
    assert decisoes[2].vencedor == "X"
    assert decisoes[2].motivo == "PREENCHIMENTO DE LACUNA"


def test_lacuna_reorganiza_a_ordem_dos_mesmos_colaboradores_quando_hierarquia_restrita_permite():
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
    # REORGANIZA as duas decisoes ja tomadas pela Fase 4: Y passa a cobrir a
    # 1a lacuna e X a 2a -- os MESMOS dois colaboradores da hierarquia, so
    # trocando qual data cada um cobre.
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
    # Escolha gulosa inicial da Fase 4 seria X nas duas lacunas (maior
    # prioridade; nenhuma delas e vizinha do proprio uso anterior de Y ou
    # W), o que violaria a vizinhanca na 2a. A reorganizacao troca: Y cobre
    # a 1a lacuna (livre ali -- seu vizinho anterior e W, nao ele mesmo) e X
    # a 2a -- os mesmos dois colaboradores da hierarquia, so em datas
    # diferentes.
    assert decisoes[3].vencedor == "Y" and decisoes[3].motivo == "REORGANIZAÇÃO"
    assert decisoes[4].vencedor == "X" and decisoes[4].motivo == "REORGANIZAÇÃO"


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
