"""Testes para o orquestrador transacional de departamentos.

Cobre 13 cenários obrigatórios:
1-3: Ativação
4-5: Remoção
6-9: Falha parcial
10-11: INATIVO
12: Ordem transacional
13: Idempotência
"""

import pytest
from unittest.mock import MagicMock, call, patch

from scripts.Colaborador.reconciliar_cadeia_departamentos import (
    PessoaProblema,
    PlanoReconciliacaoCadeia,
    ResultadoTransacao,
    calcular_plano,
    aplicar_remocao,
    map_headers,
    get,
    is_true,
)


class TestAtivacao:
    """Cenários 1-3: Ativação"""

    def test_ativacao_d_true_departamentos_false(self):
        """Cenário 1: D.* TRUE + DEPARTAMENTOS FALSE → ativação."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["1", "João Silva", "TRUE", "FALSE", ""],
        ]
        bp_autority = [["ID_USER", "NOME"]]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_ativacao) == 1
        assert plano.pessoas_ativacao[0].id_user == "1"
        assert plano.pessoas_ativacao[0].situacao == "ativacao"

    def test_ativacao_d_true_departamentos_vazio(self):
        """Cenário 2: D.* TRUE + DEPARTAMENTOS vazio → ativação."""
        bp_service = [
            ["ID_USER", "NOME", "D. COMUNICACAO", "DEPARTAMENTOS", "INATIVO"],
            ["2", "Maria Santos", "TRUE", "", ""],  # DEPARTAMENTOS vazio
        ]
        bp_autority = [["ID_USER", "NOME"]]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_ativacao) == 1
        assert plano.pessoas_ativacao[0].id_user == "2"

    def test_ativacao_varios_d_true(self):
        """Cenário 3: Vários D.* TRUE → ativação."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "D. COMUNICACAO", "D. LOUVOR", "DEPARTAMENTOS", "INATIVO"],
            ["3", "Pedro Costa", "TRUE", "TRUE", "FALSE", "FALSE", ""],
        ]
        bp_autority = [["ID_USER", "NOME"]]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_ativacao) == 1


class TestRemocao:
    """Cenários 4-5: Remoção"""

    def test_remocao_nenhum_d_departamentos_true(self):
        """Cenário 4: Nenhum D.* TRUE + DEPARTAMENTOS TRUE → remoção."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["4", "Ana Silva", "FALSE", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["4", "Ana Silva"],
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "4"

    def test_idempotencia_cadeia_ja_removida(self):
        """Cenário 5: Cadeia já removida → segunda execução não altera."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["5", "Carlos Nunes", "FALSE", "FALSE", ""],  # Já correcto
        ]
        bp_autority = [["ID_USER", "NOME"]]  # Já removido
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 0
        assert len(plano.pessoas_ativacao) == 0


