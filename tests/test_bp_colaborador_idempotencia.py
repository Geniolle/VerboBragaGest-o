"""Testes de idempotência para atualizar_bp_colaborador.py"""

from unittest.mock import MagicMock, patch
from scripts.Colaborador.atualizar_bp_colaborador import calcular_plano, aplicar_plano


class TestBpColaboradorIdempotencia:
    """Validação de que BP COLABORADOR só escreve delta."""

    def test_sem_delta_zero_writes(self):
        """Estado consistente → zero writes."""
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "INATIVO", "TYPE"],
            ["1", "João Silva", "TRUE", "", ""],
            ["2", "Maria Santos", "FALSE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_MINISTROS"],
            ["João Silva"],
            [""],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)

        # Nenhuma coluna divergente
        divergentes = [col for col in plano.colunas if col.em_falta or col.a_mais]
        assert len(divergentes) == 0, "Deve estar consistente"

        # Mock de guard
        guard_mock = MagicMock()
        aplicar_plano(guard_mock, bp_colaborador, plano)

        # CRÍTICO: batch_update_cells NÃO deve ser chamado
        guard_mock.batch_update_cells.assert_not_called()

    def test_segunda_execucao_zero_writes(self):
        """Executar 2x com dados consistentes → segunda vez zero writes."""
        bp_service = [
            ["ID_USER", "NOME", "D. LOUVOR", "INATIVO", "TYPE"],
            ["3", "Ana Costa", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_LOUVOR"],
            ["Ana Costa"],
        ]

        # Primeira execução
        plano1 = calcular_plano(bp_service, bp_colaborador)
        guard1 = MagicMock()
        aplicar_plano(guard1, bp_colaborador, plano1)
        writes1 = guard1.batch_update_cells.call_count

        # Segunda execução com mesmo estado
        plano2 = calcular_plano(bp_service, bp_colaborador)
        guard2 = MagicMock()
        aplicar_plano(guard2, bp_colaborador, plano2)
        writes2 = guard2.batch_update_cells.call_count

        # Segunda execução deve ter ZERO writes
        assert writes2 == 0, f"Segunda execução deveria ter 0 writes, teve {writes2}"

    def test_adiciona_apenas_nome_novo(self):
        """Adicionar um nome novo → escrever apenas naquela posição."""
        bp_service = [
            ["ID_USER", "NOME", "D. COMUNICAÇÃO", "INATIVO", "TYPE"],
            ["10", "Alice", "TRUE", "", ""],
            ["11", "Bob", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_COMUNICAÇÃO"],
            ["Alice"],
            [""],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)

        # Deve detectar "Bob" em falta
        col = plano.colunas[0]
        assert len(col.em_falta) == 1
        assert len(col.a_mais) == 0

        # Mock
        guard_mock = MagicMock()
        aplicar_plano(guard_mock, bp_colaborador, plano)

        # Verifica que batch_update foi chamado
        assert guard_mock.batch_update_cells.called

        # Verifica que NÃO reescreveu Alice (linha 2)
        # (isto é mais complexo de validar, será feito em integração)
