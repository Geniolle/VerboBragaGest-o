"""Testar delete da linha 76 de BP AUTORITY para Cleitinho."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

guard = SpreadsheetGuard(load_settings())

print("=" * 80)
print("[TEST] Tentativa de delete linha 76 BP AUTORITY (Cleitinho)")
print("=" * 80)

# Verificar estado ANTES
print("\n[ANTES]")
bp_before = guard.read_worksheet("BP AUTORITY", force_refresh=True)
linha_antes = len(bp_before)
print(f"  BP AUTORITY: {linha_antes} linhas")

# Procurar Cleitinho
found_before = False
for i, row in enumerate(bp_before[1:], start=2):
    if i == 76:  # Linha específica
        id_val = str(row[0]) if row and len(row) > 0 else ""
        nome_val = str(row[1]) if row and len(row) > 1 else ""
        print(f"  Linha 76: ID={id_val.strip()}, NOME={nome_val.strip()}")
        if id_val.strip() == "122":
            found_before = True

if found_before:
    print(f"  ✅ Cleitinho encontrado em linha 76")
else:
    print(f"  ❌ Cleitinho NÃO em linha 76")

# Tentar delete (em modo debug, sem efectuar realmente)
print("\n[TESTE DELETE]")
print(f"  Tentando: guard.delete_rows('BP AUTORITY', [76])")
print(f"  ⚠️  NÃO EXECUTANDO - apenas verificação de segurança")
print(f"  SpreadsheetGuard deveria permitir? {guard._assert_can_write('BP AUTORITY') or 'SIM'}")

print("\n" + "=" * 80)
