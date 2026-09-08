# -*- coding: utf-8 -*-
"""Limpa (apaga) TODA a coluna MINISTRO preenchida para QUARTA-FEIRA em
CLAUDE_AppAnualGlobal (D. MINISTROS / MINISTRO / QUARTA-FEIRA) -- Rondas 1 e 2
inteiras (07/10/2026 a 26/05/2027), gravadas por engano em duas execucoes
seguidas antes do filtro de "descanso minimo cruzado" existir (2026-09-08,
pedido do Clayton: "Podes limpar a sheet e voltar a correr"). Depois de
limpar, rode preencher_claude_appanualglobal_quarta.py de novo (uma Ronda por
execucao) para recalcular do zero, agora respeitando o descanso minimo
cruzado com o DOMINGO.
"""
from __future__ import annotations

from pastoreio_orquestrador.carregamento import build_header_index, get
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

AGENDA_TITLE = "CLAUDE_AppAnualGlobal"

settings = load_settings()
guard = SpreadsheetGuard(settings)
agenda_raw = guard.read_worksheet(AGENDA_TITLE)
idx = build_header_index(agenda_raw[0])
col_ministro = idx["MINISTRO"]

limpos = []
for row_i, row in enumerate(agenda_raw[1:], start=1):
    dia = get(row, idx, "DIA DA SEMANA").strip().upper()
    if "QUARTA-FEIRA" not in dia:
        continue
    ministro = get(row, idx, "MINISTRO").strip()
    if not ministro:
        continue
    data = get(row, idx, "DATA").strip()
    linha_sheet = row_i + 1
    guard.update_cell(AGENDA_TITLE, linha_sheet, col_ministro + 1, "")
    limpos.append((data, ministro))

print(f"Celulas limpas (QUARTA-FEIRA, coluna MINISTRO): {len(limpos)}")
for data, m in limpos:
    print(f"  {data} (era {m}) -> vazio")
