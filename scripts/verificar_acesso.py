"""Verifica que o orquestrador consegue aceder a spreadsheet configurada
no .env, sem alterar nada. Lista as abas encontradas.

Uso:
    uv run python scripts/verificar_acesso.py
"""

from __future__ import annotations

import sys

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.diagnostico import ABAS_ESPERADAS, diagnosticar
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard, service_account_email


def main() -> None:
    settings = load_settings()
    print(f"Service account: {service_account_email(settings)}")
    print(f"Spreadsheet ID: {settings.spreadsheet_id}")

    guard = SpreadsheetGuard(settings)
    print(f"\nSpreadsheet aberta com sucesso: '{guard.spreadsheet.title}'")

    relatorio = diagnosticar(guard)

    print(f"Abas encontradas ({len(relatorio.abas_encontradas)}):")
    for t in relatorio.abas_encontradas:
        print(f"  - {t}")

    print("\nVerificacao de abas esperadas pelo algoritmo:")
    for esperada in ABAS_ESPERADAS:
        status = "OK" if esperada not in relatorio.abas_em_falta else "NAO ENCONTRADA"
        print(f"  - {esperada}: {status}")

    if relatorio.colunas_em_falta_por_aba:
        print("\nColunas esperadas que nao foram encontradas:")
        for aba, colunas in relatorio.colunas_em_falta_por_aba.items():
            print(f"  - {aba}: {', '.join(colunas)}")
    else:
        print("\nTodas as colunas esperadas foram encontradas nas abas presentes.")

    if not relatorio.ok:
        print("\nDiagnostico encontrou divergencias (ver acima). Corrija antes de rodar o motor.")
        sys.exit(1)

    print("\nDiagnostico OK: estrutura da spreadsheet condiz com o que o codigo espera.")


if __name__ == "__main__":
    main()
