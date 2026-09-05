from pastoreio_orquestrador.models import RegraColaborador
from pastoreio_orquestrador.sanity_regras import diagnosticar_regras


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


def test_regras_validas_nao_geram_avisos():
    regras = [_regra("Ana"), _regra("Caio")]
    relatorio = diagnosticar_regras(regras)
    assert relatorio.ok


def test_sinc_apontando_para_colaborador_inexistente_no_grupo():
    regras = [_regra("Ana", sinc_colaborador="Fantasma")]
    relatorio = diagnosticar_regras(regras)

    assert not relatorio.ok
    assert len(relatorio.avisos_sinc) == 1
    assert "Fantasma" in relatorio.avisos_sinc[0]


def test_sinc_cruzando_departamento_e_funcao_no_mesmo_dia_e_valido():
    """SINC_COLABORADOR sincroniza por linha/data (mesmo dia da semana),
    podendo cruzar departamentos e funcoes livremente (confirmado com dados
    reais: ver nota no topo de sanity_regras.py)."""
    regras = [
        _regra("Ana", funcao="SONORIZAÇÃO 1", dia_da_semana="DOMINGO", sinc_colaborador="Caio"),
        _regra("Caio", funcao="STORYS 1", dia_da_semana="DOMINGO"),
    ]
    relatorio = diagnosticar_regras(regras)
    assert relatorio.ok


def test_sinc_apontando_para_colaborador_ativo_em_outro_dia_e_invalido():
    regras = [
        _regra("Ana", dia_da_semana="DOMINGO", sinc_colaborador="Caio"),
        _regra("Caio", dia_da_semana="QUARTA-FEIRA"),
    ]
    relatorio = diagnosticar_regras(regras)
    assert not relatorio.ok
    assert len(relatorio.avisos_sinc) == 1


def test_sinc_valido_nao_gera_aviso():
    regras = [
        _regra("Ana", sinc_colaborador="Caio"),
        _regra("Caio"),
    ]
    relatorio = diagnosticar_regras(regras)
    assert relatorio.ok


def test_repeticao_mensal_invalida():
    relatorio = diagnosticar_regras([_regra("Ana", repeticao_mensal=0)])
    assert not relatorio.ok
    assert any("REPETIÇÃO MENSAL" in a for a in relatorio.avisos_quota)


def test_alocacao_extra_negativa():
    relatorio = diagnosticar_regras([_regra("Ana", alocacao_extra=-1)])
    assert not relatorio.ok
    assert any("ALOCAÇÃO EXTRA" in a for a in relatorio.avisos_quota)


def test_semana_preferencial_fora_do_intervalo():
    relatorio = diagnosticar_regras([_regra("Ana", semana_preferencial=6)])
    assert not relatorio.ok
    assert any("SEMANA PREFERENCIAL" in a for a in relatorio.avisos_quota)
