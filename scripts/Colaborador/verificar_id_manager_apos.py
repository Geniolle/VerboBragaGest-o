"""Verificar estado de ID_MANAGER após sincronização"""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

def map_headers(header):
    return {str(value).strip(): i for i, value in enumerate(header) if str(value).strip()}

def get(row, idx, col):
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()

settings = load_settings()
guard = SpreadsheetGuard(settings)

id_manager = guard.read_worksheet("ID_MANAGER")
idx_manager = map_headers(id_manager[0])

print("=" * 80)
print("[PÓS-SINCRONIZAÇÃO] Estado de ID_MANAGER")
print("=" * 80)

print(f"\nTotal de registros: {len(id_manager) - 1}")

print("\n[TODOS OS REGISTROS]")
print(f"{'Linha':>6} | {'DEPARTAMENTOS':20} | {'NOME':30} | {'EMAIL':35}")
print("-" * 110)

for i, row in enumerate(id_manager[1:], start=2):
    dept = get(row, idx_manager, "DEPARTAMENTOS")
    nome = get(row, idx_manager, "NOME")
    email = get(row, idx_manager, "EMAIL")
    print(f"{i:>6} | {dept:20} | {nome:30} | {email:35}")

print("\n" + "=" * 80)
print("[VERIFICAÇÃO]")
print("=" * 80)

# Contar por departamento
depts = {}
for row in id_manager[1:]:
    dept = get(row, idx_manager, "DEPARTAMENTOS")
    if dept:
        depts[dept] = depts.get(dept, 0) + 1

print("\nRegistros por departamento:")
for dept in sorted(depts.keys()):
    print(f"  {dept:20} : {depts[dept]:2} registro(s)")

print(f"\nTotal: {sum(depts.values())} registros")
