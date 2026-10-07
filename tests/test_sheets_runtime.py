import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
from pastoreio_orquestrador.sheets_runtime import SharedReadQuotaLimiter, SharedSheetsCache


def test_quota_partilhada_aguarda_janela(monkeypatch):
    clock = {"now": 100.0}
    monkeypatch.setattr("pastoreio_orquestrador.sheets_runtime.time.time", lambda: clock["now"])
    monkeypatch.setattr(
        "pastoreio_orquestrador.sheets_runtime.time.sleep",
        lambda seconds: clock.__setitem__("now", clock["now"] + seconds),
    )
    with TemporaryDirectory(prefix="quota-test-", dir="runtime") as directory:
        state_file = Path(directory) / "quota.json"
        limiter = SharedReadQuotaLimiter(state_file, limit=1, window_seconds=60)
        limiter.acquire()
        limiter.acquire()

        timestamps = json.loads(state_file.read_text())["timestamps"]
        assert len(timestamps) == 1
        assert timestamps[0] >= 160


def test_cache_partilhado_e_invalidacao():
    with TemporaryDirectory(prefix="cache-test-", dir="runtime") as directory:
        cache_a = SharedSheetsCache(Path(directory))
        cache_b = SharedSheetsCache(Path(directory))
        cache_a.save("BP SERVICE", [["ID"], ["1"]])

        assert cache_b.load("BP SERVICE") == [["ID"], ["1"]]
        cache_b.invalidate("BP SERVICE")
        assert cache_a.load("BP SERVICE") is None


def test_prefetch_usa_um_batch_e_preenche_cache():
    with TemporaryDirectory(prefix="prefetch-test-", dir="runtime") as directory:
        guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
        guard._worksheet_cache = {}
        guard._shared_cache = SharedSheetsCache(Path(directory))
        guard._shared_quota_limiter = None
        guard.max_retries = 2
        guard.backoff_base = 1
        guard.quota_retry_min_wait = 0
        guard.metrics = {"api_reads": 0, "retries": 0}
        guard.spreadsheet = Mock()
        guard.spreadsheet.values_batch_get.return_value = {
            "valueRanges": [
                {"values": [["A"], ["1"]]},
                {"values": [["B"], ["2"]]},
            ]
        }

        guard.prefetch_worksheets(["BP SERVICE", "BP AUTORITY"])

        guard.spreadsheet.values_batch_get.assert_called_once()
        assert guard._shared_cache.load("BP SERVICE") == [["A"], ["1"]]
        assert guard._shared_cache.load("BP AUTORITY") == [["B"], ["2"]]
