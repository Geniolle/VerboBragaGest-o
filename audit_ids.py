"""Auditoria read-only do estado dos 4 IDs nas 3 sheets."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

def get_lines(row, idx, col):
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()

def audit_ids():
    guard = SpreadsheetGuard(load_settings())

    ids_to_check = ["22", "52", "71", "122"]

    # Ler sheets
    bp_service = guard.read_worksheet("BP SERVICE", force_refresh=True)
    bp_autority = guard.read_worksheet("BP AUTORITY", force_refresh=True)
    bp_algoritimo = guard.read_worksheet("BP ALGORITIMO", force_refresh=True)

    # Headers
    idx_service = {str(v).strip(): i for i, v in enumerate(bp_service[0])}
    idx_autority = {str(v).strip(): i for i, v in enumerate(bp_autority[0])}
    idx_algoritimo = {str(v).strip(): i for i, v in enumerate(bp_algoritimo[0])}

    print("=" * 80)
    print("[AUDITORIA READ-ONLY] Estado atual dos IDs 22, 52, 71, 122")
    print("=" * 80)

    for id_user in ids_to_check:
        print(f"\n{'='*80}")
        print(f"ID_USER: {id_user}")
        print(f"{'='*80}")

        # BP SERVICE
        print("\nBP SERVICE:")
        found_service = False
        for i, row in enumerate(bp_service[1:], start=2):
            if get_lines(row, idx_service, "ID_USER") == id_user:
                found_service = True
                print(f"  Linha: {i}")
                print(f"    NOME: {get_lines(row, idx_service, 'NOME')}")
                print(f"    DEPARTAMENTOS: {get_lines(row, idx_service, 'DEPARTAMENTOS')}")
                print(f"    BP AUTORITY: {get_lines(row, idx_service, 'BP AUTORITY')}")
                print(f"    INATIVO: {get_lines(row, idx_service, 'INATIVO')}")

        if not found_service:
            print("  (não encontrado em BP SERVICE)")

        # BP AUTORITY
        print("\nBP AUTORITY:")
        found_autority = 0
        for i, row in enumerate(bp_autority[1:], start=2):
            if get_lines(row, idx_autority, "ID_USER") == id_user:
                found_autority += 1
                print(f"  Linha {i}: {get_lines(row, idx_autority, 'NOME')}")

        if found_autority == 0:
            print("  (não encontrado em BP AUTORITY)")

        # BP ALGORITIMO
        print("\nBP ALGORITIMO:")
        found_algoritimo = 0
        for i, row in enumerate(bp_algoritimo[1:], start=2):
            if get_lines(row, idx_algoritimo, "ID_USER") == id_user:
                found_algoritimo += 1
                dept = get_lines(row, idx_algoritimo, "DEPARTAMENTO")
                funcao = get_lines(row, idx_algoritimo, "FUNÇÃO")
                print(f"  Linha {i}: {dept} / {funcao}")

        if found_algoritimo == 0:
            print("  (não encontrado em BP ALGORITIMO)")

        print(f"\nRESUMO:")
        print(f"  BP SERVICE: {'SIM' if found_service else 'NÃO'}")
        print(f"  BP AUTORITY: {found_autority} linha(s)")
        print(f"  BP ALGORITIMO: {found_algoritimo} linha(s)")

if __name__ == "__main__":
    audit_ids()
