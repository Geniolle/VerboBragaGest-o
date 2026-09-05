"""Proposta E: checklist de sanity check das regras de BP ALGORITIMO antes
de alocar. So leitura + relatorio, nunca escreve nada.

Verifica dois tipos de problema que o motor nao rejeitaria sozinho (porque
nao sao erros de execucao, so configuracao suspeita):
  - SINC_COLABORADOR apontando para alguem que nao existe (ou nao esta mais
    ativo) no mesmo DIA DA SEMANA. Nota (confirmada contra dados reais em
    2026-09-05): a sincronizacao e por linha/data de AppAnualGlobal (ver
    motor.has_neighbor_conflict), entao ela cruza departamentos/funcoes
    livremente -- so precisa ser o mesmo dia da semana. Ex. real: "Jadson
    Felipe" (D. COMUNICAÇÃO/SONORIZAÇÃO 1/DOMINGO) sincroniza com "Rosa
    Cunha", que so existe em D. COMUNICAÇÃO/STORYS 1/DOMINGO -- funcao
    diferente, mesmo dia, portanto valido.
  - Combinacoes contraditorias de quota (repeticao mensal <= 0, alocacao
    extra negativa, semana preferencial fora do intervalo valido 0..5).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pastoreio_orquestrador.models import RegraColaborador

SEMANAS_PREFERENCIAIS_VALIDAS = range(0, 6)  # 0 = sem preferencia, 1..5 = semana do mes


@dataclass
class RelatorioSanityRegras:
    avisos_sinc: list[str] = field(default_factory=list)
    avisos_quota: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.avisos_sinc and not self.avisos_quota


def diagnosticar_regras(regras: list[RegraColaborador]) -> RelatorioSanityRegras:
    """`regras` deve ser a lista ja filtrada por ATIVO=true (o que
    `carregar_regras_colaboradores` ja faz), entao "nao encontrado no mesmo
    dia" e equivalente a "inexistente ou inativo"."""
    relatorio = RelatorioSanityRegras()

    nomes_por_dia: dict[str, set[str]] = {}
    for r in regras:
        nomes_por_dia.setdefault(r.dia_da_semana, set()).add(r.nome)

    for r in regras:
        if r.sinc_colaborador:
            nomes_do_dia = nomes_por_dia.get(r.dia_da_semana, set())
            if r.sinc_colaborador not in nomes_do_dia:
                relatorio.avisos_sinc.append(
                    f"{r.nome} ({r.chave_grupo}): SINC_COLABORADOR aponta para "
                    f"'{r.sinc_colaborador}', que nao esta ativo em nenhuma funcao "
                    f"de {r.dia_da_semana}."
                )

        if r.repeticao_mensal <= 0:
            relatorio.avisos_quota.append(
                f"{r.nome} ({r.chave_grupo}): REPETIÇÃO MENSAL={r.repeticao_mensal} "
                f"(deveria ser >= 1)."
            )
        if r.alocacao_extra < 0:
            relatorio.avisos_quota.append(
                f"{r.nome} ({r.chave_grupo}): ALOCAÇÃO EXTRA={r.alocacao_extra} (nao pode ser negativa)."
            )
        if r.semana_preferencial not in SEMANAS_PREFERENCIAIS_VALIDAS:
            relatorio.avisos_quota.append(
                f"{r.nome} ({r.chave_grupo}): SEMANA PREFERENCIAL={r.semana_preferencial} "
                f"fora do intervalo valido (0 a 5)."
            )

    return relatorio


__all__ = ["RelatorioSanityRegras", "diagnosticar_regras"]
