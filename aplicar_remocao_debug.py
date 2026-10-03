"""Versão diagnóstica de aplicar_remocao para entender por que linha_autority=None."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
from scripts.Colaborador.reconciliar_cadeia_departamentos import (
    get, map_headers, PessoaProblema, ResultadoTransacao,
    SHEET_BP_SERVICE, SHEET_BP_AUTORITY, SHEET_BP_ALGORITIMO
)

guard = SpreadsheetGuard(load_settings())

# Ler sheets originais
bp_service = guard.read_worksheet(SHEET_BP_SERVICE, force_refresh=True)
bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY, force_refresh=True)
bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO, force_refresh=True)

idx_service = map_headers(bp_service[0])
idx_autority = map_headers(bp_autority[0])
idx_algoritimo = map_headers(bp_algoritimo[0])

# Criar pessoa de teste
pessoa = PessoaProblema("122", "Cleitinho Fubá", "remocao", "teste")

print("=" * 80)
print("[DEBUG DIAGNÓSTICO] Simulação de aplicar_remocao() para ID 122")
print("=" * 80)

print(f"\n[Entrada]")
print(f"pessoa.id_user: {repr(pessoa.id_user)}")
print(f"pessoa.nome: {repr(pessoa.nome)}")

# PASSO 1: force_refresh BP AUTORITY
print(f"\n[Etapa 1] force_refresh BP AUTORITY")
bp_autority_atual = guard.read_worksheet(SHEET_BP_AUTORITY, force_refresh=True)
idx_autority_atual = map_headers(bp_autority_atual[0])

print(f"  Tamanho: {len(bp_autority_atual)} linhas")
print(f"  Header: {list(idx_autority_atual.keys())[:5]}...")
print(f"  idx_autority_atual.get('ID_USER'): {idx_autority_atual.get('ID_USER')}")

# PASSO 2: Procurar linhas do ID_USER
print(f"\n[Etapa 2] Lookup de ID_USER={repr(pessoa.id_user)}")

linhas_autority = []
for i, row in enumerate(bp_autority_atual[1:], start=2):
    id_atual = get(row, idx_autority_atual, "ID_USER")
    nome_atual = get(row, idx_autority_atual, "NOME")

    # Debug detalhado
    if id_atual == pessoa.id_user:
        print(f"  ✅ MATCH linha {i}:")
        print(f"     ID_USER: {repr(id_atual)}")
        print(f"     NOME: {repr(nome_atual)}")
        linhas_autority.append(i)

if not linhas_autority:
    print(f"  ❌ NENHUMA LINHA ENCONTRADA")
    # Mostrar algumas amostras
    print(f"\n  Amostra de linhas (primeiras 3):")
    for i, row in enumerate(bp_autority_atual[1:4], start=2):
        id_val = get(row, idx_autority_atual, "ID_USER")
        nome_val = get(row, idx_autority_atual, "NOME")
        print(f"    Linha {i}: ID={repr(id_val)} | NOME={repr(nome_val)}")

print(f"\n[Resultado Lookup]")
print(f"  linhas_autority: {linhas_autority}")
print(f"  quantidade: {len(linhas_autority)}")

# PASSO 3: Simular o que o código actual faz
print(f"\n[Etapa 3] Lógica actual (if linha_autority:)")

# Código actual tira primeira linha
linha_autority = linhas_autority[0] if linhas_autority else None
print(f"  linha_autority = {linha_autority}")

if linha_autority:
    print(f"  ✅ Entraria no bloco de delete")
else:
    print(f"  ❌ PULARIA O BLOCO DE DELETE (SUCESSO SILENCIOSO)")

print("\n" + "=" * 80)
