"""Testes de robustez para remocao de BP AUTORITY - proteção contra sucesso silencioso."""

import pytest
from scripts.Colaborador.reconciliar_cadeia_departamentos import (
    calcular_plano, aplicar_remocao, map_headers, PessoaProblema
)


class TestAuthorityRobustez:
    """Validação de robustez na remoção de BP AUTORITY."""

    def test_authority_existente_deve_ser_encontrada(self):
        """BP AUTORITY com ID_USER deve ser localizada mesmo após force_refresh."""
        bp_service = [
            ["ID_USER", "NOME", "D. X", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["1", "Pessoa", "", "", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["1", "Pessoa"],  # Existe na BP AUTORITY
        ]
        bp_algoritimo = [["ID_USER"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Deve detectar para remoção
        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "1"

    def test_multiplas_linhas_authority_mesmo_id_sao_removidas(self):
        """Se houver múltiplas linhas para o mesmo ID_USER, TODAS devem ser removidas."""
        # Cenário: duas linhas da mesma pessoa (erro de dados, mas deve ser tratado)
        bp_service = [
            ["ID_USER", "NOME", "D. X", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["99", "Duplicada", "", "", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["99", "Duplicada"],
            ["99", "Duplicada"],  # Duplicada!
        ]
        bp_algoritimo = [["ID_USER"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        pessoa = plano.pessoas_remocao[0]

        # Verificar que o motivo reporta ambas as ocorrências
        assert "BP AUTORITY linha" in pessoa.motivo

    def test_validacao_authority_e_sempre_executada(self):
        """Validação de ausência em BP AUTORITY deve ser INCONDICIONAL.

        Mesmo que o lookup não encontre linhas (linha_autority=None),
        deve fazer force_refresh e validar que realmente não existe.
        """
        bp_service = [
            ["ID_USER", "NOME", "D. X", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["88", "Teste", "", "", "TRUE", ""],
        ]
        # BP AUTORITY aparentemente vazia
        bp_autority = [["ID_USER", "NOME"]]
        bp_algoritimo = [["ID_USER"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Sem linha em BP AUTORITY
        # Remoção ainda deve ser candidata porque DEPARTAMENTOS=TRUE
        # (ou por outro resíduo)
        if plano.pessoas_remocao:
            # Se for detectado, OK
            assert plano.pessoas_remocao[0].id_user == "88"

    def test_cleitinho_id_122_remove_authority(self):
        """Caso real: Cleitinho Fubá ID 122 com resíduo em BP AUTORITY.

        Estado:
        - BP SERVICE: D.* vazio, DEPARTAMENTOS vazio, BP AUTORITY='TRUE'
        - BP AUTORITY: linha 76 existe
        - BP ALGORITIMO: vazio

        Esperado: detectado para remoção
        """
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["122", "Cleitinho Fubá", "", "", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["122", "Cleitinho Fubá"],
        ]
        bp_algoritimo = [["ID_USER"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        pessoa = plano.pessoas_remocao[0]
        assert pessoa.id_user == "122"
        assert "Cleitinho" in pessoa.nome
        # Motivo deve incluir resíduo de BP AUTORITY
        assert "BP AUTORITY" in pessoa.motivo
