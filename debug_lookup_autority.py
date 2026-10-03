"""Debug do lookup de BP AUTORITY para ID 122."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
from scripts.Colaborador.reconciliar_cadeia_departamentos import get, map_headers

guard = SpreadsheetGuard(load_settings())

bp_autority = guard.read_worksheet("BP AUTORITY", force_refresh=True)
idx_autority = map_headers(bp_autority[0])

print("=" * 80)
print("[DEBUG] Lookup de BP AUTORITY para ID_USER='122'")
print("=" * 80)

print(f"\nTamanho BP AUTORITY: {len(bp_autority)} linhas (1 header + {len(bp_autority)-1} dados)")
print(f"Índices de header: {list(idx_autority.keys())[:5]}...")

# Procurar manualmente
print("\n[Procura manual]")
print("Linhas com ID_USER = '122':")

encontrado = False
for i, row in enumerate(bp_autority[1:], start=2):
    id_val = get(row, idx_autority, "ID_USER")

    # Debugging
    if i <= 5 or i >= len(bp_autority) - 3:  # Mostrar primeiras e últimas
        print(f"  Linha {i}: ID_USER={repr(id_val)} | Comparação: {id_val == '122'}")

    if id_val == "122":
        encontrado = True
        nome = get(row, idx_autority, "NOME")
        print(f"\n✅ ENCONTRADA LINHA {i}:")
        print(f"  ID_USER: {repr(id_val)}")
        print(f"  NOME: {repr(nome)}")

if not encontrado:
    print("\n❌ NENHUMA LINHA ENCONTRADA COM ID_USER='122'")

# Verificar se há o ID usando outros métodos
print("\n[Verificação alternativa]")
print("Linhas que contêm '122' em qualquer coluna:")
for i, row in enumerate(bp_autority[1:], start=2):
    row_str = ' '.join(str(v) for v in row)
    if '122' in row_str:
        print(f"  Linha {i}: {row[:3]}")  # Mostrar primeiras 3 colunas
        break
