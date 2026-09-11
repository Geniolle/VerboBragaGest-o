# -*- coding: utf-8 -*-
"""PASSO 1 do fluxo do orquestrador: sincroniza BP SERVICE -> BP ALGORITIMO
antes de qualquer alocacao (os scripts `preencher_claude_appanualglobal_*`
dependem de BP ALGORITIMO estar em dia com o cadastro atual de BP SERVICE).

Le BP SERVICE e ID_DEPARTAMENTOS (sempre permitido, mesmo em abas
originais), calcula o plano de sincronizacao contra a copia de teste
indicada em `--destino` (por padrao `CLAUDE_BP ALGORITIMO`) e so escreve se
`--aplicar` for passado -- por padrao roda em modo consulta (dry-run),
so mostrando o que faria.

`--destino` DEVE comecar por "CLAUDE_": escrever na aba `BP ALGORITIMO`
original e bloqueado por `SpreadsheetGuard` (regra de seguranca do
projeto, ver README.md).

Uso:
    uv run python scripts/passo1_sincronizar_bp_service.py                     # dry-run
    uv run python scripts/passo1_sincronizar_bp_service.py --aplicar           # escreve
    uv run python scripts/passo1_sincronizar_bp_service.py --destino "CLAUDE_BP ALGORITIMO" --aplicar
"""

from __future__ import annotations

import argparse

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
from pastoreio_orquestrador.sincronizacao_bp_service import (
    aplicar_plano,
    calcular_plano_sincronizacao,
    carregar_email_por_departamento,
    garantir_cabecalhos_bp_algoritimo,
    selecionar_vinculos_elegiveis,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destino",
        default="CLAUDE_BP ALGORITIMO",
        help='Aba de destino (DEVE comecar por "CLAUDE_"). Padrao: "CLAUDE_BP ALGORITIMO".',
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Escreve as mudancas de fato. Sem esta flag, so mostra o plano (dry-run).",
    )
    args = parser.parse_args()

    guard = SpreadsheetGuard(load_settings())

    bp_service_raw = guard.read_worksheet("BP SERVICE")
    id_departamentos_raw = guard.read_worksheet("ID_DEPARTAMENTOS")
    email_por_departamento = carregar_email_por_departamento(id_departamentos_raw)

    vinculos = selecionar_vinculos_elegiveis(bp_service_raw, email_por_departamento)
    print(f"Vinculos elegiveis em BP SERVICE: {len(vinculos)}")

    header_destino = garantir_cabecalhos_bp_algoritimo(guard, args.destino)
    bp_algoritimo_raw = guard.read_worksheet(args.destino)

    plano = calcular_plano_sincronizacao(vinculos, bp_algoritimo_raw)

    print(f"\nPlano de sincronizacao para '{args.destino}':")
    print(f"  Inserir: {len(plano.inserir)}")
    for v in plano.inserir:
        print(f"    + {v.nome} | {v.departamento} | ID_TABLE={v.id_user}")
    print(f"  Atualizar: {len(plano.atualizacoes)}")
    for a in plano.atualizacoes:
        print(f"    ~ linha {a.linha_bp_algoritimo} | {a.coluna} = {a.valor!r} ({a.motivo})")

    if plano.vazio:
        print("\nNada a fazer -- BP ALGORITIMO ja reflete a selecao atual de BP SERVICE.")
        return

    if not args.aplicar:
        print("\nDry-run (nada foi escrito). Rode de novo com --aplicar para gravar.")
        return

    aplicar_plano(guard, args.destino, header_destino, plano)
    print(f"\nAplicado em '{args.destino}': {len(plano.inserir)} inseridas, {len(plano.atualizacoes)} atualizadas.")


if __name__ == "__main__":
    main()
