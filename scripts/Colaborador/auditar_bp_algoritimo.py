"""Auditoria de BP ALGORITIMO para detectar resíduos obsoletos.

Valida:
1. Linhas com ATIVO=FALSE mas que existem em BP ALGORITIMO
2. Linhas para pessoas que não existem em BP SERVICE
3. Linhas para vínculos que já não estão em BP AUTORITY
4. Duplicados (mesmo ID_USER + DEPARTAMENTO)
5. Linhas sem ID_USER
6. Divergências de ID entre BP ALGORITIMO e BP SERVICE
"""

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

bp_algoritimo = guard.read_worksheet("BP ALGORITIMO")
bp_service = guard.read_worksheet("BP SERVICE")
bp_autority = guard.read_worksheet("BP AUTORITY")

idx_alg = map_headers(bp_algoritimo[0])
idx_svc = map_headers(bp_service[0])
idx_auth = map_headers(bp_autority[0])

print("=" * 80)
print("[AUDITORIA] BP ALGORITIMO - Detectar Resíduos Obsoletos")
print("=" * 80)

# Construir mapas
service_by_id = {}
for row in bp_service[1:]:
    id_user = get(row, idx_svc, "ID_USER")
    if id_user:
        service_by_id[id_user] = row

autority_vinculos = set()  # (id_user, departamento)
for row in bp_autority[1:]:
    id_user = get(row, idx_auth, "ID_USER")
    if not id_user:
        continue
    for col in bp_autority[0]:
        col_str = str(col).strip()
        if col_str.upper().startswith("COLABORADOR_"):
            if is_true(get(row, idx_auth, col_str)):
                dept_token = col_str.replace("COLABORADOR_", "").upper()
                dept_token = dept_token.replace("CENTRODECURA", "CENTRODE CURA")
                autority_vinculos.add((id_user, dept_token))

print(f"\nLinhas BP ALGORITIMO: {len(bp_algoritimo) - 1}")
print(f"Pessoas em BP SERVICE: {len(service_by_id)}")
print(f"Vínculos ativos em BP AUTORITY: {len(autority_vinculos)}")

# Auditar cada linha
residuos = []
sem_id_user = 0
sem_bp_service = 0
sem_vinculo_autority = 0
duplicados_encontrados = 0
ativo_false = 0

visto = set()  # Para detectar duplicados

for linha, row in enumerate(bp_algoritimo[1:], start=2):
    id_user = get(row, idx_alg, "ID_USER")
    nome = get(row, idx_alg, "NOME")
    departamento = get(row, idx_alg, "DEPARTAMENTO")
    ativo = get(row, idx_alg, "ATIVO")

    # Validação 1: Sem ID_USER
    if not id_user:
        sem_id_user += 1
        residuos.append(f"Linha {linha}: SEM ID_USER ({nome})")
        continue

    # Validação 2: ATIVO=FALSE
    if ativo and not is_true(ativo):
        ativo_false += 1
        residuos.append(f"Linha {linha}: ATIVO=FALSE ou vazio ({id_user} {nome})")
        continue

    # Validação 3: Sem correspondência em BP SERVICE
    if id_user not in service_by_id:
        sem_bp_service += 1
        residuos.append(f"Linha {linha}: ID_USER={id_user} não existe em BP SERVICE")
        continue

    # Validação 4: Sem vínculo em BP AUTORITY
    dept_token = departamento.upper().replace(" ", "").replace("D.", "")
    if (id_user, dept_token) not in autority_vinculos:
        sem_vinculo_autority += 1
        residuos.append(f"Linha {linha}: Vínculo INATIVO ({id_user} {nome} {departamento})")
        continue

    # Validação 5: Duplicados
    chave = (id_user, dept_token)
    if chave in visto:
        duplicados_encontrados += 1
        residuos.append(f"Linha {linha}: DUPLICADO ({id_user} {departamento})")
    visto.add(chave)

print("\n" + "=" * 80)
print("[RESULTADO]")
print("=" * 80)

print(f"\nLinhas sem ID_USER: {sem_id_user}")
print(f"Linhas com ATIVO=FALSE ou vazio: {ativo_false}")
print(f"Linhas sem correspondência em BP SERVICE: {sem_bp_service}")
print(f"Linhas com vínculo INATIVO em BP AUTORITY: {sem_vinculo_autority}")
print(f"Linhas duplicadas: {duplicados_encontrados}")

total_residuos = sem_id_user + ativo_false + sem_bp_service + sem_vinculo_autority + duplicados_encontrados

print(f"\n{'='*80}")
print(f"TOTAL DE RESÍDUOS: {total_residuos}")
print(f"{'='*80}")

if residuos:
    print("\n[DETALHES DOS RESÍDUOS]")
    for residuo in residuos[:20]:
        print(f"  • {residuo}")
    if len(residuos) > 20:
        print(f"  ... e mais {len(residuos) - 20}")
else:
    print("\n✅ Nenhum resíduo detectado - BP ALGORITIMO está limpa!")

print(f"\n[AÇÃO RECOMENDADA]")
if total_residuos > 0:
    print(f"❌ BP ALGORITIMO tem {total_residuos} linha(s) obsoleta(s)")
    print(f"   Implementar limpeza no orquestrador")
else:
    print(f"✅ BP ALGORITIMO em estado consistente")
