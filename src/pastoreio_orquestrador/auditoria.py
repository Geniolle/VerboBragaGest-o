"""Log de auditoria das decisoes do motor.

Converte cada `DecisaoAlocacao` (ja calculada por `motor.alocar_grupo`) numa
linha de texto pronta para gravacao numa aba `CLAUDE_LOG_AUDITORIA`,
preservando o raciocinio da escolha (motivo, candidatos avaliados na ordem
de desempate, runner-up) para que uma alocacao proposta possa ser revisada
por um humano sem reexecutar o motor.
"""

from __future__ import annotations

from datetime import datetime

from pastoreio_orquestrador.models import DecisaoAlocacao

NOME_ABA_AUDITORIA = "CLAUDE_LOG_AUDITORIA"

CABECALHO_AUDITORIA = [
    "TIMESTAMP_EXECUCAO",
    "GRUPO",
    "DATA_SLOT",
    "DIA_DA_SEMANA",
    "TEMA",
    "REQUISITO_TEMA",
    "VENCEDOR",
    "MOTIVO",
    "RUNNER_UP",
    "CANDIDATOS_AVALIADOS",
]


def construir_linhas_auditoria(
    decisoes: list[DecisaoAlocacao],
    grupo_label: str,
    requisitos_tema_por_slot: dict[int, str] | None = None,
    timestamp_execucao: str | None = None,
) -> list[list[str]]:
    """Devolve as linhas (sem cabecalho) prontas para `CLAUDE_LOG_AUDITORIA`,
    uma por decisao. `CANDIDATOS_AVALIADOS` preserva a ordem de desempate
    (o primeiro nome e o vencedor), permitindo entender por que um
    colaborador venceu sobre outro no mesmo slot."""
    requisitos_tema_por_slot = requisitos_tema_por_slot or {}
    ts = timestamp_execucao or datetime.now().isoformat(timespec="seconds")

    linhas: list[list[str]] = []
    for d in decisoes:
        requisito = requisitos_tema_por_slot.get(d.slot.row_index, "")
        linhas.append(
            [
                ts,
                grupo_label,
                d.slot.data.isoformat(),
                d.slot.dia_da_semana,
                d.slot.tema,
                requisito,
                d.vencedor or "",
                d.motivo,
                d.runner_up or "",
                "; ".join(d.candidatos_avaliados),
            ]
        )
    return linhas
