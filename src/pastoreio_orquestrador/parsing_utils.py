"""Funcoes utilitarias de parsing/data, equivalentes as do Apps Script original
(parseBool, fmtDatePT, weekOfMonth, monthKey, isLastOccurrenceOfMonth,
isValidPreferredWeek, diffDays)."""

from __future__ import annotations

import math
from calendar import monthrange
from datetime import date, datetime

VALORES_VERDADEIROS = {"true", "1", "sim", "yes", "y", "x"}


def parse_bool(valor: object) -> bool:
    if valor is None:
        return False
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    return texto in VALORES_VERDADEIROS


def parse_int(valor: object, default: int = 0) -> int:
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        return default
    try:
        return int(float(texto.replace(",", ".")))
    except ValueError:
        # Colunas como ALOCAÇÃO EXTRA sao usadas tanto como quantidade
        # numerica (ex.: "1") quanto como checkbox booleano (ex.: "TRUE") --
        # sem isso, um valor "TRUE" seria descartado silenciosamente para 0.
        return 1 if parse_bool(valor) else default


def parse_date_ddmmyyyy(texto: str) -> date | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date_pt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def week_of_month(d: date) -> int:
    """1..5, igual a Math.ceil(dia/7) do script original."""
    return math.ceil(d.day / 7)


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def is_last_occurrence_of_month(d: date) -> bool:
    ultimo_dia_do_mes = monthrange(d.year, d.month)[1]
    return (ultimo_dia_do_mes - d.day) < 7


def is_valid_preferred_week(semana_preferencial: int, d: date) -> bool:
    """sem0 == 0 -> sem preferencia (sempre valido).
    sem0 == 5 -> exige ultima ocorrencia do mes.
    Caso contrario, exige week_of_month(d) == sem0."""
    if semana_preferencial == 0:
        return True
    if semana_preferencial == 5:
        return is_last_occurrence_of_month(d)
    return week_of_month(d) == semana_preferencial


def diff_days(d1: date, d2: date) -> int:
    return abs((d2 - d1).days)