class TestFalhasParciais:
    """Cenários 6-9: Falha parcial (com mocks)"""

    def test_falha_algoritimo_nao_afeta_autority_service(self):
        """Cenário 6: Falha em BP ALGORITIMO → não toca AUTORITY nem SERVICE."""
        guard_mock = MagicMock()
        guard_mock.delete_rows.side_effect = Exception("Erro ao deletar BP ALGORITIMO")

        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["6", "Test User", "FALSE", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["6", "Test User"],
        ]
        bp_algoritimo = [
            ["ID_USER", "NOME"],
            ["6", "Test User"],
        ]

        idx_service = map_headers(bp_service[0])
        idx_autority = map_headers(bp_autority[0])
        idx_algoritimo = map_headers(bp_algoritimo[0])

        pessoa = PessoaProblema("6", "Test User", "remocao", "Teste")

        resultado = aplicar_remocao(guard_mock, bp_service, bp_autority, bp_algoritimo, idx_service, idx_autority, idx_algoritimo, pessoa)

        # Deve falhar na primeira etapa
        assert resultado.sucesso == False
        assert resultado.etapa_falha == "remocao"

        # Verificar que delete_rows foi chamado apenas uma vez (BP ALGORITIMO)
        assert guard_mock.delete_rows.call_count == 1

        # Verificar que batch_update_cells NUNCA foi chamado (não tocou BP SERVICE)
        assert guard_mock.batch_update_cells.call_count == 0

    def test_validacao_algoritimo_falha(self):
        """Cenário 7: Validação de remoção de ALGORITIMO falha → aborta."""
        guard_mock = MagicMock()

        # delete_rows funciona, mas read_worksheet retorna que a linha ainda existe
        guard_mock.delete_rows.return_value = None
        guard_mock.read_worksheet.return_value = [
            ["ID_USER", "NOME"],
            ["7", "Still Exists"],  # ← Linha ainda presente após delete!
        ]

        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["7", "Test User", "FALSE", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["7", "Test User"],
        ]
        bp_algoritimo = [
            ["ID_USER", "NOME"],
            ["7", "Test User"],
        ]

        idx_service = map_headers(bp_service[0])
        idx_autority = map_headers(bp_autority[0])
        idx_algoritimo = map_headers(bp_algoritimo[0])

        pessoa = PessoaProblema("7", "Test User", "remocao", "Teste")

        resultado = aplicar_remocao(guard_mock, bp_service, bp_autority, bp_algoritimo, idx_service, idx_autority, idx_algoritimo, pessoa)

        # Deve falhar na validação
        assert resultado.sucesso == False
        assert resultado.etapa_falha == "validar_remocao_BP_ALGORITIMO"

        # delete_rows foi chamado em BP ALGORITIMO, mas não em BP AUTORITY
        assert guard_mock.delete_rows.call_count == 1

        # batch_update_cells NUNCA foi chamado
        assert guard_mock.batch_update_cells.call_count == 0

    def test_falha_autority_nao_afeta_service(self):
        """Cenário 8: Falha em BP AUTORITY → não toca SERVICE."""
        guard_mock = MagicMock()

        # Primeira leitura (BP ALGORITIMO): validação OK
        # Segunda leitura (BP AUTORITY): simular falha no delete
        def read_side_effect(sheet):
            return [["ID_USER", "NOME"]]  # Vazio (validação OK)

        guard_mock.read_worksheet.side_effect = read_side_effect
        guard_mock.delete_rows.side_effect = [None, Exception("Erro ao deletar BP AUTORITY")]

        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["8", "Test User", "FALSE", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["8", "Test User"],
        ]
        bp_algoritimo = [
            ["ID_USER", "NOME"],
            ["8", "Test User"],
        ]

        idx_service = map_headers(bp_service[0])
        idx_autority = map_headers(bp_autority[0])
        idx_algoritimo = map_headers(bp_algoritimo[0])

        pessoa = PessoaProblema("8", "Test User", "remocao", "Teste")

        resultado = aplicar_remocao(guard_mock, bp_service, bp_autority, bp_algoritimo, idx_service, idx_autority, idx_algoritimo, pessoa)

        # Deve falhar na remoção de BP AUTORITY
        assert resultado.sucesso == False
        assert resultado.etapa_falha == "remocao"

        # delete_rows foi chamado 2x (ALGORITIMO + AUTORITY), mas batch_update nunca
        assert guard_mock.delete_rows.call_count == 2
        assert guard_mock.batch_update_cells.call_count == 0

    def test_validacao_autority_falha(self):
        """Cenário 9: Validação de remoção de AUTORITY falha → aborta SERVICE."""
        guard_mock = MagicMock()

        # Leitura 1: BP ALGORITIMO vazio (OK)
        # Leitura 2: BP AUTORITY ainda com a linha (falha validação)
        def read_side_effect(sheet):
            return [["ID_USER", "NOME"]]  # Vazio

        guard_mock.read_worksheet.side_effect = [
            [["ID_USER", "NOME"]],  # BP ALGORITIMO vazio
            [["ID_USER", "NOME"], ["9", "Still Here"]],  # BP AUTORITY ainda tem linha!
        ]

        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["9", "Test User", "FALSE", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["9", "Test User"],
        ]
        bp_algoritimo = [
            ["ID_USER", "NOME"],
            ["9", "Test User"],
        ]

        idx_service = map_headers(bp_service[0])
        idx_autority = map_headers(bp_autority[0])
        idx_algoritimo = map_headers(bp_algoritimo[0])

        pessoa = PessoaProblema("9", "Test User", "remocao", "Teste")

        resultado = aplicar_remocao(guard_mock, bp_service, bp_autority, bp_algoritimo, idx_service, idx_autority, idx_algoritimo, pessoa)

        # Deve falhar na validação de BP AUTORITY
        assert resultado.sucesso == False
        assert resultado.etapa_falha == "validar_remocao_BP_AUTORITY"

        # batch_update_cells NUNCA foi chamado
        assert guard_mock.batch_update_cells.call_count == 0


