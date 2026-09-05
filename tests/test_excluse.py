from datetime import date

from pastoreio_orquestrador.carregamento import build_header_index
from pastoreio_orquestrador.models import RegraColaborador, SlotAgenda
from pastoreio_orquestrador.motor import (
    EstadoExecucaoGrupo,
    alocar_grupo,
    esta_bloqueado_por_excluse,
)

# Estrutura real da aba Excluse (confirmada em 2026-09-05): a funcao (coluna
# "COLUNAS") indica a linha, e a coluna "ID_<DEPARTAMENTO>" guarda o NOME de
# uma das colunas genericas ASSIDUIDADE1..30 de AppAnualGlobal. O VALOR
# dessa coluna, na linha do slot, e o nome do colaborador excluido naquela
# data (nao um booleano).
EXCLUSE_HEADER = build_header_index(["COLUNAS", "ID_MINISTROS", "ID_AUXILIAR"])
EXCLUSE_ROWS = [
    ["MINISTRO", "ASSIDUIDADE1", "ASSIDUIDADE1"],
    ["AUXILIAR", "ASSIDUIDADE2", "ASSIDUIDADE2"],
]


def _slot(assiduidade: dict[str, str]) -> SlotAgenda:
    return SlotAgenda(
        row_index=1,
        data=date(2026, 1, 7),
        dia_da_semana="QUARTA-FEIRA",
        tema="",
        mes_key="2026-01",
        semana_do_mes=1,
        is_ultima_ocorrencia_do_mes=False,
        assiduidade=assiduidade,
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


def test_candidato_com_nome_na_coluna_assiduidade_mapeada_esta_bloqueado():
    slot = _slot({"ASSIDUIDADE1": "Fernando Maurício"})
    assert esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_outro_candidato_na_mesma_data_nao_esta_bloqueado():
    slot = _slot({"ASSIDUIDADE1": "Fernando Maurício"})
    assert not esta_bloqueado_por_excluse(
        "Ana Lima", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_bloqueio_e_especifico_da_coluna_assiduidade_da_funcao():
    # ASSIDUIDADE2 pertence a AUXILIAR, nao a MINISTRO: nao deve bloquear.
    slot = _slot({"ASSIDUIDADE2": "Fernando Maurício"})
    assert not esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_sem_valor_na_coluna_assiduidade_ninguem_bloqueado():
    slot = _slot({})
    assert not esta_bloqueado_por_excluse(
        "Fernando Maurício", "D. MINISTROS", "MINISTRO", slot, EXCLUSE_HEADER, EXCLUSE_ROWS
    )


def test_alocar_grupo_pula_candidato_excluido_na_data_e_usa_o_outro():
    regras = [_regra("Fernando Maurício"), _regra("Ana Lima")]
    slot = _slot({"ASSIDUIDADE1": "Fernando Maurício"})
    estado = EstadoExecucaoGrupo()
    limites = {"Fernando Maurício": 1, "Ana Lima": 1}

    decisoes = alocar_grupo(
        regras, [slot], estado, limites,
        excluse_header=EXCLUSE_HEADER, excluse_rows=EXCLUSE_ROWS,
    )

    assert decisoes[0].vencedor == "Ana Lima"
