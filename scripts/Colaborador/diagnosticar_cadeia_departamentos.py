"""Diagnóstico read-only da cadeia de departamentos.

Valida:
1. Mapeamento de D.* em BP SERVICE vs COLABORADOR_* em BP AUTORITY
2. Casos inconsistentes (resíduos)
3. Possíveis duplicados em BP ALGORITIMO
4. Pessoas elegíveis para ativação/remoção
"""

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard
import re

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_AUTORITY = "BP AUTORITY"
SHEET_BP_ALGORITIMO = "BP ALGORITIMO"


def map_headers(header):
    return {str(nome).strip(): i for i, nome in enumerate(header) if str(nome).strip()}


def get(row, idx, col):
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def is_true(value):
    return str(value or "").strip().lower() == "true"


def normalize_token(text):
    """Normaliza nome de departamento para comparação (remove acentos, espaços, pontuação)."""
    import unicodedata

    text = str(text or "").strip()
    if text.upper().startswith("D."):
        text = text[2:].strip()
    elif text.upper().startswith("COLABORADOR_"):
        text = text[len("COLABORADOR_"):].strip()

    # Remove acentos com NFD
    text = unicodedata.normalize("NFD", text.upper())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    # Remove não-alfanuméricos
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


def main():
    guard = SpreadsheetGuard(load_settings())
    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)
    bp_algoritimo = guard.read_worksheet(SHEET_BP_ALGORITIMO)

    idx_service = map_headers(bp_service[0])
    idx_autority = map_headers(bp_autority[0])
    idx_algoritimo = map_headers(bp_algoritimo[0])

    print("###############################################################################")
    print("[DIAGNÓSTICO] CADEIA DE DEPARTAMENTOS")
    print("###############################################################################\n")

    # 1. Analisar mapeamento de departamentos
    print("1. MAPEAMENTO DE DEPARTAMENTOS\n")

    d_colunas = [c for c in bp_service[0] if str(c).strip().upper().startswith("D.")]
    col_colunas = [c for c in bp_autority[0] if str(c).strip().upper().startswith("COLABORADOR_")]

    print(f"BP SERVICE: {len(d_colunas)} colunas D.*")
    for col in d_colunas:
        print(f"  - {col}")

    print(f"\nBP AUTORITY: {len(col_colunas)} colunas COLABORADOR_*")
    for col in col_colunas:
        print(f"  - {col}")

    # Encontrar discrepâncias
    d_tokens = {normalize_token(c): c for c in d_colunas}
    col_tokens = {normalize_token(c): c for c in col_colunas}

    faltam_em_autority = set(d_tokens.keys()) - set(col_tokens.keys())
    extras_em_autority = set(col_tokens.keys()) - set(d_tokens.keys())

    if faltam_em_autority:
        print(f"\n❌ Faltam em BP AUTORITY ({len(faltam_em_autority)}):")
        for token in sorted(faltam_em_autority):
            orig_col = d_tokens[token]
            print(f"  - {orig_col}")

    if extras_em_autority:
        print(f"\n⚠️  Extras em BP AUTORITY ({len(extras_em_autority)}):")
        for token in sorted(extras_em_autority):
            orig_col = col_tokens[token]
            print(f"  - {orig_col}")

    # 2. Casos específicos problemáticos
    print("\n" + "=" * 79)
    print("2. CASOS ESPECÍFICOS PROBLEMÁTICOS\n")

    # ID_USER 122 - Cleitinho Fubá
    for i, row in enumerate(bp_service[1:], start=2):
        if get(row, idx_service, "ID_USER") == "122":
            nome = get(row, idx_service, "NOME")
            dept_flag = get(row, idx_service, "DEPARTAMENTOS")
            bp_aut_flag = get(row, idx_service, "BP AUTORITY")
            d_ativos = [c for c in d_colunas if is_true(get(row, idx_service, c))]

            print(f"ID_USER 122: {nome}")
            print(f"  D.* ativos: {len(d_ativos)}")
            print(f"  DEPARTAMENTOS: {dept_flag if dept_flag else '(vazio)'}")
            print(f"  BP AUTORITY: {bp_aut_flag if bp_aut_flag else '(vazio)'}")

            # Verificar se existe em BP AUTORITY
            exists_autority = any(get(r, idx_autority, "ID_USER") == "122" for r in bp_autority[1:])
            print(f"  Existe em BP AUTORITY: {'SIM' if exists_autority else 'NÃO'}")

            if exists_autority:
                for j, row_aut in enumerate(bp_autority[1:], start=2):
                    if get(row_aut, idx_autority, "ID_USER") == "122":
                        col_ativos = [c for c in col_colunas if is_true(get(row_aut, idx_autority, c))]
                        print(f"  COLABORADOR_* ativos em BP AUTORITY: {len(col_ativos)}")

            print()

    # 3. Usuários com D. MULHERES, HOMENS, PASTOREIO
    print("=" * 79)
    print("3. DEPARTAMENTOS SEM CORRESPONDÊNCIA EM BP AUTORITY\n")

    dept_sem_mapping = ["D. MULHERES", "D. HOMENS", "D. PASTOREIO"]
    for dept in dept_sem_mapping:
        usuarios = []
        for i, row in enumerate(bp_service[1:], start=2):
            if is_true(get(row, idx_service, dept)):
                usuarios.append(get(row, idx_service, "NOME"))

        if usuarios:
            print(f"{dept}: {len(usuarios)} pessoa(s)")
            for nome in usuarios[:5]:  # Mostrar apenas os primeiros 5
                print(f"  - {nome}")
            if len(usuarios) > 5:
                print(f"  ... e mais {len(usuarios) - 5}")
            print()

    # 4. Possíveis duplicados em BP ALGORITIMO
    print("=" * 79)
    print("4. POSSÍVEIS DUPLICADOS EM BP ALGORITIMO\n")

    # Agrupar por ID_USER + DEPARTAMENTO
    by_id_dept = {}
    for i, row in enumerate(bp_algoritimo[1:], start=2):
        id_user = get(row, idx_algoritimo, "ID_USER")
        dept = get(row, idx_algoritimo, "DEPARTAMENTO")
        if id_user and dept:
            key = (id_user, dept)
            if key not in by_id_dept:
                by_id_dept[key] = []
            by_id_dept[key].append((i, row))

    duplicados = {k: v for k, v in by_id_dept.items() if len(v) > 1}
    if duplicados:
        print(f"Encontrados {len(duplicados)} grupo(s) com múltiplas linhas:\n")
        for (id_user, dept), linhas in sorted(duplicados.items()):
            nome = get(linhas[0][1], idx_algoritimo, "NOME")
            print(f"ID_USER={id_user}, NOME={nome}, DEPARTAMENTO={dept}")
            for linha_num, row in linhas:
                funcao = get(row, idx_algoritimo, "FUNÇÃO")
                ativo = get(row, idx_algoritimo, "ATIVO")
                print(f"  Linha {linha_num}: FUNÇÃO={funcao}, ATIVO={ativo}")
            print()

    # 5. Resumo de consistência
    print("=" * 79)
    print("5. RESUMO DE CONSISTÊNCIA\n")

    total_service = len(bp_service) - 1
    total_autority = len(bp_autority) - 1
    total_algoritimo = len(bp_algoritimo) - 1

    print(f"Total de registos:")
    print(f"  BP SERVICE: {total_service}")
    print(f"  BP AUTORITY: {total_autority}")
    print(f"  BP ALGORITIMO: {total_algoritimo}")

    print("\n✓ Análise completa (read-only, nenhuma alteração)")


if __name__ == "__main__":
    main()
