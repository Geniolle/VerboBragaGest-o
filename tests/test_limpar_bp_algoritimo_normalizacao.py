from scripts.Colaborador.limpar_bp_algoritimo import calcular_plano


def test_departamento_com_acento_corresponde_ao_vinculo_authority():
    bp_autority = [
        ["ID_USER", "NOME", "COLABORADOR_CRIANCAS", "COLABORADOR_COMUNICACAO"],
        ["1", "Ana", "TRUE", "TRUE"],
    ]
    bp_algoritimo = [
        ["ID_USER", "NOME", "DEPARTAMENTO", "ATIVO"],
        ["1", "Ana", "D. CRIANÇAS", "TRUE"],
        ["1", "Ana", "D. COMUNICAÇÃO", "TRUE"],
    ]

    plano = calcular_plano(bp_algoritimo, bp_autority)

    assert plano.remover_sem_autority == []
    assert plano.linhas_ok == 2


def test_remove_vinculo_realmente_ausente_da_authority():
    bp_autority = [
        ["ID_USER", "NOME", "COLABORADOR_CRIANCAS"],
        ["1", "Ana", ""],
    ]
    bp_algoritimo = [
        ["ID_USER", "NOME", "DEPARTAMENTO", "ATIVO"],
        ["1", "Ana", "D. CRIANÇAS", "TRUE"],
    ]

    plano = calcular_plano(bp_algoritimo, bp_autority)

    assert plano.remover_sem_autority == [2]
