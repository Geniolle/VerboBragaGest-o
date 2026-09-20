from datetime import date

import pytest

from pastoreio_orquestrador.auditoria import (
    AuditoriaAgendaInconsistenteError,
    CABECALHO_AUDITORIA,
    resolver_ultimo_cursor_hierarquia,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import EstadoExecucaoGrupo, alocar_grupo, diagnosticar_escolha_slot


DEP, FUNCAO, DIA, COLUNA = "D. MINISTROS", "MINISTRO", "DOMINGO", "MINISTRO"


def _regra(
    nome: str,
    prioridade: int,
    *,
    ceia: bool = False,
    semana: int = 0,
    repeticao_mensal: int = 1,
    alocar_todos_os_meses: bool = False,
) -> RegraColaborador:
    return RegraColaborador(
        id_table=nome,
        nome=nome,
        departamento=DEP,
        funcao=FUNCAO,
        dia_da_semana=DIA,
        prioridade=prioridade,
        repeticao_mensal=repeticao_mensal,
        alocar_todos_os_meses=alocar_todos_os_meses,
        semana_preferencial=semana,
        ceia_alternada=ceia,
        semana_alternada=False,
        alocacao_extra=0,
        atribuir_aos_recados=False,
        perfil_autorizacao=False,
        sinc_colaborador=None,
        sinc_sem_alocacao=False,
        temas=[],
        ativo=True,
        row_index_bp=prioridade,
    )


def _slot(row: int, data: date) -> SlotAgenda:
    return SlotAgenda(
        row_index=row,
        data=data,
        dia_da_semana=DIA,
        tema="",
        mes_key=f"{data.year:04d}-{data.month:02d}",
        semana_do_mes=((data.day - 1) // 7) + 1,
        is_ultima_ocorrencia_do_mes=False,
    )


def _agenda(*pares: tuple[date, str]) -> list[list[str]]:
    rows = [[ColAppAnualGlobal.DATA, ColAppAnualGlobal.DIA_DA_SEMANA, COLUNA]]
    for data_slot, vencedor in pares:
        rows.append([data_slot.strftime("%d/%m/%Y"), DIA, vencedor])
    return rows


def _audit(*pares: tuple[date, str, bool, str]) -> list[list[str]]:
    rows = [CABECALHO_AUDITORIA]
    idx = {nome: i for i, nome in enumerate(CABECALHO_AUDITORIA)}
    for data_slot, vencedor, consome, motivo in pares:
        row = [""] * len(CABECALHO_AUDITORIA)
        row[idx["RUN_ID"]] = "run"
        row[idx["TIMESTAMP_EXECUCAO"]] = "2026-12-31T10:00:00"
        row[idx["GRUPO"]] = f"{DEP}/{FUNCAO}/{DIA}"
        row[idx["DEPARTAMENTO"]] = DEP
        row[idx["FUNCAO"]] = FUNCAO
        row[idx["DIA_DA_SEMANA_GRUPO"]] = DIA
        row[idx["DATA_SLOT"]] = data_slot.isoformat()
        row[idx["DIA_DA_SEMANA"]] = DIA
        row[idx["TIPO_DIA"]] = "DOMINGO_NORMAL"
        row[idx["VENCEDOR"]] = vencedor
        row[idx["MOTIVO"]] = motivo
        row[idx["INTENCAO_ALOCACAO"]] = "NORMAL_ROTATION" if consome else ""
        row[idx["POLITICA_SELECAO"]] = "SUNDAY_HIERARCHY" if consome else ""
        row[idx["TIPO_ALOCACAO"]] = "NORMAL" if consome else motivo
        row[idx["OBRIGACAO_SATISFEITA"]] = "PARTICIPACAO_BASE" if consome else ""
        row[idx["CONSOME_HIERARQUIA"]] = "TRUE" if consome else "FALSE"
        row[idx["CANDIDATOS_AVALIADOS"]] = vencedor
        rows.append(row)
    return rows


def _resolver(agenda, audit, regras):
    return resolver_ultimo_cursor_hierarquia(agenda, audit, regras, DEP, FUNCAO, DIA, COLUNA)


def _alocar_um(regras, cursor_nome, data_slot=date(2027, 1, 10)):
    estado = EstadoExecucaoGrupo(cursor_hierarquia=cursor_nome)
    decisoes = alocar_grupo(regras, [_slot(10, data_slot)], estado, {r.nome: 10 for r in regras})
    return decisoes[0], estado


def test_nova_execucao_comeca_depois_da_ultima_prioridade_consumida():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3), _regra("P4", 4)]
    historico = _agenda((date(2026, 12, 20), "P2"))
    audit = _audit((date(2026, 12, 20), "P2", True, "ALOCAÇÃO NORMAL"))

    cursor = _resolver(historico, audit, regras)
    decisao, _estado = _alocar_um(regras, cursor.ancora)

    assert cursor.ancora == "P2"
    assert decisao.vencedor == "P3"


