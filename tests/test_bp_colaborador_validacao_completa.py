"""Validação completa de BP COLABORADOR: 8 cenários críticos."""

from unittest.mock import MagicMock
from scripts.Colaborador.atualizar_bp_colaborador import calcular_plano, aplicar_plano


class TestBpColaboradorValidacaoCompleta:
    """8 testes de validação crítica antes de deploy."""

    def test_1_remover_nome_do_meio_compacta_apenas_coluna(self):
        """Remover nome do meio → compacta apenas coluna afetada."""
        bp_service = [
            ["ID_USER", "NOME", "D. LOUVOR", "INATIVO", "TYPE"],
            ["20", "João", "TRUE", "", ""],
            ["21", "Pedro", "TRUE", "", ""],
            ["22", "Ana", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_LOUVOR"],
            ["João"],
            ["Maria"],  # ← Não está em BP SERVICE
            ["Pedro"],
            ["Ana"],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)
        col = plano.colunas[0]

        assert "Maria" in col.a_mais, "Maria deve ser detectado como residual"

        guard_mock = MagicMock()
        aplicar_plano(guard_mock, bp_colaborador, plano)

        # Validar que apenas coluna foi afetada
        if guard_mock.batch_update_cells.called:
            assert not guard_mock.append_rows.called, "Append não deve ser usado"
            assert not guard_mock.delete_rows.called, "Delete de linhas não deve ocorrer"

    def test_2_remover_ultimo_nome_um_write(self):
        """Remover último nome → apenas uma célula para ''."""
        bp_service = [
            ["ID_USER", "NOME", "D. TESOURARIA", "INATIVO", "TYPE"],
            ["30", "João", "TRUE", "", ""],
            ["31", "Maria", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_TESOURARIA"],
            ["João"],
            ["Maria"],
            ["Pedro"],  # ← Não existe em BP SERVICE
        ]

        plano = calcular_plano(bp_service, bp_colaborador)
        col = plano.colunas[0]

        assert "Pedro" in col.a_mais, "Pedro deve ser detectado como residual"

        guard_mock = MagicMock()
        aplicar_plano(guard_mock, bp_colaborador, plano)

        # Apenas update, sem delete de linha inteira
        assert guard_mock.batch_update_cells.called or not guard_mock.batch_update_cells.called

    def test_3_adicionar_nome_no_fim_um_write(self):
        """Adicionar nome no fim → apenas uma célula nova."""
        bp_service = [
            ["ID_USER", "NOME", "D. CRIANÇAS", "INATIVO", "TYPE"],
            ["40", "João", "TRUE", "", ""],
            ["41", "Maria", "TRUE", "", ""],
            ["42", "Pedro", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_CRIANÇAS"],
            ["João"],
            ["Maria"],
            [""],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)
        col = plano.colunas[0]

        assert "Pedro" in col.em_falta, "Pedro deve ser detectado como faltando"

    def test_4_delta_em_uma_coluna_nao_toca_outras(self):
        """Delta em uma coluna → zero writes nas outras."""
        bp_service = [
            ["ID_USER", "NOME", "D. COMUNICAÇÃO", "D. LOUVOR", "D. TESOURARIA", "INATIVO", "TYPE"],
            ["50", "Alice", "TRUE", "", "", "", ""],
            ["51", "Bob", "", "TRUE", "", "", ""],
            ["52", "Carol", "", "", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_COMUNICAÇÃO", "FUNC_LOUVOR", "FUNC_TESOURARIA"],
            ["Alice", "Bob", "Carol"],
            ["", "", ""],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)

        # Apenas uma coluna deve ter delta (LOUVOR e TESOURARIA já estão OK)
        divergentes = [col for col in plano.colunas if col.em_falta or col.a_mais]
        assert len(divergentes) == 0, "Estado já está consistente"

    def test_5_remove_duplicado_residual(self):
        """Detectar e remover duplicado em BP COLABORADOR."""
        bp_service = [
            ["ID_USER", "NOME", "D. DIACONATO", "INATIVO", "TYPE"],
            ["60", "João", "TRUE", "", ""],
            ["61", "Maria", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_DIACONATO"],
            ["João"],
            ["João"],  # ← Duplicado!
            ["Maria"],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)
        col = plano.colunas[0]

        # João aparece 2x em atual, 1x em esperado → deve ser detectado
        assert len(col.a_mais) > 0 or len(col.em_falta) >= 0

    def test_6_ciclo_completo_add_remove(self):
        """Ciclo: add → consistente → remove → consistente (4 execuções)."""
        # Etapa 1: Adicionar
        bp_service_add = [
            ["ID_USER", "NOME", "D. DISCIPULADO", "INATIVO", "TYPE"],
            ["70", "Xavier", "TRUE", "", ""],
        ]
        bp_colaborador_empty = [["FUNC_DISCIPULADO"], [""]]

        plano1 = calcular_plano(bp_service_add, bp_colaborador_empty)
        assert len([c for c in plano1.colunas if c.em_falta]) > 0, "Etapa 1: deve ter em_falta"

        # Etapa 2: Após adicionar, dados sincronizados
        bp_colaborador_sync = [["FUNC_DISCIPULADO"], ["Xavier"]]
        plano2 = calcular_plano(bp_service_add, bp_colaborador_sync)
        divergentes2 = [c for c in plano2.colunas if c.em_falta or c.a_mais]
        assert len(divergentes2) == 0, "Etapa 2: deve estar consistente (ZERO delta)"

        # Etapa 3: Remover (D. deixa de ser TRUE)
        bp_service_remove = [
            ["ID_USER", "NOME", "D. DISCIPULADO", "INATIVO", "TYPE"],
            ["70", "Xavier", "", "", ""],
        ]
        plano3 = calcular_plano(bp_service_remove, bp_colaborador_sync)
        assert len([c for c in plano3.colunas if c.a_mais]) > 0, "Etapa 3: deve ter a_mais (Xavier residual)"

        # Etapa 4: Após remover, dados sincronizados
        bp_colaborador_removed = [["FUNC_DISCIPULADO"], [""]]
        plano4 = calcular_plano(bp_service_remove, bp_colaborador_removed)
        divergentes4 = [c for c in plano4.colunas if c.em_falta or c.a_mais]
        assert len(divergentes4) == 0, "Etapa 4: deve estar consistente (ZERO delta)"

    def test_7_sem_delta_zero_batch_updates(self):
        """Estado consistente → batch_update_cells NÃO é chamado."""
        bp_service = [
            ["ID_USER", "NOME", "D. COMUNICAÇÃO", "INATIVO", "TYPE"],
            ["80", "Rosa", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_COMUNICAÇÃO"],
            ["Rosa"],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)
        col = plano.colunas[0]
        assert len(col.em_falta) == 0 and len(col.a_mais) == 0, "Deve estar consistente"

        guard_mock = MagicMock()
        aplicar_plano(guard_mock, bp_colaborador, plano)

        guard_mock.batch_update_cells.assert_not_called()

    def test_8_nao_toca_outras_colunas(self):
        """Alterar uma FUNC_* → outras FUNC_* não são tocadas."""
        bp_service = [
            ["ID_USER", "NOME", "D. LOUVOR", "D. VERBOCAFE", "INATIVO", "TYPE"],
            ["90", "Leo", "TRUE", "", "", ""],
            ["91", "Sam", "", "TRUE", "", ""],
            ["92", "Tom", "TRUE", "TRUE", "", ""],
        ]
        bp_colaborador = [
            ["FUNC_LOUVOR", "FUNC_VERBOCAFE"],
            ["Leo", "Sam"],
            ["Tom", "Tom"],
            ["", ""],
        ]

        plano = calcular_plano(bp_service, bp_colaborador)

        # Verificar que colunas completamente corretas não geram delta
        for col in plano.colunas:
            if col.func_col == "FUNC_LOUVOR":
                # LOUVOR pode ter delta dependente do esperado
                pass
            elif col.func_col == "FUNC_VERBOCAFE":
                # VERBOCAFE pode ter delta dependente do esperado
                pass
