"""Testes de cache e invalidação em SpreadsheetGuard."""

import pytest
from unittest.mock import Mock, patch
from gspread.exceptions import APIError

from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


class TestSheetsCacheInvalidation:
    """Validação de cache e invalidação em todas as operações de escrita."""

    def test_cache_hit_on_second_read(self):
        """Segunda leitura da mesma sheet usa cache."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["ID"], ["1"]]}
        guard._worksheet_objects = {}
        guard.metrics = {'cache_hits': 0, 'by_sheet': {}}

        result = guard.read_worksheet("BP SERVICE", force_refresh=False)

        assert result == [["ID"], ["1"]]
        assert guard.metrics['cache_hits'] == 1

    def test_force_refresh_bypasses_cache(self):
        """force_refresh=True ignora cache, relê da API."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["OLD"]]}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'force_refreshes': 0, 'by_sheet': {}}
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

    def test_cache_invalidation_deletes_from_cache(self):
        """_invalidate_cache() remove sheet do cache."""
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

        # BP SERVICE removido, BP AUTORITY preservado
        assert "BP SERVICE" not in guard._worksheet_cache
        assert "BP AUTORITY" in guard._worksheet_cache

    def test_delete_rows_invalidates_cache(self):
        """delete_rows() invalida cache automaticamente."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP AUTORITY": [["ID"], ["122"]]}
        guard._worksheet_objects = {"BP AUTORITY": Mock()}
        guard.metrics = {'writes': 0, 'by_sheet': {}}
        guard.writable_original_titles = {"BP AUTORITY"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        # Chamar delete_rows
        guard.delete_rows("BP AUTORITY", [2])

        # Cache deve estar vazio
        assert "BP AUTORITY" not in guard._worksheet_cache
        assert guard.metrics['writes'] == 1

    def test_batch_update_invalidates_cache(self):
        """batch_update_cells() invalida cache."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP SERVICE": [["OLD"]]}
        guard._worksheet_objects = {"BP SERVICE": Mock()}
        guard.metrics = {'writes': 0, 'by_sheet': {}}
        guard.writable_original_titles = {"BP SERVICE"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        guard.batch_update_cells("BP SERVICE", [(2, 1, "NEW")])

        assert "BP SERVICE" not in guard._worksheet_cache
        assert guard.metrics['writes'] == 1

    def test_transactional_delete_then_force_refresh(self):
        """Após delete, force_refresh relê dados novos da API."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {"BP ALGORITIMO": [["ID"], ["122"]]}
        guard._worksheet_objects = {"BP ALGORITIMO": Mock()}
        guard.metrics = {'api_reads': 0, 'force_refreshes': 0, 'writes': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 1
        guard.writable_original_titles = {"BP ALGORITIMO"}

        mock_ws = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        guard.spreadsheet = mock_spreadsheet

        # 1. Delete invalida cache
        guard.delete_rows("BP ALGORITIMO", [2])
        assert "BP ALGORITIMO" not in guard._worksheet_cache

        # 2. force_refresh relê da API
        mock_ws.get_all_values.return_value = [["ID"]]
        result = guard.read_worksheet("BP ALGORITIMO", force_refresh=True)

        assert result == [["ID"]]
        assert guard.metrics['api_reads'] == 1
        assert guard.metrics['force_refreshes'] == 1

    def test_retry_429_succeeds_after_backoff(self):
        """Retry 429 com backoff exponencial."""
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._worksheet_objects = {}
        guard.metrics = {'api_reads': 0, 'retries': 0, 'by_sheet': {}}
        guard.max_retries = 3
        guard.backoff_base = 1

        mock_ws = Mock()
        mock_ws.get_all_values.return_value = [["OK"]]

        call_count = [0]
        def side_effect(title):
            call_count[0] += 1
            if call_count[0] == 1:  # Primeira tentativa falha
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
        assert guard.metrics['api_reads'] == 1

    def test_non_429_error_fails_immediately(self):
        """Erro não-429 falha imediatamente, sem retry."""
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

        with pytest.raises(APIError) as exc_info:
            guard.read_worksheet("BP SERVICE")

        assert exc_info.value.code == 403
        assert guard.metrics['retries'] == 0
