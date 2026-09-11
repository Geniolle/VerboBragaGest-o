# -*- coding: utf-8 -*-
"""Regressao para a corrupcao de cabecalho encontrada em 2026-09-11 (ver
CHANGELOG/comentario em carregamento.py): se uma coluna obrigatoria de
BP ALGORITIMO desaparecer do cabecalho (renomeada/deslocada sem atualizar o
texto), `carregar_regras_colaboradores` deve falhar alto, nunca voltar a
carregar tudo em silencio com prioridade=999 (ou outro default) para todo
mundo."""
import pytest

from pastoreio_orquestrador.carregamento import (
    build_header_index, carregar_regras_colaboradores,
    validar_cabecalho_bp_algoritimo,
)

CABECALHO_OK = [
    "ID_TABLE", "NOME", "DEPARTAMENTO", "FUNÇÃO", "DIA DA SEMANA",
    "PRIORIDADE NA ALOCAÇÃO", "REPETIÇÃO MENSAL", "ALOCAR TODOS OS MESES",
    "SEMANA PREFERENCIAL", "CEIA ALTERNADA", "SEMANA ALTERNADA",
    "ALOCAÇÃO EXTRA", "ATRIBUIR AOS RECADOS", "SINC_COLABORADOR",
    "SINC_SEM_ALOCAÇÃO", "TEMA", "ATIVO",
]

LINHA_ANA = [
    "1", "Ana", "D. MINISTROS", "MINISTRO", "QUARTA-FEIRA",
    "1", "1", "FALSE", "0", "FALSE", "FALSE", "0", "", "", "", "", "TRUE",
]


def test_cabecalho_valido_carrega_normalmente():
    valores = [CABECALHO_OK, LINHA_ANA]
    regras = carregar_regras_colaboradores(valores)
    assert len(regras) == 1
    assert regras[0].prioridade == 1


def test_cabecalho_sem_prioridade_levanta_erro_alto():
    """Caso real (2026-09-11): a coluna G de CLAUDE_BP ALGORITIMO ficou com o
    cabecalho em branco em vez de 'PRIORIDADE NA ALOCAÇÃO'. Antes desta
    checagem, isso resultava em prioridade=999 para todo mundo, sem
    nenhum aviso."""
    cabecalho_quebrado = list(CABECALHO_OK)
    idx_prioridade = cabecalho_quebrado.index("PRIORIDADE NA ALOCAÇÃO")
    cabecalho_quebrado[idx_prioridade] = ""

    with pytest.raises(ValueError, match="PRIORIDADE NA ALOCAÇÃO"):
        carregar_regras_colaboradores([cabecalho_quebrado, LINHA_ANA])


def test_validar_cabecalho_lista_todas_as_colunas_faltando():
    idx = build_header_index(["ID_TABLE", "NOME"])
    faltando = validar_cabecalho_bp_algoritimo(idx)
    assert "PRIORIDADE NA ALOCAÇÃO" in faltando
    assert "ATIVO" in faltando
    assert "NOME" not in faltando
