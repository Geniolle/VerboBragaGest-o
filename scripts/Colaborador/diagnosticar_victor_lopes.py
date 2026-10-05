"""Diagnóstico específico: Victor Lopes ID 79"""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

def map_headers(header):
    return {str(value).strip(): i for i, value in enumerate(header) if str(value).strip()}

def get(row, idx, col):
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()

def is_true(value):
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"

settings = load_settings()
guard = SpreadsheetGuard(settings)

bp_service = guard.read_worksheet("BP SERVICE")
bp_autority = guard.read_worksheet("BP AUTORITY")
bp_algoritimo = guard.read_worksheet("BP ALGORITIMO")

idx_svc = map_headers(bp_service[0])
idx_auth = map_headers(bp_autority[0])
idx_alg = map_headers(bp_algoritimo[0])

print("=" * 80)
print("[DIAGNÓSTICO] Victor Lopes ID 79")
print("=" * 80)

# Procurar em BP SERVICE
print("\n[BP SERVICE]")
found_service = False
for i, row in enumerate(bp_service[1:], start=2):
    if get(row, idx_svc, "ID_USER") == "79":
        found_service = True
        print(f"Linha {i}: {get(row, idx_svc, 'NOME')}")
        print(f"  INATIVO: {get(row, idx_svc, 'INATIVO')}")
        print(f"  DEPARTAMENTOS: {get(row, idx_svc, 'DEPARTAMENTOS')}")
        print(f"  BP AUTORITY: {get(row, idx_svc, 'BP AUTORITY')}")

        # Mostrar D.*
        print("  D.* (Departamentos):")
        for col in bp_service[0]:
            col_str = str(col).strip()
            if col_str.upper().startswith("D."):
                val = get(row, idx_svc, col_str)
                if val:
                    print(f"    {col_str}: {val}")

if not found_service:
    print("❌ NÃO ENCONTRADO em BP SERVICE")

# Procurar em BP AUTORITY
print("\n[BP AUTORITY]")
found_auth = False
for i, row in enumerate(bp_autority[1:], start=2):
    if get(row, idx_auth, "ID_USER") == "79":
        found_auth = True
        print(f"Linha {i}: {get(row, idx_auth, 'NOME')}")

        # Mostrar flags COLABORADOR_*
        print("  COLABORADOR_* (Flags ativas):")
        has_flags = False
        for col in bp_autority[0]:
            col_str = str(col).strip()
            if col_str.upper().startswith("COLABORADOR_"):
                val = get(row, idx_auth, col_str)
                if is_true(val):
                    print(f"    {col_str}: {val}")
                    has_flags = True

        if not has_flags:
            print("    (nenhuma flag ativa)")

if not found_auth:
    print("❌ NÃO ENCONTRADO em BP AUTORITY")

# Procurar em BP ALGORITIMO
print("\n[BP ALGORITIMO]")
found_alg = False
for i, row in enumerate(bp_algoritimo[1:], start=2):
    if get(row, idx_alg, "ID_USER") == "79":
        found_alg = True
        print(f"Linha {i}: {get(row, idx_alg, 'NOME')}")

if not found_alg:
    print("❌ NÃO ENCONTRADO em BP ALGORITIMO")

print("\n" + "=" * 80)
print("[PROBLEMA]")
print("=" * 80)

if found_service and not found_auth and not found_alg:
    print("✅ Victor está apenas em BP SERVICE (correto)")
elif found_service and found_auth and not found_alg:
    print("⚠️  Victor está em BP SERVICE e BP AUTORITY mas NÃO em BP ALGORITIMO")
    print("   → Inconsistência: BP AUTORITY deveria ser removida")
elif found_auth and not found_service:
    print("❌ Victor está em BP AUTORITY mas NÃO em BP SERVICE")
    print("   → Resíduo: deveria ser removido")
else:
    print("⚠️  Estado misto/indefinido")
