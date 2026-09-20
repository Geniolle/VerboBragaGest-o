"""Politicas de historico rotacional do novo motor."""

from __future__ import annotations

from datetime import date


def dentro_do_historico_do_novo_motor(data_slot: date, data_corte_historico: date | None) -> bool:
    """Indica se uma data participa da reconstrução rotacional.

    A data de corte separa estado rotacional legado de fatos reais da agenda.
    Chamadores devem aplicar esta politica somente a cursor, CEIA, replay,
    cotas e historicos do motor, nunca a filtros factuais como descanso
    cruzado ou indisponibilidades.
    """
    return data_corte_historico is None or data_slot >= data_corte_historico
