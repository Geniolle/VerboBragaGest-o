from datetime import date

import pytest

from pastoreio_orquestrador.auditoria import (
    AuditoriaAgendaInconsistenteError,
    CABECALHO_AUDITORIA,
    resolver_ultimo_cursor_hierarquia,
)
from pastoreio_orquestrador.columns import ColAppAnualGlobal
from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import EstadoExecucaoGrupo, alocar_grupo


DEP, FUNCAO, DIA, COLUNA = "D. MINISTROS", "MINISTRO", "DOMINGO", "MINISTRO"


def _regra(nome: str, prioridade: int, *, ceia: bool = False, semana: int = 0) -> RegraColaborador:
    return RegraColaborador(
        id_table=nome,
        nome=nome,
        departamento=DEP,
        funcao=FUNCAO,
        dia_da_semana=DIA,
        prioridade=prioridade,
        repeticao_mensal=1,
        alocar_todos_os_meses=False,
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
    for data_slot, vencedor, consome, motivo in pares:
        rows.append([
            "run",
            "2026-12-31T10:00:00",
            f"{DEP}/{FUNCAO}/{DIA}",
            DEP,
            FUNCAO,
            DIA,
            data_slot.isoformat(),
            DIA,
            "",
            "",
            vencedor,
            "",
            motivo,
            "NORMAL" if consome else motivo,
            "TRUE" if consome else "FALSE",
            "",
            vencedor,
        ])
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
