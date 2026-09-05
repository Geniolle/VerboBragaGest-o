from pastoreio_orquestrador.diagnostico import ABAS_ESPERADAS, diagnosticar


class GuardFalso:
    """Stub de SpreadsheetGuard para testar diagnosticar() sem rede."""

    def __init__(self, abas: dict[str, list[list[str]]]):
        self._abas = abas

    def list_worksheet_titles(self) -> list[str]:
        return list(self._abas.keys())

    def read_worksheet(self, title: str) -> list[list[str]]:
        return self._abas[title]


def _abas_completas_e_validas() -> dict[str, list[list[str]]]:
    return {
        "BP ALGORITIMO": [
            ["ID_TABLE", "NOME", "DEPARTAMENTO", "FUNÇÃO", "DIA DA SEMANA", "ATIVO"]
        ],
        "AppAnualGlobal": [["DIA DA SEMANA", "DATA", "TEMA"]],
        "Excluse": [["COLUNAS"]],
        "CONF_ALGORITIMO": [["PROCESSO", "VALOR"]],
        "Livros": [["DIA DA SEMANA", "TEMA", "CLASSIFICAÇÃO"]],
        "BP LOG": [["DEPARTAMENTO", "PROCESSO", "NOME", "DISPONIBILIDADE"]],
        "LOG ALGORITIMO": [["Data de Execução", "Alocações (JSON)", "Status"]],
    }


def test_diagnosticar_estrutura_valida_reporta_ok():
    guard = GuardFalso(_abas_completas_e_validas())
    relatorio = diagnosticar(guard)

    assert relatorio.ok
    assert relatorio.abas_em_falta == []
    assert relatorio.colunas_em_falta_por_aba == {}
    assert set(relatorio.abas_encontradas) == set(ABAS_ESPERADAS)


def test_diagnosticar_aba_em_falta():
    abas = _abas_completas_e_validas()
    del abas["BP LOG"]
    relatorio = diagnosticar(GuardFalso(abas))

    assert not relatorio.ok
    assert relatorio.abas_em_falta == ["BP LOG"]


def test_diagnosticar_coluna_em_falta():
    abas = _abas_completas_e_validas()
    abas["AppAnualGlobal"] = [["DIA DA SEMANA", "DATA"]]  # falta TEMA
    relatorio = diagnosticar(GuardFalso(abas))

    assert not relatorio.ok
    assert relatorio.colunas_em_falta_por_aba == {"AppAnualGlobal": ["TEMA"]}


def test_diagnosticar_aba_vazia_reporta_todas_colunas_em_falta():
    abas = _abas_completas_e_validas()
    abas["Excluse"] = []
    relatorio = diagnosticar(GuardFalso(abas))

    assert not relatorio.ok
    assert relatorio.colunas_em_falta_por_aba["Excluse"] == ["COLUNAS"]
