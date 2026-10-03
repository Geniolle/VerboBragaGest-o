"""Testes para detecção correcta de resíduos (causa raiz: Cleitinho Fubá)."""

import pytest
from scripts.Colaborador.reconciliar_cadeia_departamentos import calcular_plano


class TestResiduosDetectados:
    """Validação de detecção de resíduos com D.* vazio vs FALSE."""

    def test_remocao_detecta_departamentos_vazio_com_bp_autority_flag(self):
        """Detectar resíduo quando DEPARTAMENTOS vazio mas BP AUTORITY=TRUE."""
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["122", "Cleitinho", "", "", "TRUE", ""],  # Vazio, não FALSE
        ]
        bp_autority = [["ID_USER", "NOME"], ["122", "Cleitinho"]]
        bp_algoritimo = [["ID_USER"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "122"
        assert "resíduo" in plano.pessoas_remocao[0].motivo.lower()

    def test_remocao_detecta_linha_autority_com_flags_vazias(self):
        """Detectar resíduo quando linha em BP AUTORITY existe mas flags vazias."""
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["71", "Roberta", "", "", "", ""],  # Tudo vazio
        ]
        bp_autority = [["ID_USER", "NOME"], ["71", "Roberta"]]
        bp_algoritimo = [["ID_USER"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        assert plano.pessoas_remocao[0].id_user == "71"

    def test_d_vazio_vs_false_sao_equivalentes(self):
        """Ambos D.="" e D.="FALSE" devem resultar em remocao se houver residuo."""
        # Caso 1: D vazio
        bp_service_1 = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["1", "Pessoa", "", "", "TRUE", ""],
        ]
        bp_autority_1 = [["ID_USER"], ["1"]]
        plano_1 = calcular_plano(bp_service_1, bp_autority_1, [["ID_USER"]])

        # Caso 2: D="FALSE"
        bp_service_2 = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["2", "Pessoa", "FALSE", "", "TRUE", ""],
        ]
        bp_autority_2 = [["ID_USER"], ["2"]]
        plano_2 = calcular_plano(bp_service_2, bp_autority_2, [["ID_USER"]])

        # Ambos devem ser detectados para remoção
        assert len(plano_1.pessoas_remocao) == 1
        assert len(plano_2.pessoas_remocao) == 1

    def test_d_true_nao_dispara_remocao(self):
        """D.=TRUE não deve disparar remoção mesmo com outros campos vazios."""
        bp_service = [
            ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["99", "Ativa", "TRUE", "", "", ""],
        ]
        bp_autority = [["ID_USER"], ["99"]]
        bp_algoritimo = [["ID_USER"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        # Não deve estar em remoção
        assert all(p.id_user != "99" for p in plano.pessoas_remocao)

    def test_multiplos_residuos_listados_no_motivo(self):
        """Motivo deve listar todos os resíduos detectados."""
        bp_service = [
            ["ID_USER", "NOME", "D. X", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
            ["100", "Multi", "", "TRUE", "TRUE", ""],
        ]
        bp_autority = [["ID_USER"], ["100"]]
        bp_algoritimo = [["ID_USER"], ["100"]]

        plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

        assert len(plano.pessoas_remocao) == 1
        motivo = plano.pessoas_remocao[0].motivo
        assert "DEPARTAMENTOS" in motivo
        assert "BP AUTORITY" in motivo or "linha" in motivo
