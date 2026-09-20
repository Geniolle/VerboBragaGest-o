from datetime import date
import importlib.util
from pathlib import Path

from pastoreio_orquestrador.carregamento import build_header_index


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "preencher_claude_appanualglobal_quarta.py"
spec = importlib.util.spec_from_file_location("preencher_claude_appanualglobal_quarta", SCRIPT_PATH)
quarta_script = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(quarta_script)


def test_quarta_coleta_apenas_datas_a_partir_do_corte_rotacional():
    agenda = [
        ["DATA", "DIA DA SEMANA", "MINISTRO"],
        ["30/09/2026", "QUARTA-FEIRA", "Pessoa Antiga"],
        ["04/10/2026", "DOMINGO", "Pessoa Domingo"],
        ["07/10/2026", "QUARTA-FEIRA", ""],
        ["14/10/2026", "QUARTA-FEIRA", "Pessoa Nova"],
    ]
    idx = build_header_index(agenda[0])

    linhas, ignoradas = quarta_script.coletar_linhas_agenda_quarta(
        agenda,
        idx,
        date(2026, 10, 1),
    )

    assert ignoradas == 1
    assert [(data_slot, valor) for _row, data_slot, valor in linhas] == [
        (date(2026, 10, 7), ""),
        (date(2026, 10, 14), "Pessoa Nova"),
    ]
