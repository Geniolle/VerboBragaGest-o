"""Politicas puras do contexto DOMINGO.

Este modulo separa conceitos que antes ficavam implicitos no motor: intencao
da vaga, obrigacao mensal e transicao do cursor de hierarquia normal.
"""

from __future__ import annotations

from pastoreio_orquestrador.domain.common.decisions import AllocationIntent


MOTIVO_CEIA = "CEIA ALTERNADA"
MOTIVO_NORMAL = "ALOCAÇÃO NORMAL"
MOTIVO_NORMAL_RODIZIO_QUEBRADO = "ALOCAÇÃO NORMAL (RODÍZIO QUEBRADO P/ FECHAR LACUNA)"
MOTIVO_RESGATE = "RESGATE"
MOTIVO_LACUNA = "PREENCHIMENTO DE LACUNA"
MOTIVO_REORGANIZACAO = "REORGANIZAÇÃO"
MOTIVO_SEM_ALOCACAO = "SEM ALOCAÇÃO"
MOTIVO_SINCRONIZACAO = "SINCRONIZAÇÃO"


def eh_domingo(dia_da_semana: str) -> bool:
    return "DOMINGO" in dia_da_semana.upper()


def classificar_intencao_mensal(
    *,
    dia_da_semana: str,
    slot_e_ceia: bool,
    alocar_todos_os_meses: bool,
    cota_base: int,
    limite_mensal: int,
    ocorrencias_no_mes: int,
    ja_consumiu_hierarquia_na_ronda: bool,
    ja_participou_na_ronda: bool,
) -> AllocationIntent | None:
    """Classifica se a proxima vaga deve cumprir obrigacao mensal.

    Retorna ``None`` quando o candidato ainda deve disputar uma vaga normal.
    """
    if not eh_domingo(dia_da_semana) or slot_e_ceia:
        return None
    if ocorrencias_no_mes >= limite_mensal:
        return None
    if alocar_todos_os_meses:
        if ja_consumiu_hierarquia_na_ronda or ja_participou_na_ronda:
            return AllocationIntent.EVERY_MONTH_OBLIGATION
        return None
    if cota_base > 1 and ocorrencias_no_mes > 0:
        return AllocationIntent.MONTHLY_REPEAT
    return None


def classificar_intencao_decisao(
    *,
    motivo: str,
    consome_hierarquia: bool,
    is_obrigacao_mensal: bool,
    alocar_todos_os_meses: bool,
) -> AllocationIntent:
    if motivo == MOTIVO_SEM_ALOCACAO:
        return AllocationIntent.NO_ALLOCATION
    if motivo == MOTIVO_CEIA:
        return AllocationIntent.CEIA
    if motivo == MOTIVO_RESGATE:
        return AllocationIntent.RESCUE
    if motivo == MOTIVO_LACUNA:
        return AllocationIntent.GAP_FILL
    if motivo == MOTIVO_REORGANIZACAO:
        return AllocationIntent.REORGANIZATION
    if motivo == MOTIVO_SINCRONIZACAO:
        return AllocationIntent.SYNCHRONIZATION
    if is_obrigacao_mensal:
        return (
            AllocationIntent.EVERY_MONTH_OBLIGATION
            if alocar_todos_os_meses
            else AllocationIntent.MONTHLY_REPEAT
        )
    if consome_hierarquia:
        return AllocationIntent.NORMAL_ROTATION
    return AllocationIntent.GAP_FILL


def classificar_tipo_alocacao(intent: AllocationIntent, motivo: str) -> str:
    if intent == AllocationIntent.NORMAL_ROTATION:
        return "NORMAL"
    if intent == AllocationIntent.MONTHLY_REPEAT:
        return "REPETICAO_MENSAL"
    if intent == AllocationIntent.EVERY_MONTH_OBLIGATION:
        return "ALOCAR_TODOS_OS_MESES"
    if intent == AllocationIntent.CEIA:
        return "CEIA"
    return motivo


def obrigacao_satisfeita_por_intencao(intent: AllocationIntent) -> str:
    if intent == AllocationIntent.MONTHLY_REPEAT:
        return "REPETICAO_MENSAL"
    if intent == AllocationIntent.EVERY_MONTH_OBLIGATION:
        return "ALOCAR_TODOS_OS_MESES"
    if intent == AllocationIntent.CEIA:
        return "CEIA"
    if intent == AllocationIntent.NORMAL_ROTATION:
        return "PARTICIPACAO_BASE"
    return ""


def calcular_cursor_depois(
    cursor_antes: str | None, vencedor: str | None, consome_hierarquia: bool
) -> str | None:
    if consome_hierarquia and vencedor:
        return vencedor
    return cursor_antes
