"""Testes específicos para os 4 resíduos reais encontrados."""

import pytest
from scripts.Colaborador.reconciliar_cadeia_departamentos import (
    calcular_plano,
    map_headers,
)


class TestResíduosReais:
    """Validação dos 4 resíduos encontrados na auditoria real."""

    def test_residuo_id_122_cleitinho_fuba(self):
        """ID_USER 122: Cleitinho Fubá - resíduo em BP AUTORITY, nenhum D.*."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["122", "Cleitinho Fubá", "", "", ""],  # Nenhum D.*, vazio
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["122", "Cleitinho Fubá"],  # Existe em BP AUTORITY
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Deve aparecer em remoção
        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "122"
        assert "BP AUTORITY" in plano.pessoas_remocao[0].motivo

    def test_residuo_id_22_daniela_lopes(self):
        """ID_USER 22: Daniela Lopes - resíduo em BP AUTORITY."""
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "INATIVO"],
            ["22", "Daniela Lopes", "", "", ""],  # Nenhum D.*
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["22", "Daniela Lopes"],
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "22"

    def test_residuo_id_52_lucenildo_araujo(self):
        """ID_USER 52: Lucenildo Araujo - resíduo em BP AUTORITY."""
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "INATIVO"],
            ["52", "Lucenildo Araujo", "", "", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["52", "Lucenildo Araujo"],
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "52"

    def test_residuo_id_71_roberta_delano(self):
        """ID_USER 71: Roberta Delano - resíduo em BP AUTORITY."""
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "INATIVO"],
            ["71", "Roberta Delano", "", "", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["71", "Roberta Delano"],
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "71"

    def test_todos_4_residuos_simultaneamente(self):
        """Detectar todos os 4 resíduos numa única execução."""
        bp_service = [
            ["ID_USER", "NOME", "D. PASTOREIO", "DEPARTAMENTOS", "INATIVO"],
            ["22", "Daniela Lopes", "", "", ""],
            ["52", "Lucenildo Araujo", "", "", ""],
            ["71", "Roberta Delano", "", "", ""],
            ["122", "Cleitinho Fubá", "", "", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["22", "Daniela Lopes"],
            ["52", "Lucenildo Araujo"],
            ["71", "Roberta Delano"],
            ["122", "Cleitinho Fubá"],
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 4
        ids = {p.id_user for p in plano.pessoas_remocao}
        assert ids == {"22", "52", "71", "122"}

    def test_chave_funcional_davi_suzana_duas_funcoes(self):
        """Davi Fenner + Suzana Fonseca: CEIA e MINISTRO são funções distintas."""
        # Não são duplicados se a chave é ID_USER + DEPARTAMENTO + FUNÇÃO
        # Este teste apenas documenta que não devem ser removidas
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "INATIVO"],
            ["93", "Davi Fenner", "TRUE", "TRUE", ""],
            ["75", "Suzana Fonseca", "TRUE", "TRUE", ""],
        ]
        bp_autority = [
            ["ID_USER", "NOME"],
            ["93", "Davi Fenner"],
            ["75", "Suzana Fonseca"],
        ]
        bp_algoritimo = [["ID_USER", "NOME"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Não devem aparecer em remoção (têm D. MINISTROS = TRUE)
        assert len(plano.pessoas_remocao) == 0
        assert len(plano.pessoas_ativacao) == 0  # Já estão ativadas
