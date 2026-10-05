"""Validar colunas COLABORADOR_* esperadas para Thiago Rocha em BP AUTORITY"""

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

# Mapeamento D.* → COLABORADOR_*
MAPEAMENTO_DEPARTAMENTOS = {
    "D. MINISTROS": "COLABORADOR_MINISTROS",
    "D. AUXILIAR": "COLABORADOR_AUXILIAR",
    "D. RECADOS": "COLABORADOR_RECADOS",
    "D. ORAÇÃO": "COLABORADOR_ORACAO",
    "D. CENTRO DE CURA": "COLABORADOR_CENTRODECURA",
    "D. COMUNICAÇÃO": "COLABORADOR_COMUNICACAO",
    "D. CRIANÇAS": "COLABORADOR_CRIANCAS",
    "D. DIACONATO": "COLABORADOR_DIACONATO",
    "D. LOUVOR": "COLABORADOR_LOUVOR",
    "D. TESOURARIA": "COLABORADOR_TESOURARIA",
    "D. VERBOCAFE": "COLABORADOR_VERBOCAFE",
    "D. VERBOSHOP": "COLABORADOR_VERBOSHOP",
    "D. CASAIS": "COLABORADOR_CASAIS",
    "D. HOMENS": "COLABORADOR_HOMENS",
    "D. MULHERES": "COLABORADOR_MULHERES",
    "D. JOVENS": "COLABORADOR_JOVENS",
    "D. COMPRAS": "COLABORADOR_COMPRAS",
    "D. DISCIPULADO": "COLABORADOR_DISCIPULADO",
    "D. PASTOREIO": "COLABORADOR_PASTOREIO",
}

settings = load_settings()
guard = SpreadsheetGuard(settings)

bp_service = guard.read_worksheet("BP SERVICE")
bp_autority = guard.read_worksheet("BP AUTORITY")

idx_svc = map_headers(bp_service[0])
idx_auth = map_headers(bp_autority[0])

print("=" * 80)
print("[THIAGO ROCHA] VALIDAÇÃO DE COLUNAS EM BP AUTORITY")
print("=" * 80)

# Encontrar Thiago em BP SERVICE
thiago_service_row = None
thiago_id = None

for i, row in enumerate(bp_service[1:], start=2):
    nome = get(row, idx_svc, "NOME")
    if "thiago" in nome.lower() and "rocha" in nome.lower():
        thiago_service_row = row
        thiago_id = get(row, idx_svc, "ID_USER")
        break

if not thiago_service_row:
    print("❌ Thiago Rocha não encontrado em BP SERVICE")
    exit(1)

# Encontrar Thiago em BP AUTORITY
thiago_auth_row = None
thiago_auth_linha = None

for i, row in enumerate(bp_autority[1:], start=2):
    if get(row, idx_auth, "ID_USER") == thiago_id:
        thiago_auth_row = row
        thiago_auth_linha = i
        break

if not thiago_auth_row:
    print(f"❌ Thiago Rocha (ID {thiago_id}) não encontrado em BP AUTORITY")
    exit(1)

print(f"\nThiago Rocha (ID {thiago_id})")
print(f"BP SERVICE linha: {i}")
print(f"BP AUTORITY linha: {thiago_auth_linha}")

# Determinar quais departamentos estão ATIVOS
depts_ativos = []
for col_header in bp_service[0]:
    col_str = str(col_header).strip()
    if col_str.upper().startswith("D."):
        if is_true(get(thiago_service_row, idx_svc, col_str)):
            depts_ativos.append(col_str)

print(f"\n[DEPARTAMENTOS ATIVOS EM BP SERVICE]")
for dept in depts_ativos:
    print(f"  ✅ {dept}")

# Calcular quais COLABORADOR_* deveriam estar TRUE
esperado_colaborador = []
for dept in depts_ativos:
    if dept in MAPEAMENTO_DEPARTAMENTOS:
        esperado_colaborador.append(MAPEAMENTO_DEPARTAMENTOS[dept])

print(f"\n[COLUNAS ESPERADAS EM BP AUTORITY]")
print(f"Baseado em D.* ativo, Thiago deveria estar com TRUE em:")
for col in esperado_colaborador:
    print(f"  ✅ {col}")

# Verificar o estado ACTUAL em BP AUTORITY
print(f"\n[ESTADO ACTUAL EM BP AUTORITY LINHA {thiago_auth_linha}]")

estado_colaborador = {}
for col_header in bp_autority[0]:
    col_str = str(col_header).strip()
    if col_str.upper().startswith("COLABORADOR_"):
        valor = get(thiago_auth_row, idx_auth, col_str)
        estado_colaborador[col_str] = valor

print(f"\nTodas as colunas COLABORADOR_*:")
for col, valor in sorted(estado_colaborador.items()):
    if is_true(valor):
        print(f"  ✅ {col:40} = TRUE")
    elif valor:
        print(f"  ⚪ {col:40} = {valor}")
    else:
        print(f"  ❌ {col:40} = (vazio)")

# VALIDAÇÃO
print("\n" + "=" * 80)
print("[VALIDAÇÃO]")
print("=" * 80)

print(f"\nEsperado em BP AUTORITY: {len(esperado_colaborador)} colunas TRUE")
for col in esperado_colaborador:
    print(f"  • {col}")

print(f"\nAtual em BP AUTORITY:")
atual_true = [col for col, val in estado_colaborador.items() if is_true(val)]
print(f"  {len(atual_true)} colunas TRUE")
for col in atual_true:
    print(f"  • {col}")

# Comparar
faltam = set(esperado_colaborador) - set(atual_true)
sobrando = set(atual_true) - set(esperado_colaborador)

print("\n[RESULTADO]")
if not faltam and not sobrando:
    print("✅ SINCRONIZAÇÃO PERFEITA")
    print("   Todas as colunas esperadas estão TRUE")
    print("   Nenhuma coluna extra está TRUE")
else:
    if faltam:
        print(f"❌ COLUNAS FALTANDO (devem ser TRUE, mas não estão):")
        for col in faltam:
            print(f"   • {col}")

    if sobrando:
        print(f"⚠️  COLUNAS EXTRAS (estão TRUE, mas não deveriam):")
        for col in sobrando:
            print(f"   • {col}")
