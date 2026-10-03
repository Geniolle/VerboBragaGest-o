"""Cliente de acesso ao Google Sheets com trava de seguranca.

Por padrao, qualquer escrita (update de celulas, limpeza, etc.) so e
permitida em abas cujo titulo comece por "CLAUDE_". Um processo validado pode
promover uma escrita produtiva passando explicitamente a allowlist de abas
originais que aquele processo esta autorizado a alterar. Abas fora dessa
allowlist continuam somente leitura.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional
from collections import deque
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

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
    """Wrapper fino sobre gspread.Spreadsheet com allowlist de escrita.

    A escrita em `CLAUDE_*` e sempre permitida. Escrita em aba produtiva exige
    que o chamador passe o titulo em `writable_original_titles`, de forma
    explicita e por processo.

    Inclui:
    - Cache de leitura por sheet (invalidado após escrita)
    - Retry automático com backoff exponencial para HTTP 429
    - Instrumentação de leituras/escritas
    """

    def __init__(self, settings: Settings, writable_original_titles: set[str] | None = None):
        self.settings = settings
        self.writable_original_titles = set(writable_original_titles or set())
        self.client = get_client(settings)
        self.spreadsheet = self.client.open_by_key(settings.spreadsheet_id)

        # Cache de leitura
        self._worksheet_cache: dict[str, list[list[str]]] = {}
        self._worksheet_objects: dict[str, gspread.Worksheet] = {}

        # Instrumentação
        self.metrics = {
            'api_reads': 0,
            'cache_hits': 0,
            'writes': 0,
            'retries': 0,
            'force_refreshes': 0,
            'by_sheet': {}  # {sheet_name: {api_reads, cache_hits, ...}}
        }

        # Configuração de retry
        self.max_retries = int(os.getenv('GOOGLE_SHEETS_MAX_RETRIES', '5'))
        self.backoff_base = int(os.getenv('GOOGLE_SHEETS_BACKOFF_BASE_SECONDS', '2'))

        # Rate limiting (60 reads/minuto)
        self.quota_limit_per_minute = 60
        self.quota_threshold = 50  # Parar em 50 para margem
        self.read_timestamps = deque()  # Timestamps das últimas leituras

    def list_worksheet_titles(self) -> list[str]:
        return [ws.title for ws in self.spreadsheet.worksheets()]

    def read_worksheet(self, title: str, force_refresh: bool = False) -> list[list[str]]:
        """Leitura com cache local + retry 429.

        Args:
            title: nome da sheet
            force_refresh: True = ignorar cache e reler da API

        Returns:
            dados da sheet como lista de listas
        """
        # Verificar cache
        if not force_refresh and title in self._worksheet_cache:
            self.metrics['cache_hits'] += 1
            if title not in self.metrics['by_sheet']:
                self.metrics['by_sheet'][title] = {'api_reads': 0, 'cache_hits': 0}
            self.metrics['by_sheet'][title]['cache_hits'] += 1
            return self._worksheet_cache[title]

        if force_refresh:
            self.metrics['force_refreshes'] += 1

        # Rate limiting: parar se aproximar do limite de quota
        self._check_rate_limit()

        # Reler da API com retry
        for tentativa in range(self.max_retries):
            try:
                ws = self.spreadsheet.worksheet(title)
                dados = ws.get_all_values()

                # Guardar em cache
                self._worksheet_cache[title] = dados
                self._worksheet_objects[title] = ws

                # Instrumentação + rate limiting tracking
                self.metrics['api_reads'] += 1
                self.read_timestamps.append(datetime.now())  # Rastrear para rate limit
                if title not in self.metrics['by_sheet']:
                    self.metrics['by_sheet'][title] = {'api_reads': 0, 'cache_hits': 0}
                self.metrics['by_sheet'][title]['api_reads'] += 1

                return dados

            except APIError as e:
                if e.code == 429:
                    self.metrics['retries'] += 1

                    if tentativa < self.max_retries - 1:
                        # Calcular delay com backoff exponencial
                        delay = self.backoff_base * (2 ** tentativa)

                        # Respeitar Retry-After se existir
                        if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                            retry_after = e.response.headers.get('Retry-After')
                            if retry_after:
                                try:
                                    delay = int(retry_after)
                                except (ValueError, TypeError):
                                    pass

                        time.sleep(delay)
                    else:
                        raise
                else:
                    # Erro não transitório: falhar imediatamente
                    raise

    def _invalidate_cache(self, title: str) -> None:
        """Invalidar cache da sheet após escrita."""
        if title in self._worksheet_cache:
            del self._worksheet_cache[title]
        if title in self._worksheet_objects:
            del self._worksheet_objects[title]

    def _check_rate_limit(self) -> None:
        """Verificar quota de leituras (60/minuto). Pausa se aproximar do limite."""
        if not hasattr(self, 'read_timestamps'):
            self.read_timestamps = deque()
        if not hasattr(self, 'quota_threshold'):
            self.quota_threshold = 50
        if not hasattr(self, 'quota_limit_per_minute'):
            self.quota_limit_per_minute = 60

        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)

        # Remover timestamps antigos (> 1 minuto)
        while self.read_timestamps and self.read_timestamps[0] < one_minute_ago:
            self.read_timestamps.popleft()

        # Verificar se atingiu threshold
        if len(self.read_timestamps) >= self.quota_threshold:
            # Calcular quanto tempo aguardar
            oldest_read = self.read_timestamps[0]
            time_until_expire = (oldest_read + timedelta(minutes=1)) - now
            wait_seconds = max(0, time_until_expire.total_seconds())

            print(f"\n⏳ [RATE LIMIT] Aproximação ao limite ({len(self.read_timestamps)}/{self.quota_limit_per_minute} reads/minuto)")
            print(f"   Aguardando {wait_seconds:.1f}s para nova janela de quota...")
            time.sleep(wait_seconds + 0.5)  # +0.5s de margem

            # Limpar timestamps após aguardo
            self.read_timestamps.clear()

    def _assert_can_write(self, title: str) -> None:
        if not title.startswith(CLAUDE_PREFIX) and title not in self.writable_original_titles:
            raise TentativaDeAlteracaoOriginalError(
                f"Bloqueado: tentativa de escrever/apagar na aba '{title}'. "
                f"So e permitido escrever em abas com prefixo '{CLAUDE_PREFIX}' "
                "ou em abas produtivas explicitamente autorizadas pelo processo."
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
        self._assert_can_write(title)
        ws = self.spreadsheet.worksheet(title)
        ws.update(values, "A1")
        self._invalidate_cache(title)
        self.metrics['writes'] += 1

    def update_cell(self, title: str, row: int, col: int, value: str) -> None:
        self._assert_can_write(title)
        ws = self.spreadsheet.worksheet(title)
        ws.update_cell(row, col, value)
        self._invalidate_cache(title)
        self.metrics['writes'] += 1

    def batch_update_cells(self, title: str, updates: list[tuple[int, int, str]]) -> None:
        """Escreve varias celulas (possivelmente nao-contiguas, ex.: uma
        Ronda inteira de domingos/quartas) numa UNICA chamada de API, em vez
        de uma chamada por celula (`update_cell`). Pedido do Clayton
        (2026-09-08) para economizar cota da API depois de bater em rate
        limit (429) rodando Rondas em sequencia -- cada `update_cell` conta
        como 1 requisicao de escrita; uma Ronda de 18 datas viravam 18
        requisicoes, agora viram 1. Nao faz nada se `updates` estiver vazio
        (algumas APIs de batch rejeitam payload vazio)."""
        self._assert_can_write(title)
        if not updates:
            return
        ws = self.spreadsheet.worksheet(title)
        data = [
            {"range": gspread.utils.rowcol_to_a1(row, col), "values": [[value]]}
            for row, col, value in updates
        ]
        ws.batch_update(data, value_input_option=gspread.utils.ValueInputOption.user_entered)

    def batch_clear_cells(self, title: str, cells: list[tuple[int, int]]) -> None:
        """Limpa varias celulas numa unica chamada de API."""
        self._assert_can_write(title)
        if not cells:
            return
        ws = self.spreadsheet.worksheet(title)
        ranges = [gspread.utils.rowcol_to_a1(row, col) for row, col in cells]
        ws.batch_clear(ranges)

    def append_row(self, title: str, values: list[str]) -> None:
        self._assert_can_write(title)
        ws = self.spreadsheet.worksheet(title)
        ws.append_row(values)

    def append_rows(self, title: str, rows: list[list[str]]) -> None:
        """Acrescenta varias linhas numa UNICA chamada de API (mesmo motivo
        de `batch_update_cells`: evitar 1 requisicao por linha). Nao faz
        nada se `rows` estiver vazio."""
        self._assert_can_write(title)
        if not rows:
            return
        ws = self.spreadsheet.worksheet(title)
        ws.append_rows(rows, value_input_option=gspread.utils.ValueInputOption.user_entered)

    def create_worksheet(self, title: str, rows: int = 100, cols: int = 26) -> gspread.Worksheet:
        """Cria uma aba nova.

        Para `CLAUDE_*`, substitui uma aba pre-existente com o mesmo nome.
        Para produtivo explicitamente autorizado, nunca apaga uma aba existente.
        """
        self._assert_can_write(title)
        existing = {ws.title: ws for ws in self.spreadsheet.worksheets()}
        if title in existing:
            if not title.startswith(CLAUDE_PREFIX):
                raise TentativaDeAlteracaoOriginalError(
                    f"Bloqueado: tentativa de recriar a aba produtiva '{title}'. "
                    "A allowlist produtiva permite escrita, nao delete/recreate."
                )
            self.spreadsheet.del_worksheet(existing[title])
        return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def ensure_worksheet_with_header(
        self, title: str, header: list[str], rows: int = 1000, cols: int | None = None
    ) -> gspread.Worksheet:
        """Devolve a aba `title` (so permitido com prefixo CLAUDE_), criando-a
        com o cabecalho indicado se ainda nao existir. Ao contrario de
        `create_worksheet`, NUNCA apaga uma aba ja existente — usado para
        logs que se acumulam entre execucoes (ex.: auditoria)."""
        self._assert_can_write(title)
        existing = {ws.title: ws for ws in self.spreadsheet.worksheets()}
        if title in existing:
            ws = existing[title]
            header_atual = ws.row_values(1)
            if [str(v).strip() for v in header_atual] != [str(v).strip() for v in header]:
                ws.update([header], "A1")
            return ws
        ws = self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols or len(header))
        ws.update([header], "A1")
        return ws

    def delete_worksheet(self, title: str) -> None:
        if not title.startswith(CLAUDE_PREFIX):
            raise TentativaDeAlteracaoOriginalError(
                f"Bloqueado: tentativa de apagar a aba produtiva '{title}'. "
                "A allowlist produtiva permite escrita, nao delete."
            )
        ws = self.spreadsheet.worksheet(title)
        self.spreadsheet.del_worksheet(ws)

    def delete_rows(self, title: str, rows: list[int]) -> None:
        """Apaga linhas especificas de uma aba permitida, de baixo para cima.

        Usado por processos produtivos com allowlist explicita quando a regra
        de negocio exige remover linhas obsoletas sem apagar a worksheet.
        """
        self._assert_can_write(title)
        if not rows:
            return
        ws = self.spreadsheet.worksheet(title)
        for row in sorted(set(rows), reverse=True):
            ws.delete_rows(row)
        self._invalidate_cache(title)
        self.metrics['writes'] += 1
