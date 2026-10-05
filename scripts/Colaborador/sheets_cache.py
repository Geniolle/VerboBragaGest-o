"""Cache compartilhado de sheets durante execução do cockpit.

Problema: Cada script lê as mesmas sheets múltiplas vezes, excedendo quotas.
Solução: Cache em arquivo JSON durante execução do cockpit.

Uso:
    # Primeiro script (lê e cacheia)
    cache = SheetsCache()
    bp_autority = cache.read("BP AUTORITY")

    # Próximos scripts (usam cache)
    cache = SheetsCache()
    bp_autority = cache.read("BP AUTORITY")  # Retorna do cache

    # Final do cockpit
    SheetsCache.cleanup()
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


class SheetsCache:
    """Cache compartilhado de sheets entre scripts."""

    # Diretório de cache (arquivo temporário compartilhado)
    _CACHE_DIR = Path(tempfile.gettempdir()) / "pastoreio_cockpit_cache"
    _CACHE_TIMEOUT = 3600  # 1 hora de validade do cache

    def __init__(self):
        """Inicializar cache."""
        self._guard = None
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    @property
    def _cache_dir(cls) -> Path:
        return cls._CACHE_DIR

    def _get_cache_file(self, sheet_name: str) -> Path:
        """Obter caminho do arquivo de cache para uma sheet."""
        safe_name = sheet_name.replace(" ", "_").lower()
        return self._cache_dir / f"{safe_name}.json"

    def _is_cache_valid(self, sheet_name: str) -> bool:
        """Verificar se cache é válido."""
        cache_file = self._get_cache_file(sheet_name)
        if not cache_file.exists():
            return False

        # Verificar timestamp
        mtime = cache_file.stat().st_mtime
        age = time.time() - mtime
        return age < self._CACHE_TIMEOUT

    def read(self, sheet_name: str) -> list[list[str]]:
        """Ler sheet (cache se disponível, senão lê do Google)."""

        # Tentar cache primeiro
        if self._is_cache_valid(sheet_name):
            try:
                cache_file = self._get_cache_file(sheet_name)
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data["rows"]
            except (json.JSONDecodeError, KeyError, OSError):
                # Cache corrompido, remover e ler de novo
                cache_file.unlink(missing_ok=True)

        # Ler do Google Sheets
        if self._guard is None:
            settings = load_settings()
            self._guard = SpreadsheetGuard(settings)

        rows = self._guard.read_worksheet(sheet_name)

        # Cachear resultado
        try:
            cache_file = self._get_cache_file(sheet_name)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"rows": rows, "timestamp": time.time()}, f)
        except OSError:
            # Falha ao cachear, continua normalmente
            pass

        return rows

    @classmethod
    def cleanup(cls) -> None:
        """Limpar cache (final do cockpit)."""
        try:
            import shutil

            if cls._CACHE_DIR.exists():
                shutil.rmtree(cls._CACHE_DIR)
        except OSError:
            pass

    @classmethod
    def stats(cls) -> dict:
        """Obter estatísticas do cache."""
        if not cls._CACHE_DIR.exists():
            return {"cached_sheets": 0, "total_size_bytes": 0}

        cache_files = list(cls._CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "cached_sheets": len(cache_files),
            "total_size_bytes": total_size,
            "cache_dir": str(cls._CACHE_DIR),
        }
