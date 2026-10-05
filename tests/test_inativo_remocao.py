"""Teste: pessoas INATIVO=TRUE devem ser removidas da cadeia."""

from scripts.Colaborador.reconciliar_cadeia_departamentos import calcular_plano


def test_inativo_true_com_residuo_para_remocao():
    """INATIVO=TRUE com resíduo em BP AUTORITY → deve estar em pessoas_remocao."""

    bp_service = [
        ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
        ["79", "Victor Lopes", "FALSE", "", "TRUE", "TRUE"],  # INATIVO!
    ]

    bp_autority = [
        ["ID_USER", "NOME", "COLABORADOR_CENTRODECURA", "COLABORADOR_LOUVOR"],
        ["79", "Victor Lopes", "TRUE", "TRUE"],  # Resíduo!
    ]

    bp_algoritimo = [
        ["ID_USER", "NOME"],
        ["79", "Victor Lopes"],  # Resíduo!
        ["79", "Victor Lopes"],  # Segundo vínculo
    ]

    plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

    # Deve estar em pessoas_remocao
    assert len(plano.pessoas_remocao) == 1, f"Esperava 1 para remocao, obteve {len(plano.pessoas_remocao)}"

    pessoa = plano.pessoas_remocao[0]
    assert pessoa.id_user == "79"
    assert pessoa.nome == "Victor Lopes"
    assert pessoa.situacao == "remocao"
    assert "INATIVO=TRUE" in pessoa.motivo
    assert "BP AUTORITY" in pessoa.motivo


def test_inativo_true_sem_residuo_ignorado():
    """INATIVO=TRUE mas SEM resíduo → não deve estar em pessoas_remocao."""

    bp_service = [
        ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
        ["80", "Pessoa Inativa", "FALSE", "", "", "TRUE"],  # INATIVO mas SEM resíduo
    ]

    bp_autority = [
        ["ID_USER", "NOME"],
        # Pessoa 80 não está aqui
    ]

    bp_algoritimo = [
        ["ID_USER", "NOME"],
        # Pessoa 80 não está aqui
    ]

    plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

    # NÃO deve estar em pessoas_remocao (sem resíduo)
    assert len(plano.pessoas_remocao) == 0, f"Pessoa sem resíduo não deve ser removida"


def test_multiplos_inativo_detectados():
    """Múltiplas pessoas INATIVO=TRUE com resíduo devem todas ser detectadas."""

    bp_service = [
        ["ID_USER", "NOME", "D. MINISTROS", "DEPARTAMENTOS", "BP AUTORITY", "INATIVO"],
        ["1", "Aline", "FALSE", "", "TRUE", "TRUE"],
        ["2", "Elizabette", "FALSE", "", "TRUE", "TRUE"],
        ["3", "Ativo", "FALSE", "", "", "FALSE"],  # Este não deve estar
    ]

    bp_autority = [
        ["ID_USER", "NOME"],
        ["1", "Aline"],
        ["2", "Elizabette"],
    ]

    bp_algoritimo = [
        ["ID_USER", "NOME"],
    ]

    plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

    # Deve ter 2 para remoção (Aline e Elizabette)
    assert len(plano.pessoas_remocao) == 2, f"Esperava 2 para remocao, obteve {len(plano.pessoas_remocao)}"

    ids = {p.id_user for p in plano.pessoas_remocao}
    assert ids == {"1", "2"}