def test_repeticao_mensal_posterior_nao_move_cursor():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3)]
    agenda = _agenda((date(2026, 12, 20), "P2"), (date(2026, 12, 27), "P1"))
    audit = _audit(
        (date(2026, 12, 20), "P2", True, "ALOCAÇÃO NORMAL"),
        (date(2026, 12, 27), "P1", False, "REPETIÇÃO MENSAL"),
    )

    cursor = _resolver(agenda, audit, regras)

    assert cursor.ancora == "P2"
    assert cursor.proximo_candidato.nome == "P3"


def test_ceia_posterior_nao_move_cursor():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3)]
    agenda = _agenda((date(2026, 12, 20), "P2"), (date(2027, 1, 3), "P1"))
    audit = _audit(
        (date(2026, 12, 20), "P2", True, "ALOCAÇÃO NORMAL"),
        (date(2027, 1, 3), "P1", False, "CEIA ALTERNADA"),
    )

    cursor = _resolver(agenda, audit, regras)

    assert cursor.ancora == "P2"
    assert cursor.proximo_candidato.nome == "P3"


def test_candidato_analisado_inelegivel_nao_consumido_proximo_elegivel_consumido():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3, semana=5), _regra("P4", 4)]
    decisao, estado = _alocar_um(regras, "P2", date(2027, 1, 10))

    assert decisao.vencedor == "P4"
    assert decisao.consome_hierarquia is True
    assert estado.cursor_hierarquia == "P4"


def test_diagnostico_domingo_nao_altera_estado_e_explica_rejeicoes():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3, semana=5), _regra("P4", 4)]
    estado = EstadoExecucaoGrupo(cursor_hierarquia="P2")
    slot = _slot(10, date(2027, 1, 10))

    trace = diagnosticar_escolha_slot(
        regras,
        slot,
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={r.nome: 1 for r in regras},
    )

    assert trace.selecionado == "P4"
    assert trace.cursor_antes == "P2"
    assert trace.cursor_depois == "P4"
    assert estado.cursor_hierarquia == "P2"
    assert estado.uso_por_mes == {}
    assert [a.candidato for a in trace.avaliacoes if a.passada == "NORMAL"] == ["P3", "P4", "P1", "P2"]
    rejeitado = [a for a in trace.avaliacoes if a.candidato == "P3"][0]
    assert rejeitado.elegivel is False
    assert "fora da semana preferencial" in rejeitado.motivos_rejeicao

    decisao_motor, _estado_motor = _alocar_um(regras, "P2", slot.data)
    assert trace.selecionado == decisao_motor.vencedor
    assert str(trace.intent) == decisao_motor.intent


def test_wraparound_depois_do_ultimo_elemento():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3)]
    cursor = _resolver(
        _agenda((date(2026, 12, 27), "P3")),
        _audit((date(2026, 12, 27), "P3", True, "ALOCAÇÃO NORMAL")),
        regras,
    )

    assert cursor.proximo_candidato.nome == "P1"


def test_prioridades_nao_sequenciais_usam_ordem_atual():
    regras = [_regra("P1", 1), _regra("P3", 3), _regra("P7", 7), _regra("P10", 10)]
    cursor = _resolver(
        _agenda((date(2026, 12, 13), "P3")),
        _audit((date(2026, 12, 13), "P3", True, "ALOCAÇÃO NORMAL")),
        regras,
    )

    assert cursor.proximo_candidato.nome == "P7"


def test_mudanca_de_prioridade_usa_identidade_e_hierarquia_atual():
    regras = [_regra("A", 1), _regra("C", 2), _regra("B", 4), _regra("D", 7)]
    cursor = _resolver(
        _agenda((date(2026, 12, 20), "B")),
        _audit((date(2026, 12, 20), "B", True, "ALOCAÇÃO NORMAL")),
        regras,
    )

    assert cursor.ancora == "B"
    assert cursor.prioridade_ancora_atual == 4
    assert cursor.proximo_candidato.nome == "D"


