# -*- coding: utf-8 -*-
r"""Executa sequencialmente todos os scripts preencher_claude_*.

Por padrao, interrompe a sequencia assim que uma etapa falha. O cockpit usa
sempre o interpretador da .venv deste projeto, mesmo quando outra .venv esta
ativa, e pode ser executado a partir de qualquer diretorio.

Uso:
    .\.venv\Scripts\python.exe .\scripts\cockpit_preencher_claude.py
    .\.venv\Scripts\python.exe .\scripts\cockpit_preencher_claude.py --simular
    .\.venv\Scripts\python.exe .\scripts\cockpit_preencher_claude.py --continuar-em-erro
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


SCRIPTS = (
    "preencher_claude_appanualglobal_domingo.py",
    "preencher_claude_appanualglobal_quarta.py",
    "preencher_claude_appanualglobal_auxiliar_domingo.py",
    "preencher_claude_appanualglobal_auxiliar_quarta.py",
    "preencher_claude_appanualglobal_ceia.py",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--simular",
        action="store_true",
        help="Mostra a ordem dos scripts sem os executar.",
    )
    parser.add_argument(
        "--continuar-em-erro",
        action="store_true",
        help="Continua as etapas seguintes mesmo se uma delas falhar.",
    )
    args = parser.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    project_dir = scripts_dir.parent
    candidatos_python = (
        project_dir / ".venv" / "Scripts" / "python.exe",  # Windows
        project_dir / ".venv" / "bin" / "python",  # Linux/macOS
    )
    python_projeto = next(
        (caminho for caminho in candidatos_python if caminho.is_file()), None
    )
    if python_projeto is None:
        print(
            f"ERRO: a .venv do projeto nao foi encontrada em {project_dir / '.venv'}.",
            file=sys.stderr,
        )
        return 2

    caminhos = [scripts_dir / nome for nome in SCRIPTS]
    ausentes = [str(caminho) for caminho in caminhos if not caminho.is_file()]
    if ausentes:
        print("ERRO: script(s) nao encontrado(s):", file=sys.stderr)
        for caminho in ausentes:
            print(f"  - {caminho}", file=sys.stderr)
        return 2

    print("Cockpit de preenchimento CLAUDE")
    print(f"Python do cockpit: {sys.executable}")
    print(f"Python dos scripts: {python_projeto}")
    print("Ordem de execucao:")
    for numero, caminho in enumerate(caminhos, start=1):
        print(f"  {numero}. {caminho.name}")

    if args.simular:
        print("\nSimulacao concluida; nenhum script foi executado.")
        return 0

    resultados: list[tuple[str, int, float]] = []
    total = len(caminhos)

    for numero, caminho in enumerate(caminhos, start=1):
        print(f"\n{'=' * 72}", flush=True)
        print(f"[{numero}/{total}] Executando {caminho.name}", flush=True)
        print(f"{'=' * 72}", flush=True)
        inicio = time.monotonic()

        try:
            processo = subprocess.run(
                [str(python_projeto), str(caminho)],
                cwd=project_dir,
                check=False,
            )
            codigo = processo.returncode
        except KeyboardInterrupt:
            print("\nExecucao interrompida pelo utilizador.", file=sys.stderr)
            return 130

        duracao = time.monotonic() - inicio
        resultados.append((caminho.name, codigo, duracao))

        if codigo != 0:
            print(
                f"\nERRO: {caminho.name} terminou com codigo {codigo}.",
                file=sys.stderr,
            )
            if not args.continuar_em_erro:
                print("As etapas seguintes nao foram executadas.", file=sys.stderr)
                break

    print(f"\n{'=' * 72}")
    print("Resumo")
    print(f"{'=' * 72}")
    for nome, codigo, duracao in resultados:
        estado = "OK" if codigo == 0 else f"FALHOU ({codigo})"
        print(f"  {estado:12} {duracao:8.1f}s  {nome}")

    executados = {nome for nome, _, _ in resultados}
    for caminho in caminhos:
        if caminho.name not in executados:
            print(f"  {'NAO EXECUTADO':12} {'':8}  {caminho.name}")

    falhas = [codigo for _, codigo, _ in resultados if codigo != 0]
    if falhas:
        print(f"\nConcluido com {len(falhas)} falha(s).", file=sys.stderr)
        return 1

    print("\nTodos os scripts foram executados com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
