from datetime import date

from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    calcular_demanda_onda_expansiva,
)
from pastoreio_orquestrador.parsing_utils import week_of_month


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
        # True por padrao: a maioria dos testes deste arquivo nao testa a
        # regra de CEIA ALTERNADA (1o domingo do mes), entao o fixture
        # precisa deixar todo mundo elegivel para nao ser bloqueado por ela.
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


def _slot(row_index: int, d: date, tema: str = "") -> SlotAgenda:
    return SlotAgenda(
        row_index=row_index,
        data=d,
        dia_da_semana="QUARTA-FEIRA",
        tema=tema,
        mes_key=f"{d.year:04d}-{d.month:02d}",
        semana_do_mes=week_of_month(d),
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


def test_alocar_grupo_resgata_com_quota_esgotada_quando_tem_alocacao_extra():
    # Cota mensal esgotada nao gera SEM ALOCACAO se o resgate consegue
    # reaproveitar o mesmo (unico) candidato -- mas o resgate (corrigido
    # 2026-09-07, pedido do Clayton) so aceita quem tem ALOCAR TODOS OS
    # MESES=false E ALOCAÇÃO EXTRA=true; dentro desse pool restrito, os
    # unicos filtros sao Excluse e conflito de vizinhanca (cota mensal,
    # descanso minimo e tema nao bloqueiam).
    #
    # CORRECAO 2026-09-07 (mesmo dia, pedido do Clayton -- "a regra da
    # vizinhanca... esse doi e sobre a datas"): resgatar o UNICO candidato
    # para a data seguinte da mesma sequencia semanal do grupo violaria a
    # "vizinhanca de datas" (repeticao em datas consecutivas), que agora e
    # um filtro obrigatorio mesmo dentro do resgate. Com um unico candidato
    # no grupo inteiro nao ha ninguem para reorganizar -- SEM ALOCACAO passa
    # a ser o resultado correto (era impossivel alocar sem repetir em
    # sequencia).
    regras = [_regra("Ana", repeticao_mensal=1, alocacao_extra=1)]
    slots = [_slot(1, date(2026, 1, 7)), _slot(2, date(2026, 1, 14))]
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 1}  # so uma vaga liberada para Ana neste periodo

    decisoes = alocar_grupo(regras, slots, estado, limites)

    assert decisoes[0].vencedor == "Ana"
    assert decisoes[0].motivo == "ALOCAÇÃO NORMAL"
    assert decisoes[1].vencedor is None
    assert decisoes[1].sem_alocacao is True


def test_alocar_grupo_nao_resgata_sem_alocacao_extra_mesmo_sendo_unico_candidato():
    # Mesmo cenario acima, mas sem ALOCAÇÃO EXTRA=true: o resgate nao pode
    # reaproveitar Ana (ela nao esta explicitamente marcada como disponivel
    # para cota extra), entao a vaga fica SEM ALOCAÇÃO.
    regras = [_regra("Ana", repeticao_mensal=1, alocacao_extra=0)]
    slots = [_slot(1, date(2026, 1, 7)), _slot(2, date(2026, 1, 14))]
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 1}

    decisoes = alocar_grupo(regras, slots, estado, limites)

    assert decisoes[0].vencedor == "Ana"
    assert decisoes[1].vencedor is None
    assert decisoes[1].sem_alocacao is True


def test_vizinhanca_de_datas_impede_repeticao_em_datas_consecutivas():
    # "Vizinhanca de DATAS" (2026-09-07, correcao do Clayton: "esse doi e
    # sobre a datas e nao sobre as funcoes") -- ninguem pode vencer duas
    # datas cronologicamente CONSECUTIVAS da propria sequencia do grupo. Ana
    # (prioridade 1) venceria as 3 datas seguidas por desempate de
    # prioridade se essa regra nao existisse; com ela, Bia entra na 2a data
    # e Ana volta na 3a (nao e mais vizinha da 1a, ja que a 2a ficou entre
    # elas).
    regras = [_regra("Ana", prioridade=1), _regra("Bia", prioridade=2)]
    slots = [
        _slot(1, date(2026, 1, 7)),
        _slot(2, date(2026, 1, 14)),
        _slot(3, date(2026, 1, 21)),
    ]
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 100, "Bia": 100}

    decisoes = alocar_grupo(regras, slots, estado, limites)

    assert [d.vencedor for d in decisoes] == ["Ana", "Bia", "Ana"]


def test_alocar_grupo_marca_sem_alocacao_quando_nao_ha_nenhum_candidato():
    slots = [_slot(1, date(2026, 1, 7))]
    estado = EstadoExecucaoGrupo()

    decisoes = alocar_grupo([], slots, estado, {})

    assert decisoes[0].sem_alocacao is True
    assert decisoes[0].vencedor is None


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


