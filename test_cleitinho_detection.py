"""Testar se Cleitinho é detectado para remoção em calcular_plano()."""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
from scripts.Colaborador.reconciliar_cadeia_departamentos import calcular_plano

guard = SpreadsheetGuard(load_settings())

# Ler sheets
bp_service = guard.read_worksheet("BP SERVICE", force_refresh=True)
bp_autority = guard.read_worksheet("BP AUTORITY", force_refresh=True)
bp_algoritimo = guard.read_worksheet("BP ALGORITIMO", force_refresh=True)

print("=" * 80)
print("[TEST] Detecção de Cleitinho em calcular_plano()")
print("=" * 80)

# Rodar calcular_plano
plano = calcular_plano(bp_service, bp_autority, bp_algoritimo)

print(f"\nPessoas para remover: {len(plano.pessoas_remocao)}")
print(f"Pessoas para ativar: {len(plano.pessoas_ativacao)}")

# Procurar Cleitinho
cleitinho_detectado = False
for pessoa in plano.pessoas_remocao:
    if pessoa.id_user == "122" or "Cleitinho" in pessoa.nome:
        cleitinho_detectado = True
        print(f"\n✅ CLEITINHO DETECTADO PARA REMOÇÃO:")
        print(f"  ID: {pessoa.id_user}")
        print(f"  Nome: {pessoa.nome}")
        print(f"  Motivo: {pessoa.motivo}")
        break

if not cleitinho_detectado:
    print(f"\n❌ CLEITINHO NÃO DETECTADO PARA REMOÇÃO!")
    print("\nPessoas detectadas para remoção:")
    for pessoa in plano.pessoas_remocao[:5]:  # Mostrar primeiras 5
        print(f"  - ID {pessoa.id_user}: {pessoa.nome}")
    if len(plano.pessoas_remocao) > 5:
        print(f"  ... e mais {len(plano.pessoas_remocao) - 5}")

print("\n" + "=" * 80)
