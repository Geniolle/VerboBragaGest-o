"""Coordenação de quota e cache de Sheets entre subprocessos."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path


class SharedReadQuotaLimiter:
    """Limitador de janela móvel partilhado por ficheiro entre processos."""

    def __init__(self, state_file: Path, limit: int = 45, window_seconds: float = 60.0):
        self.state_file = state_file
        self.lock_file = state_file.with_suffix(state_file.suffix + ".lock")
        self.limit = limit
        self.window_seconds = window_seconds
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _acquire_lock(self) -> int:
        while True:
            try:
                return os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    if time.time() - self.lock_file.stat().st_mtime > 30:
                        self.lock_file.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                time.sleep(0.05)

    def _read_timestamps(self) -> list[float]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            return [float(value) for value in payload.get("timestamps", [])]
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return []

    def _write_timestamps(self, timestamps: list[float]) -> None:
        tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        tmp.write_text(json.dumps({"timestamps": timestamps}), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def acquire(self) -> None:
        while True:
            fd = self._acquire_lock()
            wait_seconds = 0.0
            try:
                now = time.time()
                timestamps = [
                    value
                    for value in self._read_timestamps()
                    if value > now - self.window_seconds
                ]
                if len(timestamps) < self.limit:
                    timestamps.append(now)
                    self._write_timestamps(timestamps)
                    return
                wait_seconds = max(0.05, timestamps[0] + self.window_seconds - now + 0.1)
                self._write_timestamps(timestamps)
            finally:
                os.close(fd)
                self.lock_file.unlink(missing_ok=True)
            print(
                f"[WAITING_QUOTA] {len(timestamps)}/{self.limit} leituras; "
                f"aguardando {wait_seconds:.1f}s",
                flush=True,
            )
            time.sleep(wait_seconds)


class SharedSheetsCache:
    """Cache JSON de uma única execução, partilhado entre subprocessos."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, title: str) -> Path:
        safe = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        return self.directory / f"{safe}.json"

    def load(self, title: str) -> list[list[str]] | None:
        try:
            payload = json.loads(self._path(title).read_text(encoding="utf-8"))
            if payload.get("title") != title:
                return None
            return payload["rows"]
        except (OSError, KeyError, json.JSONDecodeError):
            return None

    def save(self, title: str, rows: list[list[str]]) -> None:
        path = self._path(title)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"title": title, "rows": rows}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def invalidate(self, title: str) -> None:
        self._path(title).unlink(missing_ok=True)
