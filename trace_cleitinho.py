"""Trace read-only do estado completo de Cleitinho Fubá nas 3 sheets."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

def get_raw(row, idx, col):
    """Get valor RAW sem normalização."""
    i = idx.get(col)
    if i is None or i >= len(row):
        return None
    return row[i]  # RAW value

def get_str(row, idx, col):
    """Get valor normalizado para string."""
    val = get_raw(row, idx, col)
    return str(val).strip() if val else ""

guard = SpreadsheetGuard(load_settings())

# Ler sheets
bp_service = guard.read_worksheet("BP SERVICE", force_refresh=True)
bp_autority = guard.read_worksheet("BP AUTORITY", force_refresh=True)
bp_algoritimo = guard.read_worksheet("BP ALGORITIMO", force_refresh=True)

# Headers
idx_service = {str(v).strip(): i for i, v in enumerate(bp_service[0]) if str(v).strip()}
idx_autority = {str(v).strip(): i for i, v in enumerate(bp_autority[0]) if str(v).strip()}
idx_algoritimo = {str(v).strip(): i for i, v in enumerate(bp_algoritimo[0]) if str(v).strip()}

# Colunas D.*
d_colunas = [c for c in bp_service[0] if str(c).strip().upper().startswith("D.")]
col_colunas = [c for c in bp_autority[0] if str(c).strip().upper().startswith("COLABORADOR_")]

print("=" * 80)
print("[TRACE READ-ONLY] Cleitinho Fubá (ID_USER 122)")
print("=" * 80)

# BP SERVICE
print("\n[BP SERVICE]")
for i, row in enumerate(bp_service[1:], start=2):
    if get_str(row, idx_service, "ID_USER") == "122":
        print(f"Linha: {i}")
        print(f"  ID_USER: {get_raw(row, idx_service, 'ID_USER')}")
        print(f"  NOME: {get_str(row, idx_service, 'NOME')}")
        print(f"  DEPARTAMENTOS: {repr(get_raw(row, idx_service, 'DEPARTAMENTOS'))}")
        print(f"  BP AUTORITY: {repr(get_raw(row, idx_service, 'BP AUTORITY'))}")
        print(f"  INATIVO: {repr(get_raw(row, idx_service, 'INATIVO'))}")

        print(f"\n  Colunas D.* (valores RAW):")
        for col in d_colunas:
            raw_val = get_raw(row, idx_service, col)
            print(f"    {col}: {repr(raw_val)} (tipo: {type(raw_val).__name__})")

# BP AUTORITY
print("\n[BP AUTORITY]")
encontrado = False
for i, row in enumerate(bp_autority[1:], start=2):
    if get_str(row, idx_autority, "ID_USER") == "122":
        encontrado = True
        print(f"Linha: {i}")
        print(f"  ID_USER: {get_raw(row, idx_autority, 'ID_USER')}")
        print(f"  NOME: {get_str(row, idx_autority, 'NOME')}")

        print(f"\n  Colunas COLABORADOR_* (valores RAW):")
        for col in col_colunas:
            raw_val = get_raw(row, idx_autority, col)
            print(f"    {col}: {repr(raw_val)} (tipo: {type(raw_val).__name__})")

if not encontrado:
    print("  (não encontrado em BP AUTORITY)")

# BP ALGORITIMO
print("\n[BP ALGORITIMO]")
encontrado_algo = False
for i, row in enumerate(bp_algoritimo[1:], start=2):
    if get_str(row, idx_algoritimo, "ID_USER") == "122":
        encontrado_algo = True
        dept = get_str(row, idx_algoritimo, "DEPARTAMENTO")
        funcao = get_str(row, idx_algoritimo, "FUNÇÃO")
        ativo = get_raw(row, idx_algoritimo, "ATIVO")
        print(f"Linha: {i}")
        print(f"  DEPARTAMENTO: {dept}")
        print(f"  FUNÇÃO: {funcao}")
        print(f"  ATIVO: {repr(ativo)} (tipo: {type(ativo).__name__})")

if not encontrado_algo:
    print("  (não encontrado em BP ALGORITIMO)")

print("\n" + "=" * 80)
print("[RESUMO]")
print("=" * 80)
print(f"BP SERVICE: DEPARTAMENTOS = {repr(get_raw([row for row in bp_service[1:] if get_str(row, idx_service, 'ID_USER') == '122'][0], idx_service, 'DEPARTAMENTOS'))}")
print(f"BP AUTORITY: {'SIM - linha encontrada' if encontrado else 'NÃO - linha não encontrada'}")
print(f"BP ALGORITIMO: {'SIM - {n} linha(s) encontrada(s)'.format(n=len([1 for row in bp_algoritimo[1:] if get_str(row, idx_algoritimo, 'ID_USER') == '122'])) if encontrado_algo else 'NÃO'}")
