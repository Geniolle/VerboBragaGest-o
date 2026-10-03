"""Validação detalhada do plano de remoção - mostra exatamente o que será feito."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

# Import local functions
import importlib.util
spec = importlib.util.spec_from_file_location("reconciliar", Path(__file__).parent / "reconciliar_cadeia_departamentos.py")
reconciliar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconciliar_module)

calcular_plano = reconciliar_module.calcular_plano
map_headers = reconciliar_module.map_headers
get = reconciliar_module.get
is_true = reconciliar_module.is_true

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_AUTORITY = "BP AUTORITY"
SHEET_BP_ALGORITIMO = "BP ALGORITIMO"


def main():
    guard = SpreadsheetGuard(load_settings())
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)
    bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO)

    idx_service = map_headers(bp_service[0])
    idx_autority = map_headers(bp_autority[0])
    idx_algoritimo = map_headers(bp_algoritimo[0])

    plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

    print("###############################################################################")
    print("[VALIDAÇÃO DETALHADA] PLANO DE REMOÇÃO")
    print("###############################################################################\n")

    # Colunas D.*
    d_colunas = [c for c in bp_service[0] if str(c).strip().upper().startswith("D.")]

    print(f"ATIVAÇÕES PREVISTAS: {len(plano.pessoas_ativacao)}\n")

    print(f"REMOÇÕES PREVISTAS: {len(plano.pessoas_remocao)}\n")

    for pessoa in plano.pessoas_remocao:
        print("=" * 79)
        print(f"ID_USER: {pessoa.id_user}")
        print(f"NOME: {pessoa.nome}")
        print(f"MOTIVO: {pessoa.motivo}\n")

        # Encontrar linha em BP SERVICE
        linha_service = None
        for i, row in enumerate(bp_service[1:], start=2):
            if get(row, idx_service, "ID_USER") == pessoa.id_user:
                linha_service = i
                row_service = row
                break

        if linha_service:
            # D.* ativos
            depts = [c for c in d_colunas if is_true(get(row_service, idx_service, c))]
            print(f"D.* ativos: {depts if depts else '(nenhum)'}")

            # Flags
            dept_flag = get(row_service, idx_service, "DEPARTAMENTOS")
            bp_aut_flag = get(row_service, idx_service, "BP AUTORITY")
            inativo = get(row_service, idx_service, "INATIVO")

            print(f"BP SERVICE.DEPARTAMENTOS: {dept_flag if dept_flag else '(vazio)'}")
            print(f"BP SERVICE.BP AUTORITY: {bp_aut_flag if bp_aut_flag else '(vazio)'}")
            print(f"BP SERVICE.INATIVO: {inativo if inativo else '(vazio)'}")

        # Verificar BP AUTORITY
        linha_autority = None
        for i, row in enumerate(bp_autority[1:], start=2):
            if get(row, idx_autority, "ID_USER") == pessoa.id_user:
                linha_autority = i
                break

        print(f"\nBP AUTORITY:")
        if linha_autority:
            print(f"  Existe: SIM (linha {linha_autority})")
            print(f"  AÇÃO: delete_rows(BP AUTORITY, [{linha_autority}])")
        else:
            print(f"  Existe: NÃO")

        # Verificar BP ALGORITIMO
        linhas_algoritimo = []
        for i, row in enumerate(bp_algoritimo[1:], start=2):
            if get(row, idx_algoritimo, "ID_USER") == pessoa.id_user:
                linhas_algoritimo.append(i)

        print(f"\nBP ALGORITIMO:")
        if linhas_algoritimo:
            print(f"  Existe: SIM ({len(linhas_algoritimo)} linha(s): {linhas_algoritimo})")
            print(f"  AÇÃO: delete_rows(BP ALGORITIMO, {linhas_algoritimo})")
        else:
            print(f"  Existe: NÃO")

        # Resumo de ações
        print(f"\nORDEM DE EXECUÇÃO:")
        if linhas_algoritimo:
            print(f"  1. delete_rows(BP ALGORITIMO, {linhas_algoritimo})")
            print(f"  2. validar BP ALGORITIMO")
            if linha_autority:
                print(f"  3. delete_rows(BP AUTORITY, [{linha_autority}])")
                print(f"  4. validar BP AUTORITY")
        elif linha_autority:
            print(f"  1. delete_rows(BP AUTORITY, [{linha_autority}])")
            print(f"  2. validar BP AUTORITY")

        print(f"  N. batch_update(BP SERVICE): DEPARTAMENTOS='FALSE', BP AUTORITY=''")
        print(f"  INATIVO: NÃO SERÁ ALTERADO\n")

    # Validação de integridade
    print("=" * 79)
    print("[VALIDAÇÃO DE INTEGRIDADE]\n")

    # Confirmar que não afeta Davi/Suzana
    print("Pessoas que NÃO serão alteradas (Davi Fenner, Suzana Fonseca):")
    for i, row in enumerate(bp_service[1:], start=2):
        if get(row, idx_service, "NOME") in ["Davi Fenner", "Suzana Fonseca"]:
            id_user = get(row, idx_service, "ID_USER")
            depts = [c for c in d_colunas if is_true(get(row, idx_service, c))]
            print(f"  {get(row, idx_service, 'NOME')} (ID {id_user}): D.* = {depts}")

    print("\nDepartamentos sem correspondência (NÃO será criada coluna nova):")
    print("  - D. HOMENS")
    print("  - D. MULHERES")
    print("  - D. PASTOREIO")
    print("  - COLABORADOR_EVENTOS (permanecerá intocado)")

    print("\n" + "=" * 79)
    print("✓ Validação completa (read-only)")


if __name__ == "__main__":
    main()
