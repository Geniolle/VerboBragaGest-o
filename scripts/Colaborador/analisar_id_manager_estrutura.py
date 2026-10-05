"""Analisar estrutura e dados reais de ID_MANAGER e BP AUTORITY"""

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
    return str(value or "").strip().lower() == "true"

settings = load_settings()
guard = SpreadsheetGuard(settings)

bp_autority = guard.read_worksheet("BP AUTORITY")
id_manager = guard.read_worksheet("ID_MANAGER")

idx_auth = map_headers(bp_autority[0])
idx_manager = map_headers(id_manager[0])

print("=" * 80)
print("[ANÁLISE ESTRUTURAL] ID_MANAGER e BP AUTORITY")
print("=" * 80)

print("\n[BP AUTORITY]")
print(f"Linhas de dados: {len(bp_autority) - 1}")
print(f"Headers: {list(bp_autority[0])}")

# Encontrar colunas MANAGER_*
manager_cols = [col for col in bp_autority[0] if str(col).strip().upper().startswith("MANAGER_")]
print(f"\nColunas MANAGER_* encontradas: {len(manager_cols)}")
for col in sorted(manager_cols):
    print(f"  • {col}")

print("\n[ID_MANAGER]")
print(f"Linhas de dados: {len(id_manager) - 1}")
print(f"Headers: {list(id_manager[0])}")

# Validar campos esperados
print(f"\n[VALIDAÇÃO - Campos esperados]")
campos_esperados = ["DEPARTAMENTOS", "NOME", "TELEFONE", "EMAIL"]
for campo in campos_esperados:
    if campo in idx_manager:
        print(f"  ✅ {campo}")
    else:
        print(f"  ❌ {campo} NÃO ENCONTRADO")

# Listar alguns registros de ID_MANAGER para padrão
print(f"\n[AMOSTRA - ID_MANAGER (primeiras 5 linhas)]")
for i, row in enumerate(id_manager[1:6], start=2):
    dept = get(row, idx_manager, "DEPARTAMENTOS")
    nome = get(row, idx_manager, "NOME")
    print(f"  Linha {i}: {dept:20} | {nome}")

# Contar registros MANAGER_ ativos em BP AUTORITY
print(f"\n[CONTAGEM - MANAGER_ ativos em BP AUTORITY]")
total_manager_entries = 0
for row in bp_autority[1:]:
    for col in manager_cols:
        if is_true(get(row, idx_auth, col)):
            total_manager_entries += 1

print(f"Total de vínculos MANAGER_=TRUE: {total_manager_entries}")

# Amostra de pessoas com MANAGER_
print(f"\n[AMOSTRA - Pessoas com MANAGER_=TRUE (primeiras 5)]")
count = 0
for i, row in enumerate(bp_autority[1:], start=2):
    nome = get(row, idx_auth, "NOME")
    if not nome:
        continue

    has_manager = False
    managers = []
    for col in manager_cols:
        if is_true(get(row, idx_auth, col)):
            has_manager = True
            dept = col.replace("MANAGER_", "D. ").strip()
            managers.append(dept)

    if has_manager:
        print(f"  Linha {i}: {nome:20} | {', '.join(managers[:3])}")
        count += 1
        if count >= 5:
            break

print("\n" + "=" * 80)