def test_delimitar_uma_ronda_estende_ate_fechar_o_mes():
    from pastoreio_orquestrador.motor import delimitar_uma_ronda

    datas = [
        date(2026, 10, 4), date(2026, 10, 11), date(2026, 10, 18), date(2026, 10, 25),
        date(2026, 11, 1), date(2026, 11, 8), date(2026, 11, 15), date(2026, 11, 22),
        date(2026, 11, 29), date(2026, 12, 6), date(2026, 12, 13),
    ]
    ronda = delimitar_uma_ronda(datas, n_colaboradores_ativos=7)
    assert ronda == datas[:9]


def test_delimitar_uma_ronda_sem_extensao_quando_mes_ja_fecha_exato():
    from pastoreio_orquestrador.motor import delimitar_uma_ronda

    datas = [date(2026, 10, 4), date(2026, 10, 11), date(2026, 11, 1)]
    ronda = delimitar_uma_ronda(datas, n_colaboradores_ativos=2)
    assert ronda == [date(2026, 10, 4), date(2026, 10, 11)]


def test_filtrar_slots_ja_preenchidos_remove_so_as_datas_com_valor():
    from pastoreio_orquestrador.motor import filtrar_slots_ja_preenchidos

    slots = [_slot(1, date(2026, 10, 4)), _slot(2, date(2026, 10, 11)), _slot(3, date(2026, 10, 18))]
    valor_por_data = {
        date(2026, 10, 4): "",
        date(2026, 10, 11): "Fulano",  # ex.: feriado marcado a mao
        date(2026, 10, 18): "",
    }
    restantes = filtrar_slots_ja_preenchidos(slots, valor_por_data)
    assert [s.data for s in restantes] == [date(2026, 10, 4), date(2026, 10, 18)]


def test_filtrar_slots_ja_preenchidos_nao_remove_nada_quando_tudo_vazio():
    from pastoreio_orquestrador.motor import filtrar_slots_ja_preenchidos

    slots = [_slot(1, date(2026, 10, 4)), _slot(2, date(2026, 10, 11))]
    valor_por_data = {date(2026, 10, 4): "", date(2026, 10, 11): ""}
    assert filtrar_slots_ja_preenchidos(slots, valor_por_data) == slots


def test_data_ja_preenchida_na_ronda_aberta_nao_consome_cota_de_ninguem():
    # Regra global pedida pelo Clayton (2026-09-11): mes com 5 datas mas 1 ja
    # preenchida (ex.: feriado) deve usar so 4 colaboradores -- a data
    # preenchida nao pode "gastar" o rodizio/cota de ninguem, mesmo nao
    # sendo escrita de volta.
    from pastoreio_orquestrador.motor import filtrar_slots_ja_preenchidos

    # 5 candidatos (N=5), 5 datas no MESMO mes (1 vaga por pessoa por mes),
    # prioridades distintas para o rodizio ser deterministico.
    candidatos = [
        _regra(f"Pessoa{i}", repeticao_mensal=1, prioridade=i * 10) for i in range(1, 6)
    ]
    todas_as_datas = [date(2026, 10, d) for d in (1, 8, 15, 22, 29)]
    valor_por_data = {d: "" for d in todas_as_datas}
    valor_por_data[date(2026, 10, 15)] = "FERIADO"  # pre-preenchida, fora do algoritmo

    todos_os_slots = [_slot(i, d) for i, d in enumerate(todas_as_datas, start=1)]
    slots_pendentes = filtrar_slots_ja_preenchidos(todos_os_slots, valor_por_data)
    assert len(slots_pendentes) == 4  # so 4 vagas reais, nao 5

    meses_tocados = len({s.mes_key for s in slots_pendentes})
    demanda = calcular_demanda_onda_expansiva(
        candidatos, vagas_reais_no_periodo=len(slots_pendentes), meses_tocados=meses_tocados
    )
    estado = EstadoExecucaoGrupo(historico_total={})
    decisoes = alocar_grupo(candidatos, slots_pendentes, estado, demanda.mapa_limites_locais)

    vencedores = {d.vencedor for d in decisoes}
    assert None not in vencedores
    assert len(vencedores) == 4  # so 4 dos 5 colaboradores tiveram o rodizio "gasto"
    for c in candidatos:
        assert estado.uso_no_mes.get(c.nome, 0) <= 1


