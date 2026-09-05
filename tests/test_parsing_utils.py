from datetime import date

from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month,
    is_valid_preferred_week,
    month_key,
    parse_bool,
    parse_date_ddmmyyyy,
    week_of_month,
)


def test_parse_bool_variacoes():
    for v in ["true", "TRUE", "1", "sim", "SIM", "yes", "y", "x", "X"]:
        assert parse_bool(v) is True
    for v in ["false", "0", "nao", "", None]:
        assert parse_bool(v) is False


def test_week_of_month():
    assert week_of_month(date(2026, 1, 1)) == 1
    assert week_of_month(date(2026, 1, 7)) == 1
    assert week_of_month(date(2026, 1, 8)) == 2
    assert week_of_month(date(2026, 1, 31)) == 5


def test_month_key():
    assert month_key(date(2026, 3, 15)) == "2026-03"


def test_is_last_occurrence_of_month_janeiro_2026():
    # Janeiro/2026 tem 31 dias. Ultima quarta-feira e dia 28 (< 7 dias do fim).
    assert is_last_occurrence_of_month(date(2026, 1, 28)) is True
    assert is_last_occurrence_of_month(date(2026, 1, 21)) is False


def test_is_valid_preferred_week():
    d = date(2026, 1, 7)  # semana 1
    assert is_valid_preferred_week(0, d) is True
    assert is_valid_preferred_week(1, d) is True
    assert is_valid_preferred_week(2, d) is False

    ultima_quarta = date(2026, 1, 28)
    assert is_valid_preferred_week(5, ultima_quarta) is True
    assert is_valid_preferred_week(5, date(2026, 1, 7)) is False


def test_parse_date_ddmmyyyy():
    assert parse_date_ddmmyyyy("07/01/2026") == date(2026, 1, 7)
    assert parse_date_ddmmyyyy("") is None
    assert parse_date_ddmmyyyy("data invalida") is None
