"""Simula, sem escrever em Sheets, o cursor persistido de DOMINGO.

Le CLAUDE_AppAnualGlobal + CLAUDE_LOG_AUDITORIA e mostra qual foi a ultima
alocacao normal que consumiu a hierarquia de D. MINISTROS/MINISTRO/DOMINGO.
"""

from __future__ import annotations

from pastoreio_orquestrador.auditoria import (
    NOME_ABA_AUDITORIA,
    resolver_ultimo_cursor_hierarquia,
)
from pastoreio_orquestrador.carregamento import carregar_regras_colaboradores
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

DEPARTAMENTO, FUNCAO, DIA = "D. MINISTROS", "MINISTRO", "DOMINGO"
AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
BP_ALGORITMO_TITLE = "CLAUDE_BP ALGORITIMO"
COL_NOME = "MINISTRO"


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)
    titulos = set(guard.list_worksheet_titles())

    agenda_raw = guard.read_worksheet(AGENDA_TITLE)
    auditoria_raw = guard.read_worksheet(NOME_ABA_AUDITORIA) if NOME_ABA_AUDITORIA in titulos else []
    regras = carregar_regras_colaboradores(guard.read_worksheet(BP_ALGORITMO_TITLE))

    grupo = []
    vistos: set[str] = set()
    for regra in regras:
        nome_key = regra.nome.strip().upper()
        if (
            regra.departamento == DEPARTAMENTO
            and regra.funcao == FUNCAO
            and DIA in regra.dia_da_semana
            and nome_key not in vistos
        ):
            grupo.append(regra)
            vistos.add(nome_key)

    cursor = resolver_ultimo_cursor_hierarquia(
        agenda_raw,
        auditoria_raw,
        grupo,
        DEPARTAMENTO,
        FUNCAO,
        DIA,
        COL_NOME,
    )

    print("SIMULACAO CURSOR HIERARQUIA DOMINGO")
    print(f"Registros validos que consumiram hierarquia: {len(cursor.registros_validos)}")
    print(f"Ultima alocacao normal que consumiu a hierarquia: {cursor.ancora or '(nenhuma)'}")
    print(
        "Posicao atual da ancora: "
        f"{cursor.prioridade_ancora_atual if cursor.prioridade_ancora_atual is not None else '(nenhuma)'}"
    )
    print(
        "Proximo candidato inicial: "
        f"{cursor.proximo_candidato.nome if cursor.proximo_candidato else '(nenhum)'}"
    )
    if cursor.diagnosticos:
        print("Diagnosticos:")
        for diagnostico in cursor.diagnosticos:
            print(f"- {diagnostico}")


if __name__ == "__main__":
    main()
