from pastoreio_orquestrador.carregamento import (
    carregar_historico_alocacoes,
    carregar_zumbis_prioritarios,
)
from pastoreio_orquestrador.models import RegistroBpLog

LOG_HEADER = [
    "Log ID", "Data de Execução", "Alocações (JSON)", "Status",
    "Notas do Usuário", "Departamento", "Função",
]


def test_carregar_historico_conta_apenas_alocacoes_ativas_da_funcao():
    valores = [
        LOG_HEADER,
        [
            "1", "2026/01/01", '[{"nome":"Ana","funcao":"MINISTRO"},{"nome":"Bia","funcao":"MINISTRO"},{"nome":"Ana","funcao":"CEIA"}]',
            "Ativo", "", "", "",
        ],
        [
            "2", "2026/02/01", '[{"nome":"Ana","funcao":"MINISTRO"}]',
            "", "", "", "",  # Status vazio (nao ativo): nao deve contar
        ],
    ]
    historico = carregar_historico_alocacoes(valores, "MINISTRO")
    assert historico == {"Ana": 1, "Bia": 1}


def test_carregar_historico_sem_json_valido_e_ignorado():
    valores = [LOG_HEADER, ["1", "2026/01/01", "não é json", "Ativo", "", "", ""]]
    assert carregar_historico_alocacoes(valores, "MINISTRO") == {}


def test_carregar_zumbis_prioritarios_filtra_departamento_processo_e_disponibilidade():
    registros = [
        RegistroBpLog("D. MINISTROS", "MINISTRO", "Edna Souza", "07/2026", True, ""),
        RegistroBpLog("D. MINISTROS", "MINISTRO", "Ana Lima", "05/2026", False, "01/01/2026"),
        RegistroBpLog("D. COMUNICAÇÃO", "CEIA", "Aissa Lima", "03/2026", True, ""),
    ]
    zumbis = carregar_zumbis_prioritarios(registros, "D. MINISTROS", "MINISTRO")
    assert zumbis == {"Edna Souza"}
