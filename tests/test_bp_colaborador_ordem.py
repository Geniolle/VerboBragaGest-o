"""Teste crítico: diferença apenas de ordem não gera escrita."""

from unittest.mock import MagicMock
from scripts.Colaborador.atualizar_bp_colaborador import calcular_plano, aplicar_plano


def test_mesmos_nomes_ordem_diferente_zero_writes():
    """CRÍTICO: Apenas diferença de ordem → ZERO WRITES."""

    bp_service = [
        ["ID_USER", "NOME", "D. LOUVOR", "INATIVO", "TYPE"],
        ["1", "Maria", "TRUE", "", ""],
        ["2", "João", "TRUE", "", ""],
    ]

    # ATUAL tem ordem diferente, mas mesmo conjunto
    bp_colaborador = [
        ["FUNC_LOUVOR"],
        ["Maria"],  # Maria primeiro
        ["João"],   # João segundo
    ]

    plano = calcular_plano(bp_service, bp_colaborador)
    col = plano.colunas[0]

    # O conjunto é idêntico, apenas ordem diferente
    # Deve resultar em ZERO delta
    assert len(col.em_falta) == 0, f"Não deveria haver em_falta: {col.em_falta}"
    assert len(col.a_mais) == 0, f"Não deveria haver a_mais: {col.a_mais}"

    # Validar que aplicar_plano não faz escrita
    guard_mock = MagicMock()
    aplicar_plano(guard_mock, bp_colaborador, plano)

    guard_mock.batch_update_cells.assert_not_called()
    print("✅ CRÍTICO PASSADO: Ordem diferente resultou em ZERO WRITES")
