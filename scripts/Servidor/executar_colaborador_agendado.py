"""Runner de servidor para o cockpit Colaborador.

Responsabilidades:
- impedir execucoes concorrentes com um lock atomico;
- executar o cockpit em modo produtivo quando chamado com --aplicar;
- manter somente o log da ultima execucao real em runtime/colaborador_ultimo.log;
- nao sobrescrever o log quando uma chamada e ignorada porque outra execucao
  ainda esta em andamento.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from pastoreio_orquestrador.ntfy_alertas import notificar_transicao
from pastoreio_orquestrador.saude_colaborador import gravar_saude, ler_saude


ROOT_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT_DIR / "runtime"
LOCK_FILE = RUNTIME_DIR / "colaborador.lock"
LAST_LOG = RUNTIME_DIR / "colaborador_ultimo.log"
NTFY_STATE_FILE = RUNTIME_DIR / "colaborador_ntfy_state.json"
HEALTH_FILE = RUNTIME_DIR / "colaborador_health.json"
COCKPIT = ROOT_DIR / "scripts" / "Colaborador" / "cockpit_colaborador.py"


def cleanup_temp_logs(active_tmp: Path | None = None) -> None:
    """Remove restos de execucoes interrompidas.

    O servidor deve manter somente o ultimo log consolidado. Durante uma
    execucao normal existe um unico .tmp ativo; qualquer outro .tmp e lixo.
    """
    if not RUNTIME_DIR.exists():
        return
    active = active_tmp.resolve() if active_tmp is not None else None
    for path in RUNTIME_DIR.glob("colaborador_*.log.tmp"):
        try:
            if active is not None and path.resolve() == active:
                continue
            path.unlink()
        except OSError:
            pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if platform.system().lower() == "windows":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return f'"{pid}"' in result.stdout or f",{pid}," in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_lock_pid() -> int | None:
    try:
        text = LOCK_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in text:
        if line.startswith("pid="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def acquire_lock() -> int | None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(LOCK_FILE), flags)
    except FileExistsError:
        pid = read_lock_pid()
        if pid is not None and not is_pid_running(pid):
            try:
                LOCK_FILE.unlink()
            except FileNotFoundError:
                pass
            return acquire_lock()
        return None

    content = (
        f"pid={os.getpid()}\n"
        f"started_at={now_iso()}\n"
        f"script={Path(__file__).name}\n"
    )
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
    return os.getpid()


def release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


def build_command(aplicar: bool) -> list[str]:
    cmd = [sys.executable, str(COCKPIT)]
    if aplicar:
        cmd.append("--aplicar")
    return cmd


def run_cockpit(aplicar: bool) -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_temp_logs()
    fd, tmp_name = tempfile.mkstemp(
        prefix="colaborador_",
        suffix=".log.tmp",
        dir=RUNTIME_DIR,
        text=True,
    )
    tmp_path = Path(tmp_name)
    started = time.perf_counter()
    started_at = now_iso()
    previous = ler_saude(HEALTH_FILE)
    gravar_saude(
        HEALTH_FILE,
        state="RUNNING",
        started_at=started_at,
        finished_at=None,
        exit_code=None,
        current_stage="inicializacao",
        last_error=None,
        last_success_at=previous.get("last_success_at"),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as log:
            log.write("###############################################################################\n")
            log.write("[COLABORADOR] EXECUCAO AGENDADA\n")
            log.write(f"Inicio: {now_iso()}\n")
            log.write(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN'}\n")
            log.write(f"Workdir: {ROOT_DIR}\n")
            log.write("###############################################################################\n\n")
            log.flush()

            child_env = os.environ.copy()
            child_env["PASTOREIO_HEALTH_FILE"] = str(HEALTH_FILE)
            result = subprocess.run(
                build_command(aplicar),
                cwd=ROOT_DIR,
                env=child_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )

            elapsed = time.perf_counter() - started
            log.write("\n###############################################################################\n")
            log.write("[COLABORADOR] FIM EXECUCAO AGENDADA\n")
            log.write(f"Fim: {now_iso()}\n")
            log.write(f"Duracao segundos: {elapsed:.2f}\n")
            log.write(f"Exit code: {result.returncode}\n")
            log.write("###############################################################################\n")

        os.replace(tmp_path, LAST_LOG)
        cleanup_temp_logs()
        current = ler_saude(HEALTH_FILE)
        finished_at = now_iso()
        healthy = result.returncode == 0
        gravar_saude(
            HEALTH_FILE,
            state="HEALTHY" if healthy else "FAILED",
            finished_at=finished_at,
            exit_code=result.returncode,
            duration_seconds=round(time.perf_counter() - started, 2),
            current_stage=None,
            failed_stage=None if healthy else current.get("current_stage"),
            last_error=None if healthy else f"Cockpit terminou com exit code {result.returncode}",
            last_success_at=finished_at if healthy else current.get("last_success_at"),
        )
        status_ntfy = notificar_transicao(
            exit_code=result.returncode,
            state_file=NTFY_STATE_FILE,
            timestamp=now_iso(),
        )
        print(f"[NTFY] {status_ntfy}", flush=True)
        return result.returncode
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Executa o cockpit com escrita produtiva.")
    args = parser.parse_args()

    if acquire_lock() is None:
        return 0
    try:
        return run_cockpit(args.aplicar)
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