def test_descanso_cruzado_bloqueia_mesma_pessoa_em_outro_dia_da_semana_muito_perto():
    # "Descanso minimo cruzado" (2026-09-08, pedido do Clayton apos achar
    # casos reais de MINISTRO alocado num domingo e de novo poucos dias
    # depois na quarta-feira seguinte, ex.: Ana Lima em 11/10/2026 (domingo)
    # e 14/10/2026 (quarta) -- so 3 dias, bem menos que os 7 exigidos).
    # Ana venceria por prioridade se o compromisso externo nao bloqueasse.
    regras = [_regra("Ana", prioridade=1), _regra("Bia", prioridade=2)]
    slots = [_slot(1, date(2026, 1, 14))]  # quarta-feira
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 100, "Bia": 100}
    # Compromisso ja confirmado de Ana no domingo anterior, 3 dias antes.
    compromissos_cruzados = {"ANA": [date(2026, 1, 11)]}

    decisoes = alocar_grupo(
        regras, slots, estado, limites, compromissos_cruzados=compromissos_cruzados
    )

    assert decisoes[0].vencedor == "Bia"


def test_descanso_cruzado_tambem_bloqueia_quando_o_compromisso_externo_e_no_futuro():
    # O compromisso "externo" pode ser cronologicamente DEPOIS do slot sendo
    # decidido agora (ex.: a Ronda do outro dia da semana ja foi escrita
    # antes) -- ao contrario de `respeita_descanso_minimo` (que so enxerga
    # o que ja foi decidido antes, dentro do proprio grupo), aqui o
    # compromisso futuro ja e um fato fixo e tambem deve bloquear.
    regras = [_regra("Ana", prioridade=1), _regra("Bia", prioridade=2)]
    slots = [_slot(1, date(2026, 1, 14))]  # quarta-feira
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 100, "Bia": 100}
    # Compromisso ja confirmado de Ana no domingo SEGUINTE, so 4 dias depois.
    compromissos_cruzados = {"ANA": [date(2026, 1, 18)]}

    decisoes = alocar_grupo(
        regras, slots, estado, limites, compromissos_cruzados=compromissos_cruzados
    )

    assert decisoes[0].vencedor == "Bia"


def test_resgate_tambem_respeita_descanso_cruzado():
    # Caso real (2026-09-10, achado pelo Clayton): Andre Luiz foi RESGATE no
    # domingo 23/05/2027, so 4 dias depois de ja ter sido MINISTRO na
    # quarta-feira 19/05/2027 -- o descanso minimo cruzado (criado em
    # 2026-09-08) nunca tinha sido incluido no RESGATE (que e mais antigo,
    # de 2026-09-07), entao o "ultimo recurso" furava justamente a regra
    # feita para evitar essa repeticao entre domingo e quarta.
    #
    # Aqui: Ana (unica com ALOCAR TODOS OS MESES=false + ALOCAÇÃO EXTRA=true,
    # ou seja, elegivel para RESGATE) ja tem um compromisso confirmado 4 dias
    # antes do slot -- mesmo com a cota esgotada forçando o RESGATE, ela deve
    # continuar bloqueada e a vaga deve ficar SEM ALOCAÇÃO (nao ha mais
    # ninguem elegivel para o resgate neste cenario).
    regras = [_regra("Ana", repeticao_mensal=1, alocacao_extra=1)]
    slots = [_slot(1, date(2026, 1, 14))]  # quarta-feira
    estado = EstadoExecucaoGrupo()
    limites = {"Ana": 0}  # cota ja esgotada, forca a cascata a cair no RESGATE
    compromissos_cruzados = {"ANA": [date(2026, 1, 10)]}  # domingo, 4 dias antes

    decisoes = alocar_grupo(
        regras, slots, estado, limites, compromissos_cruzados=compromissos_cruzados
    )

    assert decisoes[0].vencedor is None
    assert decisoes[0].sem_alocacao is True


def test_sub_rodizio_alterna_entre_membros_da_mesma_semana_preferencial():
    # Pedido do Clayton (2026-09-10, apos ver Fernando Mauricio vencer sempre
    # sobre Gislane Ferreira na unica vaga PLENO+"ultima semana" observada):
    # "Temos de fazer um sub-rodizio para quem tem o SEMANA PREFERENCIAL,
    # agrupamos quem tem igual, e uma vez de cada um." Isso ja esta
    # implementado (`chave_rodizio_nivel`, 2a correcao de 2026-09-10) -- este
    # teste prova que, havendo DUAS ocorrencias da mesma vaga (nivel PLENO +
    # semana 5) na mesma janela, o rodizio de fato alterna: Fernando vence a
    # 1a (prioridade melhor), fica bloqueado, Gislane vence a 2a.
    fernando = _regra("Fernando", prioridade=8, semana_preferencial=5, temas=["P2"])
    gislane = _regra("Gislane", prioridade=9, semana_preferencial=5, temas=["P2"])
    regras = [fernando, gislane]
    slots = [
        _slot(1, date(2026, 8, 26)),  # ultima quarta de agosto/2026 (5a semana)
        _slot(2, date(2026, 10, 28)),  # ultima quarta de outubro/2026 (5a semana)
    ]
    estado = EstadoExecucaoGrupo()
    limites = {"Fernando": 100, "Gislane": 100}
    requisitos = {1: "PLENO", 2: "PLENO"}

    decisoes = alocar_grupo(regras, slots, estado, limites, requisitos_tema_por_slot=requisitos)

    assert [d.vencedor for d in decisoes] == ["Fernando", "Gislane"]