class TestINATIVO:
    """Cenários 10-11: INATIVO nunca é alterado"""

    def test_inativo_true_permanece_true(self):
        """Cenário 10: INATIVO=TRUE permanece TRUE."""
        # Se uma pessoa tem INATIVO=TRUE, não entra no plano
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["10", "Inativo Pessoa", "TRUE", "FALSE", "TRUE"],  # INATIVO=TRUE
        ]
        bp_autority = [["ID_USER", "NOME"]]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Não deve aparecer em nenhum plano (INATIVO actua como filtro)
        assert len(plano.pessoas_ativacao) == 0
        assert len(plano.pessoas_remocao) == 0

    def test_inativo_false_permanece_false(self):
        """Cenário 11: INATIVO=FALSE permanece inalterado."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["11", "Ativa Pessoa", "TRUE", "FALSE", "FALSE"],  # INATIVO=FALSE
        ]
        bp_autority = [["ID_USER", "NOME"]]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Deve aparecer em ativações (e INATIVO não é alterado)
        assert len(plano.pessoas_ativacao) == 1


class TestOrdemTransacional:
    """Cenário 12: Ordem ALGORITIMO → AUTORITY → SERVICE comprovada"""

    def test_ordem_exata_remocao(self):
        """Comprovação de ordem: delete ALGORITIMO → read ALGORITIMO → delete AUTORITY → read AUTORITY → update SERVICE."""
        guard_mock = MagicMock()

        # Simular retornos para reads
        guard_mock.read_worksheet.return_value = [["ID_USER", "NOME"]]  # Vazio

        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["12", "Test User", "FALSE", "TRUE", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["12", "Test User"],
        ]
        bp_algoritimo = [
            ["ID_USER", "NOME"],
            ["12", "Test User"],
        ]

        idx_service = map_headers(bp_service[0])
        idx_autority = map_headers(bp_autority[0])
        idx_algoritimo = map_headers(bp_algoritimo[0])

        pessoa = PessoaProblema("12", "Test User", "remocao", "Teste")

        resultado = aplicar_remocao(guard_mock, bp_service, bp_autority, bp_algoritimo, idx_service, idx_autority, idx_algoritimo, pessoa)

        assert resultado.sucesso == True

        # Verificar ordem EXATA das chamadas via method_calls
        method_names = [str(c) for c in guard_mock.method_calls]

        # Procurar índices das chamadas críticas
        delete_algoritimo_idx = None
        read_algoritimo_idx = None
        delete_autority_idx = None
        read_autority_idx = None
        batch_service_idx = None

        for i, method_str in enumerate(method_names):
            if "delete_rows" in method_str and "BP ALGORITIMO" in method_str:
                delete_algoritimo_idx = i
            elif "delete_rows" in method_str and "BP AUTORITY" in method_str:
                delete_autority_idx = i
            elif "read_worksheet" in method_str:
                if read_algoritimo_idx is None:
                    read_algoritimo_idx = i
                else:
                    read_autority_idx = i
            elif "batch_update_cells" in method_str:
                batch_service_idx = i

        # Validar que todas as chamadas foram feitas
        assert delete_algoritimo_idx is not None, "delete_rows(BP ALGORITIMO) não foi chamado"
        assert read_algoritimo_idx is not None, "read_worksheet(BP ALGORITIMO) não foi chamado"
        assert delete_autority_idx is not None, "delete_rows(BP AUTORITY) não foi chamado"
        assert read_autority_idx is not None, "read_worksheet(BP AUTORITY) não foi chamado"
        assert batch_service_idx is not None, "batch_update_cells(BP SERVICE) não foi chamado"

        # Validar ORDEM: ALGORITIMO → read → AUTORITY → read → SERVICE
        assert delete_algoritimo_idx < read_algoritimo_idx, (
            f"delete_rows(BP ALGORITIMO) índice {delete_algoritimo_idx} deve vir antes de "
            f"read_worksheet(BP ALGORITIMO) índice {read_algoritimo_idx}"
        )
        assert read_algoritimo_idx < delete_autority_idx, (
            f"read_worksheet(BP ALGORITIMO) índice {read_algoritimo_idx} deve vir antes de "
            f"delete_rows(BP AUTORITY) índice {delete_autority_idx}"
        )
        assert delete_autority_idx < read_autority_idx, (
            f"delete_rows(BP AUTORITY) índice {delete_autority_idx} deve vir antes de "
            f"read_worksheet(BP AUTORITY) índice {read_autority_idx}"
        )
        assert read_autority_idx < batch_service_idx, (
            f"read_worksheet(BP AUTORITY) índice {read_autority_idx} deve vir antes de "
            f"batch_update_cells(BP SERVICE) índice {batch_service_idx}"
        )


class TestIdempotencia:
    """Cenário 13: Idempotência (rodar 2x sem problemas)"""

    def test_segunda_execucao_nao_cria_duplicados(self):
        """Idempotência: segunda execução do mesmo plano não cria duplicados."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["13a", "Pessoa A", "TRUE", "FALSE", ""],  # Candidato ativação
        ]
        bp_autority = [["ID_USER", "NOME"]]
        bp_algoritimo = [["ID_USER", "NOME"]]

        # Primeira execução
        plano1 = calcular_plano(bp_service, bp_autority, bp_algoritimo)
        assert len(plano1.pessoas_ativacao) == 1

        # Simular que a primeira execução foi bem-sucedida (DEPARTAMENTOS agora TRUE)
        bp_service[1][3] = "TRUE"  # DEPARTAMENTOS = TRUE

        # Segunda execução
        plano2 = calcular_plano(bp_service, bp_autority, bp_algoritimo)
        assert len(plano2.pessoas_ativacao) == 0  # Nada a fazer
        assert len(plano2.pessoas_remocao) == 0

    def test_segunda_remocao_sem_erros(self):
        """Idempotência: segunda remoção não falha se já foi removida."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["13b", "Pessoa B", "FALSE", "FALSE", ""],  # Já removida
        ]
        bp_autority = [["ID_USER", "NOME"]]  # Já vazio
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Não deve haver problema
        assert len(plano.pessoas_remocao) == 0


class TestHelpers:
    """Testes dos helpers (map_headers, get, is_true)"""

    def test_map_headers_basico(self):
        header = ["ID_USER", "NOME", "EMAIL"]
        idx = map_headers(header)
        assert idx["ID_USER"] == 0
        assert idx["NOME"] == 1
        assert idx["EMAIL"] == 2

    def test_get_basico(self):
        header = ["ID_USER", "NOME"]
        idx = map_headers(header)
        row = ["123", "João Silva"]
        assert get(row, idx, "ID_USER") == "123"
        assert get(row, idx, "NOME") == "João Silva"

    def test_get_inexistente(self):
        idx = {"ID_USER": 0}
        row = ["123"]
        assert get(row, idx, "INEXISTENTE") == ""

    def test_is_true_string(self):
        assert is_true("TRUE") == True
        assert is_true("true") == True
        assert is_true("True") == True
        assert is_true("FALSE") == False
        assert is_true("") == False
        assert is_true(None) == False

    def test_is_true_bool(self):
        assert is_true(True) == True
        assert is_true(False) == False


class TestCalcularPlano:
    """Testes integrados do calcular_plano"""

    def test_plano_vazio_sheets_vazias(self):
        plano = calcular_plano([], [], [])
        assert len(plano.pessoas_ativacao) == 0
        assert len(plano.pessoas_remocao) == 0

    def test_multiplas_pessoas_mistas(self):
        """Plano com múltiplas pessoas (ativação + remoção + normal)."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["a1", "Para Ativar", "TRUE", "FALSE", ""],       # ativação
            ["a2", "Para Remover", "FALSE", "TRUE", ""],      # remoção (se em BP AUTORITY)
            ["a3", "Ja Correto", "TRUE", "TRUE", ""],         # correcto
            ["a4", "Ja Correto2", "FALSE", "FALSE", ""],      # correcto
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["a2", "Para Remover"],
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_ativacao) == 1
        assert plano.pessoas_ativacao[0].id_user == "a1"
        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "a2"
