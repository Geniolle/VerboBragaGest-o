"""Checklist de pre-alocacao (propostas E e F): so leitura, nunca altera
nada. Roda o sanity check de regras (SINC invalido, quotas contraditorias)
e o protocolo de validacao por grupo (compara BP ALGORITIMO com
GRUPOS_VALIDADOS.md).

Uso:
    uv run python scripts/checklist_pre_alocacao.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from pastoreio_orquestrador.carregamento import carregar_regras_colaboradores
from pastoreio_orquestrador.config import PROJECT_ROOT, load_settings
from pastoreio_orquestrador.protocolo_validacao import avaliar_grupos, parse_grupos_validados
from pastoreio_orquestrador.sanity_regras import diagnosticar_regras
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)

    regras_raw = guard.read_worksheet("BP ALGORITIMO")
    regras = carregar_regras_colaboradores(regras_raw)
    print(f"Regras ativas carregadas: {len(regras)}")

    print("\n--- Proposta E: sanity check de configuracao ---")
    relatorio_sanity = diagnosticar_regras(regras)
    if relatorio_sanity.ok:
        print("Nenhum problema encontrado.")
    else:
        for aviso in relatorio_sanity.avisos_sinc:
            print(f"  [SINC] {aviso}")
        for aviso in relatorio_sanity.avisos_quota:
            print(f"  [QUOTA] {aviso}")

    print("\n--- Proposta F: protocolo de validacao por grupo ---")
    registro_path = PROJECT_ROOT / "GRUPOS_VALIDADOS.md"
    grupos_validados = parse_grupos_validados(registro_path.read_text(encoding="utf-8"))
    relatorio_grupos = avaliar_grupos(regras, grupos_validados)

    print(f"Grupos validados ({len(relatorio_grupos.validados)}):")
    for g in relatorio_grupos.validados:
        print(f"  - {g}")
    print(f"Grupos pendentes de validacao ({len(relatorio_grupos.pendentes)}):")
    for g in relatorio_grupos.pendentes:
        print(f"  - {g}")

    if not relatorio_sanity.ok:
        print("\nChecklist encontrou avisos de configuracao (ver acima).")
        sys.exit(1)


if __name__ == "__main__":
    main()
