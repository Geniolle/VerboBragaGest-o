from unittest.mock import Mock

from scripts.Colaborador.sincronizar_id_manager import (
    ManagerEntry,
    PlanoSincronizacaoIdManager,
    aplicar_plano,
    valor_texto_para_sheet,
)


def test_valor_texto_para_sheet_preserva_telefone_com_prefixo_mais():
    assert valor_texto_para_sheet("+351999999999") == "'+351999999999"
    assert valor_texto_para_sheet("351999999999") == "351999999999"


def test_aplicar_plano_escreve_telefone_internacional_como_texto():
    guard = Mock()
    id_manager = [["DEPARTAMENTOS", "NOME", "TELEFONE", "EMAIL"]]
    entry = ManagerEntry(
        id_user="1",
        nome="Verbinho Braga",
        telefone="+351999999999",
        email="verbodavidabraga@gmail.com",
        departamento="D. COMUNICACAO",
        manager_col="MANAGER_COMUNICACAO",
        linha_authority=20,
    )
    plano = PlanoSincronizacaoIdManager(atualizar=[(20, entry)])

    aplicar_plano(guard, id_manager, plano)

    guard.batch_update_cells.assert_called_once_with(
        "ID_MANAGER",
        [
            (20, 3, "'+351999999999"),
            (20, 4, "verbodavidabraga@gmail.com"),
        ],
    )
