"""Simular transação completa de remoção para Cleitinho (sem alterar dados reais)."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
from scripts.Colaborador.reconciliar_cadeia_departamentos import (
    get, map_headers, PessoaProblema, ResultadoTransacao,
    calcular_plano, aplicar_remocao,
    SHEET_BP_SERVICE, SHEET_BP_AUTORITY, SHEET_BP_ALGORITIMO
)

guard = SpreadsheetGuard(load_settings())

# Ler estado actual
bp_service = guard.read_worksheet(SHEET_BP_SERVICE, force_refresh=True)
bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY, force_refresh=True)
bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO, force_refresh=True)

print("=" * 80)
print("[TESTE] Simulação de remocao transacional para Cleitinho (ID 122)")
print("=" * 80)

# Calcular plano
plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

print(f"\nPessoas para remover: {len(plano.pessoas_remocao)}")

# Encontrar Cleitinho
cleitinho = None
for pessoa in plano.pessoas_remocao:
    if pessoa.id_user == "122":
        cleitinho = pessoa
        break

if not cleitinho:
    print("❌ Cleitinho não encontrado no plano!")
    exit(1)

print(f"\nCleitinho encontrado: {cleitinho.nome} (ID {cleitinho.id_user})")
print(f"Motivo: {cleitinho.motivo}")

# Simular aplicar_remocao (sem efectuar)
print("\n[Simulando aplicar_remocao()]")
print(f"  pessoa.id_user: {repr(cleitinho.id_user)}")

# Map headers
idx_service = map_headers(bp_service[0])
idx_autority = map_headers(bp_autority[0])
idx_algoritimo = map_headers(bp_algoritimo[0])

# Passo 1: Procurar em BP AUTORITY COM FORCE REFRESH
print(f"\n  Passo 1: force_refresh BP AUTORITY")
bp_autority_check = guard.read_worksheet(SHEET_BP_AUTORITY, force_refresh=True)
idx_autority_check = map_headers(bp_autority_check[0])

encontrado_autority = None
for i, row in enumerate(bp_autority_check[1:], start=2):
    id_val = get(row, idx_autority_check, "ID_USER")
    if id_val == cleitinho.id_user:
        encontrado_autority = i
        nome_val = get(row, idx_autority_check, "NOME")
        print(f"    ✅ Encontrada linha {i}: {nome_val}")
        break

if not encontrado_autority:
    print(f"    ❌ Não encontrada (linha_autority=None) - SUCESSO SILENCIOSO!")
else:
    print(f"    ✅ Linha encontrada: {encontrado_autority}")

print("\n" + "=" * 80)
print("[CONCLUSÃO]")
print(f"Cleitinho em BP AUTORITY: {'SIM (linha {})'.format(encontrado_autority) if encontrado_autority else 'NÃO ENCONTRADA'}")
print(f"Motivo do problema: {'force_refresh não funciona?' if not encontrado_autority else 'Outra causa'}")
