from datetime import date

from pastoreio_orquestrador.carregamento import build_header_index
from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    esta_bloqueado_por_excluse,
)

# Estrutura real da aba Excluse (entendimento final, confirmado por Clayton
# em 2026-09-07): a coluna "COLUNAS" da linha e so um ROTULO (o papel a que
# aquela linha se refere). O que importa e o VALOR na coluna
# "ID_<DEPARTAMENTO>" -- se o NOME LITERAL de uma coluna de AppAnualGlobal
# aparece como VALOR em QUALQUER linha dessa coluna (nao so na linha cujo
# COLUNAS==o proprio papel), entao um candidato com seu nome NAQUELA coluna
# na mesma data fica bloqueado. Ter a PROPRIA linha preenchida (com qualquer
# coisa, ex.: uma ASSIDUIDADE) NAO e o criterio -- so ser citado como valor
# em outra linha. IMPORTANTE (correcao de Clayton, mesmo dia): as colunas
# "ASSIDUIDADEXX" NAO sao genericas/ruido -- sao nomes de coluna reais
# (registram ausencia do colaborador) e sao tratadas exatamente igual a
# qualquer outra coluna citada como valor.
EXCLUSE_HEADER = build_header_index(["COLUNAS", "ID_MINISTROS", "ID_AUXILIAR"])
EXCLUSE_ROWS = [
    ["MINISTRO", "ASSIDUIDADE1", "ASSIDUIDADE1"],
    ["AUXILIAR", "ASSIDUIDADE2", "ASSIDUIDADE2"],
    # Tem linha propria preenchida, mas "PORTARIA FRENTE1" nunca aparece
    # como VALOR em nenhuma linha -- nao deve bloquear.
    ["PORTARIA FRENTE1", "ASSIDUIDADE8", ""],
    ["PROFESSOR(A) (S1)", "ASSIDUIDADE30", ""],
    # "PROFESSOR(A) (S1)" aparece aqui como VALOR -- deve bloquear.
    ["PROFESSOR(A) (S3)", "PROFESSOR(A) (S1)", ""],
    # Sem valor na coluna ID_MINISTROS -- nunca bloqueia, mesmo que o
    # candidato esteja alocado nesse papel.
    ["COPERADOR1", "", ""],
]


def _slot(papeis: dict[str, str] | None = None, assiduidade: dict[str, str] | None = None) -> SlotAgenda:
    return SlotAgenda(
        row_index=1,
        data=date(2026, 1, 7),
        dia_da_semana="QUARTA-FEIRA",
        tema="",
        mes_key="2026-01",
        semana_do_mes=1,
        is_ultima_ocorrencia_do_mes=False,
        papeis=papeis or {},
        assiduidade=assiduidade or {},
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


def test_candidato_ja_alocado_em_papel_citado_como_valor_esta_bloqueado():
    # "PROFESSOR(A) (S1)" aparece como VALOR na linha PROFESSOR(A) (S3).
    slot = _slot({"PROFESSOR(A) (S1)": "Fernando Maurício"})
    assert esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_outro_candidato_no_mesmo_papel_nao_esta_bloqueado():
    slot = _slot({"PROFESSOR(A) (S1)": "Fernando Maurício"})
    assert not esta_bloqueado_por_excluse(
        "Ana Lima", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_papel_com_linha_propria_preenchida_mas_nunca_citado_como_valor_nao_bloqueia():
    # PORTARIA FRENTE1 tem sua propria linha preenchida (ASSIDUIDADE8), mas
    # o texto "PORTARIA FRENTE1" nunca aparece como VALOR em nenhuma linha
    # da coluna ID_MINISTROS -- so como rotulo. Nao deve bloquear.
    slot = _slot({"PORTARIA FRENTE1": "Fernando Maurício"})
    assert not esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_papel_sem_valor_no_id_col_nunca_bloqueia():
    # COPERADOR1 nao tem valor na coluna ID_MINISTROS -- nenhum conflito
    # declarado, mesmo que o candidato esteja alocado la.
    slot = _slot({"COPERADOR1": "Fernando Maurício"})
    assert not esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_a_propria_funcao_sendo_avaliada_e_ignorada():
    # Mesmo que a coluna MINISTRO ja tenha um valor (ex.: sobra de execucao
    # anterior), ela nao conta como um conflito contra si mesma.
    slot = _slot({"MINISTRO": "Fernando Maurício"})
    assert not esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_sem_nenhum_papel_alocado_ninguem_bloqueado():
    slot = _slot({})
    assert not esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_candidato_marcado_ausente_via_assiduidade_esta_bloqueado():
    # "ASSIDUIDADE1" aparece como VALOR na linha MINISTRO -- ASSIDUIDADEXX
    # nao e generica/ruido, e um nome de coluna real (ausencia) e bloqueia
    # igual a qualquer outra coluna citada como valor.
    slot = _slot(assiduidade={"ASSIDUIDADE1": "Fernando Maurício"})
    assert esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_candidato_ausente_em_assiduidade_nao_citada_como_valor_nao_bloqueia():
    # "ASSIDUIDADE99" nunca aparece como VALOR em nenhuma linha da fixture
    # (so ASSIDUIDADE1/2/8/30 aparecem, cada uma em alguma linha) -- nao
    # deve bloquear.
    slot = _slot(assiduidade={"ASSIDUIDADE99": "Fernando Maurício"})
    assert not esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_alocar_grupo_pula_candidato_excluido_na_data_e_usa_o_outro():
    regras = [_regra("Fernando Maurício"), _regra("Ana Lima")]
    slot = _slot({"PROFESSOR(A) (S1)": "Fernando Maurício"})
    estado = EstadoExecucaoGrupo()
    limites = {"Fernando Maurício": 1, "Ana Lima": 1}

    decisoes = alocar_grupo(
        regras, [slot], estado, limites,
        excluse_header=EXCLUSE_HEADER, excluse_rows=EXCLUSE_ROWS,
    )

    assert decisoes[0].vencedor == "Ana Lima"
