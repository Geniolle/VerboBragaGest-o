"""Testes finais para cache, retry e validação transacional."""

import pytest
from unittest.mock import Mock
from gspread.exceptions import APIError

from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


class TestCacheFinal:
    """Testes obrigatórios Opção A: cache + retry."""

    def test_append_rows_invalidates_cache(self):
        """append_rows() invalida cache após escrita."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["OLD"]]}
        guard._worksheet_objects = {"BP SERVICE": Mock()}
        guard.metrics = {'writes': 0, 'by_sheet': {}}
        guard.writable_original_titles = {"BP SERVICE"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        guard.append_rows("BP SERVICE", [["NEW"]])
        assert "BP SERVICE" not in guard._worksheet_cache
        assert guard.metrics['writes'] == 1

    def test_delete_rows_invalidates_cache(self):
        """delete_rows() invalida cache."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP AUTORITY": [["ID"]]}
        guard._worksheet_objects = {"BP AUTORITY": Mock()}
        guard.metrics = {'writes': 0, 'by_sheet': {}}
        guard.writable_original_titles = {"BP AUTORITY"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        guard.delete_rows("BP AUTORITY", [2, 3])
        assert "BP AUTORITY" not in guard._worksheet_cache
        assert guard.metrics['writes'] == 1

    def test_cache_per_sheet(self):
        """Cache é isolado por sheet."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {
            "BP SERVICE": [["A"]],
            "BP AUTORITY": [["B"]]
        }
        guard._worksheet_objects = {
            "BP SERVICE": Mock(),
            "BP AUTORITY": Mock()
        }

        guard._invalidate_cache("BP SERVICE")
        assert "BP SERVICE" not in guard._worksheet_cache
        assert "BP AUTORITY" in guard._worksheet_cache

    def test_force_refresh_ignores_cache(self):
        """force_refresh=True ignora cache e relê."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["OLD"]]}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'cache_hits': 0, 'force_refreshes': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 1

        mock_ws = Mock()
        mock_ws.get_all_values.return_value = [["NEW"]]
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        result = guard.read_worksheet("BP SERVICE", force_refresh=True)
        assert result == [["NEW"]]
        assert guard.metrics['force_refreshes'] == 1
        assert guard.metrics['api_reads'] == 1

    def test_retry_429_with_exponential_backoff(self):
        """Retry 429 com backoff exponencial."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'retries': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 2

        mock_ws = Mock()
        mock_ws.get_all_values.return_value = [["OK"]]

        call_count = [0]
        def side_effect(title):
            call_count[0] += 1
            if call_count[0] < 2:  # Falhar 1 vez
                error = APIError(Mock(code=429))
                error.code = 429
                raise error
            return mock_ws

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.side_effect = side_effect
        guard.spreadsheet = mock_spreadsheet

        result = guard.read_worksheet("BP SERVICE")
        assert result == [["OK"]]
        assert guard.metrics['retries'] == 1

    def test_non_429_error_fails_immediately(self):
        """Erro não-429 falha imediatamente sem retry."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._worksheet_objects = {}
        guard.metrics = {'retries': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 1

        error = APIError(Mock(code=403))
        error.code = 403

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.side_effect = error
        guard.spreadsheet = mock_spreadsheet

        with pytest.raises(APIError) as exc:
            guard.read_worksheet("BP SERVICE")
        assert exc.value.code == 403
        assert guard.metrics['retries'] == 0