def test_auditoria_divergente_da_agenda_gera_diagnostico_controlado():
    regras = [_regra("X", 1), _regra("Y", 2)]

    with pytest.raises(AuditoriaAgendaInconsistenteError):
        _resolver(
            _agenda((date(2026, 12, 20), "Y")),
            _audit((date(2026, 12, 20), "X", True, "ALOCAÇÃO NORMAL")),
            regras,
        )


def test_auditoria_divergente_pode_ser_ignorada_quando_produtivo_esta_em_transicao():
    regras = [_regra("X", 1), _regra("Y", 2), _regra("Z", 3)]
    cursor = resolver_ultimo_cursor_hierarquia(
        _agenda((date(2026, 12, 13), "X"), (date(2026, 12, 20), "Y")),
        _audit(
            (date(2026, 12, 13), "X", True, "ALOCAÇÃO NORMAL"),
            (date(2026, 12, 20), "Z", True, "ALOCAÇÃO NORMAL"),
        ),
        regras,
        DEP,
        FUNCAO,
        DIA,
        COLUNA,
        falhar_em_inconsistencia=False,
    )

    assert cursor.ancora == "X"
    assert cursor.proximo_candidato.nome == "Y"
    assert cursor.registros_validos[0].vencedor == "X"
    assert cursor.diagnosticos == [
        "Auditoria ignorada por nao confirmar agenda: 2026-12-20: auditoria indica Z, mas a agenda contem Y."
    ]


def test_ceia_nao_consumida_e_normal_seguinte_consumida():
    regras = [_regra("Ceia A", 1, ceia=True), _regra("Normal B", 2), _regra("Normal C", 3)]
    slots = [_slot(1, date(2026, 12, 6)), _slot(2, date(2026, 12, 13))]
    estado = EstadoExecucaoGrupo()

    decisoes = alocar_grupo(regras, slots, estado, {r.nome: 10 for r in regras})

    assert decisoes[0].motivo == "CEIA ALTERNADA"
    assert decisoes[0].consome_hierarquia is False
    assert decisoes[1].vencedor == "Normal B"
    assert decisoes[1].consome_hierarquia is True
    assert estado.cursor_hierarquia == "Normal B"


def test_cursor_nao_altera_ciclo_da_ceia():
    regras = [_regra("Ceia A", 1, ceia=True), _regra("Ceia B", 2, ceia=True)]
    estado = EstadoExecucaoGrupo(cursor_hierarquia="Ceia A")

    decisao = alocar_grupo(
        regras,
        [_slot(1, date(2026, 12, 6))],
        estado,
        {r.nome: 10 for r in regras},
    )[0]

    assert decisao.vencedor == "Ceia A"
    assert decisao.motivo == "CEIA ALTERNADA"
    assert decisao.consome_hierarquia is False


def test_fase_normal_usa_hierarquia_completa_mesmo_com_ancora_fora_do_pool():
    regras = [
        _regra("P1", 1),
        _regra("P2", 2, ceia=True),
        _regra("P3", 3),
        _regra("P4", 4),
    ]
    estado = EstadoExecucaoGrupo(cursor_hierarquia="P2")
    slots = [_slot(1, date(2026, 12, 6)), _slot(2, date(2026, 12, 13))]

    decisoes = alocar_grupo(regras, slots, estado, {r.nome: 10 for r in regras})

    assert decisoes[0].vencedor == "P2"
    assert decisoes[0].consome_hierarquia is False
    assert decisoes[1].vencedor == "P3"
    assert decisoes[1].consome_hierarquia is True


def test_novo_estado_sem_memoria_reconstroi_cursor_dos_dados_persistidos():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3)]
    agenda = _agenda((date(2026, 12, 20), "P2"))
    audit = _audit((date(2026, 12, 20), "P2", True, "ALOCAÇÃO NORMAL"))

    cursor = _resolver(agenda, audit, regras)
    novo_estado = EstadoExecucaoGrupo(cursor_hierarquia=cursor.ancora)
    decisao = alocar_grupo(regras, [_slot(30, date(2027, 1, 10))], novo_estado, {r.nome: 10 for r in regras})[0]

    assert novo_estado.hierarquia_consumida_na_ronda == {"P3"}
    assert decisao.vencedor == "P3"
    assert decisao.consome_hierarquia is True


