"""Cockpit do processo Colaborador/Utilizador.

Executa os subprocessos na ordem operacional correta.

Por padrao roda em dry-run sempre que o subprocesso suporta dry-run. Use
--aplicar para permitir escrita nos subprocessos controlados.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Etapa:
    nome: str
    script: str
    aplica: bool = False


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
        "6. Reconciliar BP AUTORITY contra BP SERVICE",
        "reconciliar_bp_autority.py",
        aplica=True,
    ),
    Etapa(
        "7. Sincronizar BP AUTORITY -> BP ALGORITIMO",
        "sincronizar_bp_autority_bp_algoritimo.py",
        aplica=True,
    ),
]


def format_duration(seconds: float) -> str:
    minutes, remaining = divmod(seconds, 60)
    return f"{int(minutes):02d}:{remaining:05.2f}"


def run_etapa(etapa: Etapa, aplicar: bool) -> ResultadoEtapa:
    cmd = [sys.executable, str(BASE_DIR / etapa.script)]
    if aplicar and etapa.aplica:
        cmd.append("--aplicar")

    print("", flush=True)
    print("=" * 79, flush=True)
    print(etapa.nome, flush=True)
    print("Comando:", " ".join(cmd), flush=True)
    print("=" * 79, flush=True)

    started_at = time.perf_counter()
    subprocess.run(cmd, check=True)
    elapsed = time.perf_counter() - started_at
    print(f"\n[DURACAO] {etapa.nome}: {format_duration(elapsed)}", flush=True)
    return ResultadoEtapa(nome=etapa.nome, duracao_segundos=elapsed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Aplica escrita nos subprocessos que suportam --aplicar.",
    )
    args = parser.parse_args()

    print("###############################################################################", flush=True)
    print("[COLABORADOR] COCKPIT", flush=True)
    print(f"Modo: {'APLICAR' if args.aplicar else 'DRY-RUN'}", flush=True)
    print("###############################################################################", flush=True)

    resultados = []
    started_at = time.perf_counter()
    for etapa in ETAPAS:
        resultados.append(run_etapa(etapa, args.aplicar))
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
