"""Recorrencias fixas para o fluxo de QUARTA-FEIRA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pastoreio_orquestrador.models import DecisaoAlocacao, RegraColaborador, SlotAgenda
from pastoreio_orquestrador.parsing_utils import month_key
from pastoreio_orquestrador.parsing_utils import week_of_month

TIPO_FIXO_RECORRENTE = "FIXO_RECORRENTE"


class ConflitoFixoRecorrenteError(RuntimeError):
    pass


@dataclass(frozen=True)
class AvaliacaoFixoRecorrente:
    regra: RegraColaborador
    delta_meses: int | None
    mes_da_recorrencia: bool
    semana_exigida: int | None
    semana_da_data: int
    aplica: bool


def eh_fixo_recorrente(regra: RegraColaborador) -> bool:
    return (regra.tipo_alocacao or "").strip().upper() == TIPO_FIXO_RECORRENTE


def avaliar_regra_fixa_na_data(regra: RegraColaborador, data_slot: date) -> AvaliacaoFixoRecorrente:
    semana_da_data = week_of_month(data_slot)
    if not eh_fixo_recorrente(regra):
        return AvaliacaoFixoRecorrente(
            regra=regra,
            delta_meses=None,
            mes_da_recorrencia=False,
            semana_exigida=None,
            semana_da_data=semana_da_data,
            aplica=False,
        )

    if regra.intervalo_meses is None or regra.data_inicio_recorrencia is None:
        return AvaliacaoFixoRecorrente(
            regra=regra,
            delta_meses=None,
            mes_da_recorrencia=False,
            semana_exigida=regra.semana_preferencial,
            semana_da_data=semana_da_data,
            aplica=False,
        )

    delta_meses = (
        (data_slot.year - regra.data_inicio_recorrencia.year) * 12
        + (data_slot.month - regra.data_inicio_recorrencia.month)
    )
    mes_da_recorrencia = delta_meses >= 0 and delta_meses % regra.intervalo_meses == 0
    aplica = (
        mes_da_recorrencia
        and semana_da_data == regra.semana_preferencial
        and "QUARTA" in regra.dia_da_semana.upper()
    )
    return AvaliacaoFixoRecorrente(
        regra=regra,
        delta_meses=delta_meses,
        mes_da_recorrencia=mes_da_recorrencia,
        semana_exigida=regra.semana_preferencial,
        semana_da_data=semana_da_data,
        aplica=aplica,
    )


def regra_fixa_aplica_na_data(regra: RegraColaborador, data_slot: date) -> bool:
    return avaliar_regra_fixa_na_data(regra, data_slot).aplica


def reserva_fixa_para_data(regras: list[RegraColaborador], data_slot: date) -> RegraColaborador | None:
    aplicaveis = [regra for regra in regras if regra_fixa_aplica_na_data(regra, data_slot)]
    if len(aplicaveis) > 1:
        nomes = "\n".join(f"- {regra.nome}" for regra in aplicaveis)
        raise ConflitoFixoRecorrenteError(
            f"Conflito FIXO_RECORRENTE:\n{data_slot.isoformat()}\n{nomes}"
        )
    return aplicaveis[0] if aplicaveis else None


def separar_regras_quarta(
    grupo: list[RegraColaborador],
) -> tuple[list[RegraColaborador], list[RegraColaborador]]:
    """Separa candidatos normais de reservas fixas recorrentes."""
    regras_fixas = [regra for regra in grupo if eh_fixo_recorrente(regra)]
    grupo_normal = [regra for regra in grupo if not eh_fixo_recorrente(regra)]
    return grupo_normal, regras_fixas


def delimitar_ronda_quarta_com_fixos(
    datas_disponiveis: list[date],
    *,
    n_colaboradores_normais: int,
    regras_fixas: list[RegraColaborador],
) -> list[date]:
    """Delimita a ronda contando apenas vagas normais como participacao-base."""
    if not datas_disponiveis or n_colaboradores_normais <= 0:
        return []

    bloco: list[date] = []
    vagas_normais = 0
    pos = 0

    while pos < len(datas_disponiveis) and vagas_normais < n_colaboradores_normais:
        data_slot = datas_disponiveis[pos]
        bloco.append(data_slot)
        if reserva_fixa_para_data(regras_fixas, data_slot) is None:
            vagas_normais += 1
        pos += 1

    if not bloco:
        return []

    mes_final = month_key(bloco[-1])
    while pos < len(datas_disponiveis) and month_key(datas_disponiveis[pos]) == mes_final:
        bloco.append(datas_disponiveis[pos])
        pos += 1

    return bloco


def montar_decisao_fixa(slot: SlotAgenda, regra: RegraColaborador) -> DecisaoAlocacao:
    return DecisaoAlocacao(
        slot=slot,
        vencedor=regra.nome,
        motivo="FIXO RECORRENTE",
        candidatos_avaliados=[regra.nome],
        tipo_dia="QUARTA_NORMAL",
        intent="FIXED_RECURRENCE",
        politica_selecao="FIXED_RECURRENCE",
        tipo_alocacao=TIPO_FIXO_RECORRENTE,
        obrigacao_satisfeita=TIPO_FIXO_RECORRENTE,
        consome_hierarquia=False,
        prioridade_vencedor=regra.prioridade,
        conta_repeticao_mensal=False,
    )
