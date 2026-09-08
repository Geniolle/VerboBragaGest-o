# -*- coding: utf-8 -*-
"""Limpa (apaga) a coluna MINISTRO da CLAUDE_AppAnualGlobal para os 9
domingos da Ronda 2 (D. MINISTROS / MINISTRO / DOMINGO), de 2026-12-06 a
2027-01-31, ja identificados como incorretos (rodizio de CEIA ALTERNADA e
PREENCHIMENTO DE LACUNA nao considerava o historico da Ronda 1). Depois de
limpar, rode preencher_claude_appanualglobal_domingo.py de novo -- agora ele
recalcula a Ronda 2 fazendo o replay da Ronda 1 antes, com o rodizio correto.
"""
from __future__ import annotations

from datetime import date

from pastoreio_orquestrador.carregamento import build_header_index, get
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.parsing_utils import parse_date_ddmmyyyy
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

AGENDA_TITLE = "CLAUDE_AppAnualGlobal"
DATAS_RONDA2 = {
    date(2026, 12, 6), date(2026, 12, 13), date(2026, 12, 20), date(2026, 12, 27),
    date(2027, 1, 3), date(2027, 1, 10), date(2027, 1, 17), date(2027, 1, 24), date(2027, 1, 31),
}

settings = load_settings()
guard = SpreadsheetGuard(settings)
agenda_raw = guard.read_worksheet(AGENDA_TITLE)
idx = build_header_index(agenda_raw[0])
col_ministro = idx["MINISTRO"]

limpos = []
for row_i, row in enumerate(agenda_raw[1:], start=1):
    dia = get(row, idx, "DIA DA SEMANA").strip().upper()
    if "DOMINGO" not in dia:
        continue
    d = parse_date_ddmmyyyy(get(row, idx, "DATA").strip())
    if d not in DATAS_RONDA2:
        continue
    ministro = get(row, idx, "MINISTRO").strip()
    if not ministro:
        continue
    linha_sheet = row_i + 1
    guard.update_cell(AGENDA_TITLE, linha_sheet, col_ministro + 1, "")
    limpos.append((d, ministro))

print(f"Celulas limpas (Ronda 2, coluna MINISTRO): {len(limpos)}")
for d, m in sorted(limpos):
    print(f"  {d} (era {m}) -> vazio")
