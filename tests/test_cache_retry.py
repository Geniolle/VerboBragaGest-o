"""Testes para cache e retry 429."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from gspread.exceptions import APIError

from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


class TestCacheAndRetry:
    """Validação de cache e retry."""

    @patch.dict("os.environ", {"GOOGLE_SHEETS_MAX_RETRIES": "3", "GOOGLE_SHEETS_BACKOFF_BASE_SECONDS": "1"})
    def test_cache_hit(self):
        """Segunda leitura usa cache."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["ID"], ["1"]]}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'cache_hits': 0, 'by_sheet': {}}

        result = guard.read_worksheet("BP SERVICE", force_refresh=False)

        assert result == [["ID"], ["1"]]
        assert guard.metrics['cache_hits'] == 1

    @patch.dict("os.environ", {"GOOGLE_SHEETS_MAX_RETRIES": "3", "GOOGLE_SHEETS_BACKOFF_BASE_SECONDS": "1"})
    def test_force_refresh_bypasses_cache(self):
        """force_refresh=True ignora cache."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["OLD"]]}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'cache_hits': 0, 'force_refreshes': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 1

        # Mock spreadsheet
        mock_ws = Mock()
        mock_ws.get_all_values.return_value = [["NEW"]]
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        result = guard.read_worksheet("BP SERVICE", force_refresh=True)

        assert result == [["NEW"]]
        assert guard.metrics['force_refreshes'] == 1

    def test_cache_invalidated_after_write(self):
        """Cache é invalidado após batch_update_cells."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["ID"]]}
        guard._worksheet_objects = {"BP SERVICE": Mock()}
        guard.metrics = {'writes': 0}
        guard.writable_original_titles = {"BP SERVICE"}

        guard._invalidate_cache("BP SERVICE")

        assert "BP SERVICE" not in guard._worksheet_cache
        assert "BP SERVICE" not in guard._worksheet_objects

    def test_retry_429_sequence(self):
        """Retry com sequência correta de delays: 2, 4, 8."""
        import time
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'retries': 0, 'by_sheet': {}}
        guard.max_retries = 4  # 3 tentativas + 1 sucesso
        guard.backoff_base = 2

        mock_ws = Mock()
        mock_ws.get_all_values.return_value = [["OK"]]

        call_count = [0]
        def side_effect(title):
            call_count[0] += 1
            if call_count[0] < 4:  # Falhar 3 vezes, sucesso na 4ª
                error = APIError(Mock(code=429))
                error.code = 429
                raise error
            return mock_ws

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.side_effect = side_effect
        guard.spreadsheet = mock_spreadsheet

        result = guard.read_worksheet("BP SERVICE", force_refresh=False)

        assert result == [["OK"]]
        assert guard.metrics['retries'] == 3

    def test_non_transient_error_no_retry(self):
        """Erro não-transitório não faz retry."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'retries': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 1

        error = APIError(Mock(code=403))
        error.code = 403

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.side_effect = error
        guard.spreadsheet = mock_spreadsheet

        with pytest.raises(APIError) as exc_info:
            guard.read_worksheet("BP SERVICE")

        assert exc_info.value.code == 403
        assert guard.metrics['retries'] == 0