def test_repeticao_mensal_intercalada_nao_move_cursor_outubro():
    regras = [
        _regra("Clayton", 1, repeticao_mensal=2),
        _regra("Patricia", 2),
        _regra("Caio", 3),
        _regra("Pessoa D", 4),
        _regra("Andre", 5),
    ]
    slots = [
        _slot(1, date(2026, 10, 4)),
        _slot(2, date(2026, 10, 11)),
        _slot(3, date(2026, 10, 18)),
        _slot(4, date(2026, 10, 25)),
    ]
    estado = EstadoExecucaoGrupo()

    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={"Clayton": 2, "Patricia": 1, "Caio": 1, "Pessoa D": 1, "Andre": 1},
    )

    assert [d.vencedor for d in decisoes] == ["Clayton", "Patricia", "Clayton", "Caio"]
    assert [d.motivo for d in decisoes] == [
        "ALOCAÇÃO NORMAL",
        "ALOCAÇÃO NORMAL",
        "REPETIÇÃO MENSAL",
        "ALOCAÇÃO NORMAL",
    ]
    assert [d.tipo_alocacao for d in decisoes] == ["NORMAL", "NORMAL", "REPETICAO_MENSAL", "NORMAL"]
    assert [d.consome_hierarquia for d in decisoes] == [True, True, False, True]
    assert estado.cursor_hierarquia == "Caio"


def test_ceia_futura_nao_remove_candidato_da_hierarquia_normal_do_mes_anterior():
    regras = [
        _regra("P1", 1, ceia=True, repeticao_mensal=2, alocar_todos_os_meses=True),
        _regra("P2", 2, ceia=True),
        _regra("P3", 3, ceia=True),
    ]
    slots = [
        _slot(1, date(2026, 10, 4)),
        _slot(2, date(2026, 10, 11)),
        _slot(3, date(2026, 10, 18)),
        _slot(4, date(2026, 10, 25)),
        _slot(5, date(2026, 11, 1)),
    ]
    estado = EstadoExecucaoGrupo()

    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={"P1": 2, "P2": 1, "P3": 1},
    )

    assert decisoes[0].vencedor == "P1"
    assert decisoes[0].motivo == "CEIA ALTERNADA"
    assert decisoes[1].vencedor == "P2"
    assert decisoes[1].tipo_dia == "DOMINGO_NORMAL"
    assert decisoes[1].intent == "NORMAL_ROTATION"
    assert decisoes[1].politica_selecao == "SUNDAY_HIERARCHY"
    assert decisoes[1].consome_hierarquia is True


def test_hierarquia_normal_sem_repeticao_avanca_um_a_um():
    regras = [_regra("P1", 1), _regra("P2", 2), _regra("P3", 3), _regra("P4", 4)]
    slots = [
        _slot(1, date(2026, 10, 4)),
        _slot(2, date(2026, 10, 11)),
        _slot(3, date(2026, 10, 18)),
        _slot(4, date(2026, 10, 25)),
    ]
    estado = EstadoExecucaoGrupo()

    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={r.nome: 1 for r in regras},
    )

    assert [d.vencedor for d in decisoes] == ["P1", "P2", "P3", "P4"]
    assert [d.consome_hierarquia for d in decisoes] == [True, True, True, True]
    assert estado.cursor_hierarquia == "P4"


def test_duas_repeticoes_intercaladas_nao_alteram_sequencia_normal():
    regras = [
        _regra("P1", 1, repeticao_mensal=3),
        _regra("P2", 2),
        _regra("P3", 3),
        _regra("P4", 4),
    ]
    slots = [
        _slot(1, date(2026, 3, 1)),
        _slot(2, date(2026, 3, 8)),
        _slot(3, date(2026, 3, 15)),
        _slot(4, date(2026, 3, 22)),
        _slot(5, date(2026, 3, 29)),
        _slot(6, date(2026, 4, 5)),
    ]
    estado = EstadoExecucaoGrupo()

    decisoes = alocar_grupo(
        regras,
        slots,
        estado,
        {r.nome: 10 for r in regras},
        mapa_limites_mensais={"P1": 3, "P2": 1, "P3": 1, "P4": 1},
    )

    assert [d.vencedor for d in decisoes] == ["P1", "P2", "P1", "P3", "P1", "P4"]
    assert [d.motivo for d in decisoes] == [
        "ALOCAÇÃO NORMAL",
        "ALOCAÇÃO NORMAL",
        "REPETIÇÃO MENSAL",
        "ALOCAÇÃO NORMAL",
        "REPETIÇÃO MENSAL",
        "ALOCAÇÃO NORMAL",
    ]
    assert [d.tipo_alocacao for d in decisoes] == [
        "NORMAL",
        "NORMAL",
        "REPETICAO_MENSAL",
        "NORMAL",
        "REPETICAO_MENSAL",
        "NORMAL",
    ]
    assert [d.consome_hierarquia for d in decisoes] == [True, True, False, True, False, True]
    assert estado.cursor_hierarquia == "P4"
