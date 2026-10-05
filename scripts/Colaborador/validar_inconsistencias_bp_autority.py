"""Validação isolada de inconsistências em BP AUTORITY.

Detecta:
1. Linhas em BP AUTORITY sem departamento correspondente em BP SERVICE
2. Linhas em BP AUTORITY com flags ativas mas pessoa inativa
3. Divergências de ID_USER entre BP AUTORITY e BP SERVICE
"""

from __future__ import annotations

from pastoreio_orquestrador.config import load_settings
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

SHEET_BP_SERVICE = "BP SERVICE"
SHEET_BP_AUTORITY = "BP AUTORITY"

COL_ID_USER = "ID_USER"
COL_NOME = "NOME"
COL_INATIVO = "INATIVO"
COL_TYPE = "TYPE"


def map_headers(header: list[str]) -> dict[str, int]:
    return {str(value).strip(): i for i, value in enumerate(header) if str(value).strip()}


def get(row: list[str], idx: dict[str, int], col: str) -> str:
    i = idx.get(col)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def is_true(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() == "true"


def main() -> None:
    settings = load_settings()
    guard = SpreadsheetGuard(settings)

    print("###############################################################################")
    print("[BP AUTORITY] VALIDACAO ISOLADA DE INCONSISTENCIAS")
    print("###############################################################################")

    bp_service = guard.read_worksheet(SHEET_BP_SERVICE)
    bp_autority = guard.read_worksheet(SHEET_BP_AUTORITY)

    if not bp_service or not bp_autority:
        print("❌ Sheets vazias ou ausentes")
        return

    idx_service = map_headers(bp_service[0])
    idx_autority = map_headers(bp_autority[0])

    # Construir mapa de IDs em BP SERVICE
    service_by_id = {}
    for i, row in enumerate(bp_service[1:], start=2):
        id_user = get(row, idx_service, COL_ID_USER)
        if id_user:
            service_by_id[id_user] = (i, row)

    # Detectar inconsistências
    inconsistencias = []
    sem_departamento = []
    inativo_com_flags = []
    id_divergente = []

    print("\nVARREDURA DE BP AUTORITY...")
    print(f"Total de linhas em BP AUTORITY: {len(bp_autority) - 1}")

    for linha, row in enumerate(bp_autority[1:], start=2):
        id_user = get(row, idx_autority, COL_ID_USER)
        nome = get(row, idx_autority, COL_NOME)

        if not id_user:
            continue

        # Verificar se existe em BP SERVICE
        service_info = service_by_id.get(id_user)
        if not service_info:
            sem_departamento.append((linha, id_user, nome))
            continue

        service_linha, service_row = service_info
        service_id = get(service_row, idx_service, COL_ID_USER)
        service_nome = get(service_row, idx_service, COL_NOME)

        # Verificar divergência de ID
        if service_id != id_user:
            id_divergente.append((linha, id_user, service_id, nome))
            continue

        # Verificar se tem D.* ativo em BP SERVICE
        tem_departamento = False
        for col in bp_service[0]:
            col_str = str(col).strip()
            if col_str.upper().startswith("D."):
                if is_true(get(service_row, idx_service, col_str)):
                    tem_departamento = True
                    break

        if not tem_departamento:
            # Pessoa em BP AUTORITY mas sem D.* em BP SERVICE
            # Verificar se tem flags ativas
            tem_flags = False
            for col in bp_autority[0]:
                col_str = str(col).strip()
                if col_str.upper().startswith("COLABORADOR_"):
                    if is_true(get(row, idx_autority, col_str)):
                        tem_flags = True
                        break

            if tem_flags:
                inativo_com_flags.append((linha, id_user, nome))
                inconsistencias.append(f"Linha {linha}: {nome} (ID {id_user}) tem flags COLABORADOR_* mas nenhum D.* em BP SERVICE")

    print("\n###############################################################################")
    print("[RESULTADO] INCONSISTENCIAS ENCONTRADAS")
    print("###############################################################################")

    print(f"\n1. Linhas sem departamento em BP SERVICE (mas com flags em BP AUTORITY):")
    if inativo_com_flags:
        print(f"   Total: {len(inativo_com_flags)}")
        for linha, id_user, nome in inativo_com_flags[:10]:  # Mostrar primeiras 10
            print(f"   Linha {linha}: {nome} (ID {id_user})")
        if len(inativo_com_flags) > 10:
            print(f"   ... e mais {len(inativo_com_flags) - 10}")
    else:
        print("   ✅ Nenhuma")

    print(f"\n2. Linhas em BP AUTORITY sem correspondente em BP SERVICE:")
    if sem_departamento:
        print(f"   Total: {len(sem_departamento)}")
        for linha, id_user, nome in sem_departamento[:10]:
            print(f"   Linha {linha}: {nome} (ID {id_user})")
        if len(sem_departamento) > 10:
            print(f"   ... e mais {len(sem_departamento) - 10}")
    else:
        print("   ✅ Nenhuma")

    print(f"\n3. Divergência de ID_USER entre BP AUTORITY e BP SERVICE:")
    if id_divergente:
        print(f"   Total: {len(id_divergente)}")
        for linha, id_autority, id_service, nome in id_divergente[:10]:
            print(f"   Linha {linha}: {nome} | ID BP AUTORITY={id_autority} | ID BP SERVICE={id_service}")
        if len(id_divergente) > 10:
            print(f"   ... e mais {len(id_divergente) - 10}")
    else:
        print("   ✅ Nenhuma")

    print("\n###############################################################################")
    print(f"[RESUMO] Total de inconsistências: {len(inconsistencias)}")
    print("###############################################################################")

    if inconsistencias:
        print("\n⚠️  INCONSISTENCIAS DETECTADAS - REQUER ACAO")
        for msg in inconsistencias[:5]:
            print(f"   {msg}")
    else:
        print("\n✅ Nenhuma inconsistência detectada")


if __name__ == "__main__":
    main()
