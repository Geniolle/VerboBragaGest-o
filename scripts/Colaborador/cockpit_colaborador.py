"""Cockpit do processo Colaborador/Utilizador.

Executa os subprocessos na ordem operacional correta.

Por padrao roda em dry-run sempre que o subprocesso suporta dry-run. Use
--aplicar para permitir escrita nos subprocessos controlados.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from pastoreio_orquestrador.saude_colaborador import gravar_saude
from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


BASE_DIR = Path(__file__).resolve().parent
ETAPA_TIMEOUT_SECONDS = 1800
HEALTH_FILE = Path(os.environ["PASTOREIO_HEALTH_FILE"]) if os.environ.get("PASTOREIO_HEALTH_FILE") else None
PREFETCH_SHEETS = [
    "Membresia",
    "BP SERVICE",
    "BP COLABORADOR",
    "BP AUTORITY",
    "BP ALGORITIMO",
    "ID_MANAGER",
]


@dataclass(frozen=True)
class Etapa:
    nome: str
    script: str
    aplica: bool = False
    usa_cache: bool = False


@dataclass(frozen=True)
class ResultadoEtapa:
    nome: str
    duracao_segundos: float


ETAPAS = [
    Etapa(
        "1. Analisar pendentes Membresia -> BP SERVICE",
        "analisar_membresia_bp_service.py",
    ),
    Etapa(
        "2. Marcar Membresia.BP SERVICE para pessoas ja existentes",
        "marcar_membresia_bp_service_existentes.py",
        aplica=True,
    ),
    Etapa(
        "3. Validar DEPARTAMENTOS x colunas D.* em BP SERVICE",
        "validar_flag_departamentos_bp_service.py",
    ),
    Etapa(
        "4. Atualizar BP COLABORADOR a partir de BP SERVICE",
        "atualizar_bp_colaborador.py",
        aplica=True,
    ),
    Etapa(
        "5. Atualizar BP AUTORITY a partir de BP SERVICE",
        "atualizar_bp_autority.py",
        aplica=True,
    ),
    Etapa(
        "5.5. Reconciliar flags de Manager/Coordenador em BP AUTORITY",
        "reconciliar_flags_papeis_bp_autority.py",
        aplica=True,
    ),
    Etapa(
        "6. Reconciliar cadeia transacional: BP ALGORITIMO -> BP AUTORITY -> BP SERVICE",
        "reconciliar_cadeia_departamentos.py",
        aplica=True,
    ),
    Etapa(
        "7. Sincronizar BP AUTORITY -> BP ALGORITIMO (ativação completa)",
        "sincronizar_bp_autority_bp_algoritimo.py",
        aplica=True,
    ),
    Etapa(
        "8. Sincronizar BP AUTORITY -> ID_MANAGER (managers por departamento)",
        "sincronizar_id_manager.py",
        aplica=True,
    ),
]


def format_duration(seconds: float) -> str:
    minutes, remaining = divmod(seconds, 60)
    return f"{int(minutes):02d}:{remaining:05.2f}"


def run_etapa(etapa: Etapa, aplicar: bool, no_cache: bool = False) -> ResultadoEtapa:
    if HEALTH_FILE is not None:
        gravar_saude(HEALTH_FILE, current_stage=etapa.nome)
    cmd = [sys.executable, str(BASE_DIR / etapa.script)]
    if aplicar and etapa.aplica:
        cmd.append("--aplicar")
    if not no_cache and etapa.usa_cache:
        cmd.append("--use-cache")

    print("", flush=True)
    print("=" * 79, flush=True)
    print(etapa.nome, flush=True)
    print("Comando:", " ".join(cmd), flush=True)
    print("=" * 79, flush=True)

    started_at = time.perf_counter()
    try:
        subprocess.run(cmd, check=True, timeout=ETAPA_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started_at
        print(
            f"\n[TIMEOUT] {etapa.nome}: excedeu {ETAPA_TIMEOUT_SECONDS}s "
            f"apos {format_duration(elapsed)}",
            flush=True,
        )
        raise SystemExit(exc.timeout) from exc
    elapsed = time.perf_counter() - started_at
    if HEALTH_FILE is not None:
        gravar_saude(HEALTH_FILE, last_completed_stage=etapa.nome)
    print(f"\n[DURACAO] {etapa.nome}: {format_duration(elapsed)}", flush=True)
    return ResultadoEtapa(nome=etapa.nome, duracao_segundos=elapsed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Aplica escrita nos subprocessos que suportam --aplicar.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Desativa cache de sheets (debug).",
    )
    args = parser.parse_args()

    print("###############################################################################", flush=True)
    print("[COLABORADOR] COCKPIT", flush=True)
    print(f"Modo: {'APLICAR' if args.aplicar else 'DRY-RUN'}", flush=True)
    print(f"Cache: {'DESATIVADO' if args.no_cache else 'ATIVADO'}", flush=True)
    print("###############################################################################", flush=True)

    if os.environ.get("PASTOREIO_SHEETS_SHARED_CACHE_DIR") and not args.no_cache:
        print("[CACHE] prefetch batch das sheets do Colaborador", flush=True)
        SpreadsheetGuard(load_settings()).prefetch_worksheets(PREFETCH_SHEETS)

    resultados = []
    started_at = time.perf_counter()
    try:
        for etapa in ETAPAS:
            resultados.append(run_etapa(etapa, args.aplicar, args.no_cache))
    finally:
        # Limpar cache ao final
        if not args.no_cache:
            try:
                import sys
                sys.path.insert(0, str(BASE_DIR))
                from sheets_cache import SheetsCache
                SheetsCache.cleanup()
                stats = SheetsCache.stats()
                if stats["cached_sheets"] > 0:
                    print(f"\n[CACHE STATS] {stats['cached_sheets']} sheets em cache ({stats['total_size_bytes']} bytes)", flush=True)
            except Exception:
                pass
    total_elapsed = time.perf_counter() - started_at

    print("", flush=True)
    print("###############################################################################", flush=True)
    print("[COLABORADOR] TEMPOS", flush=True)
    for resultado in resultados:
        print(f"{resultado.nome}: {format_duration(resultado.duracao_segundos)}", flush=True)
    print(f"Total: {format_duration(total_elapsed)}", flush=True)
    print("###############################################################################", flush=True)
    print("", flush=True)
    print("###############################################################################", flush=True)
    print("[COLABORADOR] COCKPIT CONCLUIDO", flush=True)
    print("###############################################################################", flush=True)


if __name__ == "__main__":
    main()
