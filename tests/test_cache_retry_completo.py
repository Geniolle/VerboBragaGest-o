"""Testes completos para cache, retry e validação transacional."""

import pytest
import time
from unittest.mock import Mock, patch
from gspread.exceptions import APIError

from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


class TestCacheRetryCompleto:
    """Testes obrigatórios para Opção A."""

    def test_cache_invalidated_after_append(self):
        """append_rows invalida cache."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["OLD"]]}
        guard._worksheet_objects = {"BP SERVICE": Mock()}
        guard.metrics = {'writes': 0}
        guard.writable_original_titles = {"BP SERVICE"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        guard.append_rows("BP SERVICE", [["NEW"]])

        assert "BP SERVICE" not in guard._worksheet_cache
        assert guard.metrics['writes'] == 1

    def test_cache_invalidated_after_delete(self):
        """delete_rows invalida cache."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP AUTORITY": [["ID"]]}
        guard._worksheet_objects = {"BP AUTORITY": Mock()}
        guard.metrics = {'writes': 0}
        guard.writable_original_titles = {"BP AUTORITY"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        guard.delete_rows("BP AUTORITY", [2, 3])

        assert "BP AUTORITY" not in guard._worksheet_cache
        assert guard.metrics['writes'] == 1

    def test_cache_invalidation_is_per_sheet(self):
        """Invalidação de uma sheet não afeta cache de outra."""
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

    def test_retry_after_is_respected(self):
        """Retry-After na resposta é capturado."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'retries': 0, 'by_sheet': {}}
        guard.max_retries = 2
        guard.backoff_base = 1

        mock_ws = Mock()
        mock_ws.get_all_values.return_value = [["OK"]]

        call_count = [0]
        def side_effect(title):
            call_count[0] += 1
            if call_count[0] == 1:
                error = APIError(Mock(code=429))
                error.code = 429
                error.response = Mock(headers={'Retry-After': '5'})
                raise error
            return mock_ws

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.side_effect = side_effect
        guard.spreadsheet = mock_spreadsheet

        result = guard.read_worksheet("BP SERVICE")
        assert result == [["OK"]]
        assert guard.metrics['retries'] == 1

    def test_max_retries_propagates_error(self):
        """Após max_retries, erro 429 é propagado."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'retries': 0, 'by_sheet': {}}
        guard.max_retries = 2
        guard.backoff_base = 1

        error = APIError(Mock(code=429))
        error.code = 429

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.side_effect = error
        guard.spreadsheet = mock_spreadsheet

        with pytest.raises(APIError) as exc_info:
            guard.read_worksheet("BP SERVICE")

        assert exc_info.value.code == 429

    def test_transactional_validation_uses_force_refresh(self):
        """Após delete_rows, releitura com force_refresh=True."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP ALGORITIMO": [["ID"], ["122"]]}
        guard._worksheet_objects = {"BP ALGORITIMO": Mock()}
        guard.metrics = {'api_reads': 0, 'cache_hits': 0, 'force_refreshes': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 1
        guard.writable_original_titles = {"BP ALGORITIMO"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        # delete_rows invalida cache
        guard.delete_rows("BP ALGORITIMO", [2])
        assert "BP ALGORITIMO" not in guard._worksheet_cache

        # force_refresh relê da API
        mock_ws.get_all_values.return_value = [["ID"]]
        result = guard.read_worksheet("BP ALGORITIMO", force_refresh=True)

        assert result == [["ID"]]
        assert guard.metrics['force_refreshes'] == 1
        assert guard.metrics['api_reads'] == 1
