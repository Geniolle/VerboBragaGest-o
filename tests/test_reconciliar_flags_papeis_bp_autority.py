from unittest.mock import Mock

import pytest

from scripts.Colaborador.reconciliar_flags_papeis_bp_autority import (
    SHEET_BP_AUTORITY,
    aplicar_plano,
    calcular_plano,
)


HEADER = [
    "ID_USER",
    "NOME",
    "MANAGER_MINISTROS",
    "MANAGER_CEIA",
    "DEPARTAMENTOS_MANAGER",
    "COORDENADOR_MINISTROS",
    "DEPARTAMENTOS_COORDENADOR",
]


def test_marca_flags_agregadas_quando_existe_papel_ativo():
    plano = calcular_plano(
        [
            HEADER,
            ["1", "Ana", "TRUE", "", "", "TRUE", ""],
        ]
    )

    assert plano.atualizacoes == [(2, 5, "TRUE"), (2, 7, "TRUE")]


def test_limpa_flags_agregadas_quando_nenhum_papel_esta_ativo():
    plano = calcular_plano(
        [
            HEADER,
            ["1", "Ana", "FALSE", "", "TRUE", "", "false"],
        ]
    )

    assert plano.atualizacoes == [(2, 5, ""), (2, 7, "")]


def test_nao_escreve_quando_flags_ja_estao_consistentes():
    plano = calcular_plano(
        [
            HEADER,
            ["1", "Ana", "TRUE", "", "true", "", ""],
            ["2", "Bruno", "", "", "", "TRUE", "TRUE"],
        ]
    )

    assert plano.atualizacoes == []
    assert plano.linhas_corretas == 2


def test_exige_as_duas_colunas_agregadas():
    with pytest.raises(RuntimeError, match="DEPARTAMENTOS_COORDENADOR"):
        calcular_plano([["ID_USER", "DEPARTAMENTOS_MANAGER"]])


def test_aplicacao_usa_spreadsheet_guard():
    plano = calcular_plano([HEADER, ["1", "Ana", "TRUE", "", "", "", ""]])
    guard = Mock()

    aplicar_plano(guard, plano)

    guard.batch_update_cells.assert_called_once_with(
        SHEET_BP_AUTORITY,
        [(2, 5, "TRUE")],
    )
