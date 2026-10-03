"""Auditoria RAW de formato de ID_USER para Cleitinho (ID 122)."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

def show_raw_value(label, value):
    """Mostrar valor RAW com type e repr."""
    print(f"{label}:")
    print(f"  repr(): {repr(value)}")
    print(f"  type: {type(value).__name__}")
    print(f"  str(): {str(value)}")
    print(f"  ==122: {value == 122}")
    print(f"  =='122': {value == '122'}")
    if isinstance(value, str):
        print(f"  .strip(): {repr(value.strip())}")

guard = SpreadsheetGuard(load_settings())

bp_service = guard.read_worksheet("BP SERVICE", force_refresh=True)
bp_autority = guard.read_worksheet("BP AUTORITY", force_refresh=True)
bp_algoritimo = guard.read_worksheet("BP ALGORITIMO", force_refresh=True)

print("=" * 80)
print("[AUDITORIA RAW] ID_USER Format - Cleitinho Fubá")
print("=" * 80)

# Headers
idx_service = {str(v).strip(): i for i, v in enumerate(bp_service[0]) if str(v).strip()}
idx_autority = {str(v).strip(): i for i, v in enumerate(bp_autority[0]) if str(v).strip()}
idx_algoritimo = {str(v).strip(): i for i, v in enumerate(bp_algoritimo[0]) if str(v).strip()}

# BP SERVICE
print("\n[BP SERVICE - ID_USER 122]")
for i, row in enumerate(bp_service[1:], start=2):
    id_idx = idx_service.get("ID_USER")
    if id_idx is None or id_idx >= len(row):
        continue

    id_val = row[id_idx]

    # Verificar se é o Cleitinho
    nome_idx = idx_service.get("NOME")
    if nome_idx and nome_idx < len(row):
        nome = str(row[nome_idx]).strip() if row[nome_idx] else ""
        if "Cleitinho" in nome or "122" in str(id_val):
            print(f"Linha {i}: {nome}")
            show_raw_value("  ID_USER", id_val)

            dept_idx = idx_service.get("DEPARTAMENTOS")
            if dept_idx and dept_idx < len(row):
                show_raw_value("  DEPARTAMENTOS", row[dept_idx])

            bp_auth_idx = idx_service.get("BP AUTORITY")
            if bp_auth_idx and bp_auth_idx < len(row):
                show_raw_value("  BP AUTORITY", row[bp_auth_idx])

# BP AUTORITY
print("\n[BP AUTORITY - Procurar ID_USER 122]")
encontrado_autority = False
for i, row in enumerate(bp_autority[1:], start=2):
    id_idx = idx_autority.get("ID_USER")
    if id_idx is None or id_idx >= len(row):
        continue

    id_val = row[id_idx]

    # Verificar se é o Cleitinho
    nome_idx = idx_autority.get("NOME")
    if nome_idx and nome_idx < len(row):
        nome = str(row[nome_idx]).strip() if row[nome_idx] else ""

        # Comparações para encontrar
        id_str = str(id_val).strip() if id_val else ""
        nome_match = "Cleitinho" in nome
        id_match = (id_str == "122" or str(id_val) == "122" or id_val == 122)

        if nome_match or id_match:
            encontrado_autority = True
            print(f"Linha {i}: {nome}")
            show_raw_value("  ID_USER", id_val)

if not encontrado_autority:
    print("  (Não encontrado em BP AUTORITY)")

# BP ALGORITIMO
print("\n[BP ALGORITIMO - Procurar ID_USER 122]")
encontrado_algo = False
for i, row in enumerate(bp_algoritimo[1:], start=2):
    id_idx = idx_algoritimo.get("ID_USER")
    if id_idx is None or id_idx >= len(row):
        continue

    id_val = row[id_idx]
    id_str = str(id_val).strip() if id_val else ""

    if id_str == "122" or str(id_val) == "122" or id_val == 122:
        encontrado_algo = True
        print(f"Linha {i}: encontrada")
        show_raw_value("  ID_USER", id_val)

if not encontrado_algo:
    print("  (Não encontrado em BP ALGORITIMO)")

print("\n" + "=" * 80)
print("[RESUMO]")
print("=" * 80)
print(f"BP SERVICE: ID_USER encontrado e mostrado")
print(f"BP AUTORITY: {'Encontrado (PROBLEMA!)' if encontrado_autority else 'Não encontrado (OK)'}")
print(f"BP ALGORITIMO: {'Encontrado (PROBLEMA!)' if encontrado_algo else 'Não encontrado (OK)'}")
