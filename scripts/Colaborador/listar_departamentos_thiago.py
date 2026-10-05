"""Listar TODOS os departamentos de Thiago Rocha em BP SERVICE"""

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
idx_svc = map_headers(bp_service[0])

print("=" * 80)
print("[THIAGO ROCHA] DEPARTAMENTOS ATRIBUIDOS EM BP SERVICE")
print("=" * 80)

# Encontrar Thiago Rocha
thiago_row = None
thiago_id = None

for i, row in enumerate(bp_service[1:], start=2):
    nome = get(row, idx_svc, "NOME")
    if "thiago" in nome.lower() and "rocha" in nome.lower():
        thiago_row = row
        thiago_id = get(row, idx_svc, "ID_USER")
        break

if not thiago_row:
    print("❌ Thiago Rocha não encontrado")
    exit(1)

print(f"\nNome: {get(thiago_row, idx_svc, 'NOME')}")
print(f"ID_USER: {thiago_id}")
print(f"Linha: {i}")

# Listar TODOS os D.*
print("\n" + "=" * 80)
print("[D.* DEPARTAMENTOS]")
print("=" * 80)

departamentos_ativos = []
departamentos_inativos = []

for col_header in bp_service[0]:
    col_str = str(col_header).strip()
    if col_str.upper().startswith("D."):
        valor = get(thiago_row, idx_svc, col_str)

        # Extrair nome do departamento
        dept_nome = col_str[3:].strip() if len(col_str) > 3 else col_str

        if is_true(valor):
            departamentos_ativos.append(dept_nome)
            print(f"✅ {col_str:40} = TRUE")
        elif valor:
            departamentos_inativos.append(f"{dept_nome} ({valor})")
            print(f"⚪ {col_str:40} = {valor}")
        else:
            print(f"❌ {col_str:40} = (vazio)")

print("\n" + "=" * 80)
print("[RESUMO]")
print("=" * 80)

print(f"\nDepartamentos ATIVOS (TRUE): {len(departamentos_ativos)}")
for dept in departamentos_ativos:
    print(f"  ✅ {dept}")

if departamentos_inativos:
    print(f"\nDepartamentos com outros valores: {len(departamentos_inativos)}")
    for dept in departamentos_inativos:
        print(f"  ⚪ {dept}")

print(f"\nTotal de colunas D.*: {len([c for c in bp_service[0] if str(c).strip().upper().startswith('D.')])}")

# Validar consistência
print("\n" + "=" * 80)
print("[CONSISTÊNCIA]")
print("=" * 80)

departamentos_flag = is_true(get(thiago_row, idx_svc, "DEPARTAMENTOS"))
bp_autority_flag = is_true(get(thiago_row, idx_svc, "BP AUTORITY"))

print(f"DEPARTAMENTOS flag: {get(thiago_row, idx_svc, 'DEPARTAMENTOS')}")
print(f"BP AUTORITY flag: {get(thiago_row, idx_svc, 'BP AUTORITY')}")

if len(departamentos_ativos) > 0:
    if departamentos_flag:
        print("✅ DEPARTAMENTOS=TRUE está correto (tem D.* ativo)")
    else:
        print("⚠️  DEPARTAMENTOS deveria ser TRUE (tem D.* ativo)")

    if bp_autority_flag:
        print("✅ BP AUTORITY=TRUE está correto (tem D.* ativo)")
    else:
        print("⚠️  BP AUTORITY deveria ser TRUE (tem D.* ativo)")
else:
    if not departamentos_flag:
        print("✅ DEPARTAMENTOS vazio/FALSE está correto (sem D.* ativo)")
    else:
        print("❌ DEPARTAMENTOS deveria estar vazio/FALSE (sem D.* ativo)")
