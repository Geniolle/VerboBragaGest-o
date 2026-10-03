#!/usr/bin/env python3
"""Verifica disponibilidade de quota do Google Sheets."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

try:
    guard = SpreadsheetGuard(load_settings())
    data = guard.read_worksheet('BP SERVICE')

    print('✅ QUOTA DISPONÍVEL')
    print(f'BP SERVICE lido com sucesso: {len(data)} linhas')
    print(f'API reads: {guard.metrics["api_reads"]}')
    print(f'Cache hits: {guard.metrics["cache_hits"]}')

except Exception as e:
    error_str = str(e)
    print(f'❌ ERRO: {type(e).__name__}')
    if '429' in error_str:
        print('   Quota ainda indisponível (429 - Rate limit)')
    else:
        print(f'   {error_str[:150]}')
