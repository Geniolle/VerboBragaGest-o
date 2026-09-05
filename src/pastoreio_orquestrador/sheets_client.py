"""Cliente de acesso ao Google Sheets com trava de seguranca.

Regra inegociavel deste projeto: o orquestrador nunca apaga nem altera as
abas originais. Qualquer escrita (update de celulas, limpeza, etc.) so e
permitida em abas cujo titulo comece por "CLAUDE_". Abas originais so podem
ser lidas ou duplicadas (nunca apagadas nem sobrescritas).
"""

from __future__ import annotations

import json

import gspread
from google.oauth2.service_account import Credentials

from pastoreio_orquestrador.config import Settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CLAUDE_PREFIX = "CLAUDE_"


class TentativaDeAlteracaoOriginalError(RuntimeError):
    """Levantado quando o codigo tenta escrever/apagar numa aba original."""


def service_account_email(settings: Settings) -> str:
    data = json.loads(settings.service_account_file.read_text(encoding="utf-8"))
    return data["client_email"]


def get_client(settings: Settings) -> gspread.Client:
    creds = Credentials.from_service_account_file(
        str(settings.service_account_file), scopes=SCOPES
    )
    return gspread.authorize(creds)


class SpreadsheetGuard:
    """Wrapper fino sobre gspread.Spreadsheet que bloqueia escrita/delete
    em qualquer aba que nao tenha o prefixo CLAUDE_."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = get_client(settings)
        self.spreadsheet = self.client.open_by_key(settings.spreadsheet_id)

    def list_worksheet_titles(self) -> list[str]:
        return [ws.title for ws in self.spreadsheet.worksheets()]

    def read_worksheet(self, title: str) -> list[list[str]]:
        """Leitura e sempre permitida, mesmo em abas originais."""
        ws = self.spreadsheet.worksheet(title)
        return ws.get_all_values()

    def _assert_is_claude_copy(self, title: str) -> None:
        if not title.startswith(CLAUDE_PREFIX):
            raise TentativaDeAlteracaoOriginalError(
                f"Bloqueado: tentativa de escrever/apagar na aba '{title}'. "
                f"So e permitido escrever em abas com prefixo '{CLAUDE_PREFIX}'."
            )

    def duplicate_sheet_for_testing(self, original_title: str) -> gspread.Worksheet:
        """Duplica uma aba original criando/ substituindo a copia
        CLAUDE_<original_title>. A aba original nunca e tocada."""
        claude_title = f"{CLAUDE_PREFIX}{original_title}"

        existing = {ws.title: ws for ws in self.spreadsheet.worksheets()}
        if claude_title in existing:
            self.spreadsheet.del_worksheet(existing[claude_title])

        original_ws = self.spreadsheet.worksheet(original_title)
        new_ws = self.spreadsheet.duplicate_sheet(
            source_sheet_id=original_ws.id,
            new_sheet_name=claude_title,
        )
        return new_ws

    def update_worksheet(self, title: str, values: list[list]) -> None:
        self._assert_is_claude_copy(title)
        ws = self.spreadsheet.worksheet(title)
        ws.update(values, "A1")

    def update_cell(self, title: str, row: int, col: int, value: str) -> None:
        self._assert_is_claude_copy(title)
        ws = self.spreadsheet.worksheet(title)
        ws.update_cell(row, col, value)

    def append_row(self, title: str, values: list[str]) -> None:
        self._assert_is_claude_copy(title)
        ws = self.spreadsheet.worksheet(title)
        ws.append_row(values)

    def create_worksheet(self, title: str, rows: int = 100, cols: int = 26) -> gspread.Worksheet:
        """Cria uma aba nova (so permitido com prefixo CLAUDE_), apagando
        antes qualquer aba pre-existente com o mesmo nome."""
        self._assert_is_claude_copy(title)
        existing = {ws.title: ws for ws in self.spreadsheet.worksheets()}
        if title in existing:
            self.spreadsheet.del_worksheet(existing[title])
        return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def ensure_worksheet_with_header(
        self, title: str, header: list[str], rows: int = 1000, cols: int | None = None
    ) -> gspread.Worksheet:
        """Devolve a aba `title` (so permitido com prefixo CLAUDE_), criando-a
        com o cabecalho indicado se ainda nao existir. Ao contrario de
        `create_worksheet`, NUNCA apaga uma aba ja existente — usado para
        logs que se acumulam entre execucoes (ex.: auditoria)."""
        self._assert_is_claude_copy(title)
        existing = {ws.title: ws for ws in self.spreadsheet.worksheets()}
        if title in existing:
            return existing[title]
        ws = self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols or len(header))
        ws.update([header], "A1")
        return ws

    def delete_worksheet(self, title: str) -> None:
        self._assert_is_claude_copy(title)
        ws = self.spreadsheet.worksheet(title)
        self.spreadsheet.del_worksheet(ws)
