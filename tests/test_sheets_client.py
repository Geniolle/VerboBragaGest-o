import pytest

from pastoreio_orquestrador.sheets_client import (
    SpreadsheetGuard,
    TentativaDeAlteracaoOriginalError,
)


def _guard(writable_original_titles=None) -> SpreadsheetGuard:
    guard = SpreadsheetGuard.__new__(SpreadsheetGuard)
    guard.writable_original_titles = set(writable_original_titles or set())
    return guard


def test_guard_permite_claude_por_padrao():
    _guard()._assert_can_write("CLAUDE_AppAnualGlobal")


def test_guard_bloqueia_produtivo_sem_allowlist():
    with pytest.raises(TentativaDeAlteracaoOriginalError):
        _guard()._assert_can_write("AppAnualGlobal")


def test_guard_permite_produtivo_com_allowlist_explicita():
    _guard({"AppAnualGlobal"})._assert_can_write("AppAnualGlobal")


def test_guard_nao_permite_delete_produtivo_mesmo_com_allowlist():
    guard = _guard({"AppAnualGlobal"})

    with pytest.raises(TentativaDeAlteracaoOriginalError):
        guard.delete_worksheet("AppAnualGlobal")