def test_rodizio_por_tema_favorece_quem_ainda_nao_fez_o_tema_mesmo_com_prioridade_pior():
    # Pedido do Clayton (2026-09-10): "criar ronda por tema, e fazendo o
    # rodizio, assim contemplamos todos" -- um bloco de tema com varias
    # semanas seguidas do MESMO nivel (ex.: PLENO) nao garantia por si so
    # que pessoas diferentes circulassem POR TEMA; so evitava repetir
    # IMEDIATAMENTE (via rodizio geral do nivel). Aqui Ana (prioridade 1)
    # ja venceu esse MESMO tema antes; Bia (prioridade 2) nunca fez. Mesmo
    # sem nenhum bloqueio duro (janela de nivel nao entra em jogo pois nao
    # ha requisito_tema aqui), o desempate deve favorecer Bia.
    ana = _regra("Ana", prioridade=1)
    bia = _regra("Bia", prioridade=2)
    estado = EstadoExecucaoGrupo()
    estado.historico_vencedores_por_tema["TEMA X"] = {"Ana": 2}
    slot = _slot(1, date(2026, 1, 7), tema="Tema X")

    decisoes = alocar_grupo([ana, bia], [slot], estado, {"Ana": 100, "Bia": 100})

    assert decisoes[0].vencedor == "Bia"


def test_rodizio_por_tema_nao_afeta_desempate_quando_ninguem_fez_o_tema_ainda():
    # Contagem igual (0 para todos) -- desempate cai para o proximo
    # criterio (prioridade), como antes desta mudanca.
    ana = _regra("Ana", prioridade=1)
    bia = _regra("Bia", prioridade=2)
    estado = EstadoExecucaoGrupo()
    slot = _slot(1, date(2026, 1, 7), tema="Tema X")

    decisoes = alocar_grupo([ana, bia], [slot], estado, {"Ana": 100, "Bia": 100})

    assert decisoes[0].vencedor == "Ana"


def test_quebra_de_rodizio_fecha_gap_quando_unico_livre_do_rodizio_tem_outro_bloqueio():
    # Pedido do Clayton (2026-09-10, motivado por um SEM ALOCAÇÃO real em
    # FUNDAMENTOS DA FÉ): o rodizio de nivel bloqueou Ana (ultima vencedora
    # PLENO), sobrando so Bia como "da vez" -- mas Bia esta de aniversario
    # nesse dia. Sem a quebra de rodizio, ninguem sobra (SEM ALOCAÇÃO). Com
    # a quebra (fallback so quando a passada normal falha), o rodizio e
    # desligado, Ana volta a ficar elegivel e fecha a vaga; Bia continua de
    # fora -- o bloqueio de aniversario dela NAO e quebrado, so o rodizio.
    ana = _regra("Ana", prioridade=1, temas=["P2"])
    bia = _regra("Bia", prioridade=2, temas=["P2"])
    estado = EstadoExecucaoGrupo()
    estado.historico_vencedores_por_nivel["PLENO"] = ["Ana"]
    slot = _slot(1, date(2026, 1, 14))
    aniversarios = {"BIA": date(2020, 1, 14)}

    decisoes = alocar_grupo(
        [ana, bia], [slot], estado, {"Ana": 100, "Bia": 100},
        requisitos_tema_por_slot={1: "PLENO"},
        aniversarios=aniversarios,
    )

    assert decisoes[0].vencedor == "Ana"
    assert "RODÍZIO QUEBRADO" in decisoes[0].motivo


def test_descanso_cruzado_fica_sem_alocacao_quando_e_o_unico_candidato():
    regras = [_regra("Ana", prioridade=1)]
    slots = [_slot(1, date(2026, 1, 14))]
    estado = EstadoExecucaoGrupo()
    compromissos_cruzados = {"ANA": [date(2026, 1, 11)]}

    decisoes = alocar_grupo(
        regras, slots, estado, {}, compromissos_cruzados=compromissos_cruzados
    )

    assert decisoes[0].vencedor is None
    assert decisoes[0].motivo == "SEM ALOCAÇÃO"
