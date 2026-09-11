import pytest

from pastoreio_orquestrador.sincronizacao_bp_service import (
    VinculoElegivel,
    calcular_plano_sincronizacao,
    detectar_colunas_departamento,
    montar_linhas_para_inserir,
    selecionar_vinculos_elegiveis,
)

HEADER_BP_SERVICE = [
    "ID_USER", "NOME", "EMAIL", "D. MINISTROS", "D. CENTRO DE CURA",
    "DEPARTAMENTOS", "INATIVO", "TYPE",
]

HEADER_BP_ALGORITIMO = ["ID_TABLE", "NOME", "DEPARTAMENTO", "EMAIL LIDER", "ATIVO"]


def _linha_bp_service(nome, id_user="1", ministros="true", centro_cura="", departamentos="true", inativo="", type_=""):
    return [id_user, nome, "", ministros, centro_cura, departamentos, inativo, type_]


def test_detectar_colunas_departamento_ignora_centro_de_cura():
    colunas = detectar_colunas_departamento(HEADER_BP_SERVICE)
    assert colunas == ["D. MINISTROS"]


def test_selecionar_vinculos_elegiveis_caso_basico():
    valores = [HEADER_BP_SERVICE, _linha_bp_service("Ana Lima")]
    vinculos = selecionar_vinculos_elegiveis(valores)
    assert len(vinculos) == 1
    assert vinculos[0] == VinculoElegivel(nome="Ana Lima", departamento="D. MINISTROS", id_user="1", email_lider="")


def test_selecionar_vinculos_elegiveis_ignora_inativo():
    valores = [HEADER_BP_SERVICE, _linha_bp_service("Ana Lima", inativo="true")]
    assert selecionar_vinculos_elegiveis(valores) == []


def test_selecionar_vinculos_elegiveis_ignora_sem_flag_departamentos_geral():
    valores = [HEADER_BP_SERVICE, _linha_bp_service("Ana Lima", departamentos="")]
    assert selecionar_vinculos_elegiveis(valores) == []


def test_selecionar_vinculos_elegiveis_ignora_conta_de_sistema():
    valores = [HEADER_BP_SERVICE, _linha_bp_service("Robo Sistema", type_="SY")]
    assert selecionar_vinculos_elegiveis(valores) == []


def test_selecionar_vinculos_elegiveis_ignora_departamento_nao_marcado():
    valores = [HEADER_BP_SERVICE, _linha_bp_service("Ana Lima", ministros="")]
    assert selecionar_vinculos_elegiveis(valores) == []


def test_selecionar_vinculos_elegiveis_usa_mapa_de_email_por_departamento():
    valores = [HEADER_BP_SERVICE, _linha_bp_service("Ana Lima")]
    vinculos = selecionar_vinculos_elegiveis(valores, {"D. MINISTROS": "lider@exemplo.com"})
    assert vinculos[0].email_lider == "lider@exemplo.com"


def test_plano_insere_vinculo_novo_com_id_table_igual_ao_id_user():
    vinculos = [VinculoElegivel("Ana Lima", "D. MINISTROS", id_user="7", email_lider="")]
    plano = calcular_plano_sincronizacao(vinculos, [HEADER_BP_ALGORITIMO])
    assert plano.inserir == vinculos
    assert plano.atualizacoes == []

    linhas = montar_linhas_para_inserir(HEADER_BP_ALGORITIMO, plano.inserir)
    assert linhas == [["7", "Ana Lima", "D. MINISTROS", "", "TRUE"]]


def test_plano_nao_insere_vinculo_ja_existente():
    vinculos = [VinculoElegivel("Ana Lima", "D. MINISTROS", id_user="7", email_lider="")]
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["7", "Ana Lima", "D. MINISTROS", "lider@exemplo.com", "TRUE"]]
    plano = calcular_plano_sincronizacao(vinculos, bp_algoritimo)
    assert plano.vazio


def test_plano_corrige_email_lider_vazio():
    vinculos = [VinculoElegivel("Ana Lima", "D. MINISTROS", id_user="7", email_lider="lider@exemplo.com")]
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["7", "Ana Lima", "D. MINISTROS", "", "TRUE"]]
    plano = calcular_plano_sincronizacao(vinculos, bp_algoritimo)
    assert len(plano.atualizacoes) == 1
    upd = plano.atualizacoes[0]
    assert (upd.linha_bp_algoritimo, upd.coluna, upd.valor) == (2, "EMAIL LIDER", "lider@exemplo.com")


def test_plano_nao_sobrescreve_email_lider_ja_preenchido():
    vinculos = [VinculoElegivel("Ana Lima", "D. MINISTROS", id_user="7", email_lider="novo@exemplo.com")]
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["7", "Ana Lima", "D. MINISTROS", "antigo@exemplo.com", "TRUE"]]
    plano = calcular_plano_sincronizacao(vinculos, bp_algoritimo)
    assert plano.vazio


def test_plano_corrige_id_table_vazio_com_id_user():
    vinculos = [VinculoElegivel("Ana Lima", "D. MINISTROS", id_user="7", email_lider="")]
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["", "Ana Lima", "D. MINISTROS", "", "TRUE"]]
    plano = calcular_plano_sincronizacao(vinculos, bp_algoritimo)
    upd = next(a for a in plano.atualizacoes if a.coluna == "ID_TABLE")
    assert (upd.linha_bp_algoritimo, upd.valor) == (2, "7")


def test_plano_desativa_vinculo_que_nao_esta_mais_na_selecao():
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["7", "Ana Lima", "D. MINISTROS", "", "TRUE"]]
    plano = calcular_plano_sincronizacao([], bp_algoritimo)
    assert len(plano.atualizacoes) == 1
    upd = plano.atualizacoes[0]
    assert (upd.linha_bp_algoritimo, upd.coluna, upd.valor) == (2, "ATIVO", "FALSE")
    assert plano.inserir == []


def test_plano_nao_mexe_em_vinculo_ja_inativo_que_continua_fora_da_selecao():
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["7", "Ana Lima", "D. MINISTROS", "", "FALSE"]]
    plano = calcular_plano_sincronizacao([], bp_algoritimo)
    assert plano.vazio


def test_plano_reativa_vinculo_que_voltou_a_bater_na_selecao():
    vinculos = [VinculoElegivel("Ana Lima", "D. MINISTROS", id_user="7", email_lider="")]
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["7", "Ana Lima", "D. MINISTROS", "", "FALSE"]]
    plano = calcular_plano_sincronizacao(vinculos, bp_algoritimo)
    assert len(plano.atualizacoes) == 1
    upd = plano.atualizacoes[0]
    assert (upd.linha_bp_algoritimo, upd.coluna, upd.valor) == (2, "ATIVO", "TRUE")
    assert plano.inserir == []


def test_plano_nunca_apaga_linha_so_marca_ativo_false():
    """Regressao explicita da regra de negocio: a reversao nunca remove uma
    linha de BP ALGORITIMO, so alterna a coluna ATIVO."""
    bp_algoritimo = [HEADER_BP_ALGORITIMO, ["7", "Ana Lima", "D. MINISTROS", "", "TRUE"]]
    plano = calcular_plano_sincronizacao([], bp_algoritimo)
    assert plano.inserir == []
    assert all(a.coluna == "ATIVO" for a in plano.atualizacoes)


def test_calcular_plano_levanta_erro_com_cabecalho_incompleto():
    with pytest.raises(ValueError):
        calcular_plano_sincronizacao([], [["NOME", "DEPARTAMENTO"]])
