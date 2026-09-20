"""Tipos explicitos de decisao usados pelo motor de alocacao."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AllocationIntent(StrEnum):
    """Por que a vaga existe antes/depois de resolver o colaborador."""

    NORMAL_ROTATION = "NORMAL_ROTATION"
    PREFERRED_WEEK = "PREFERRED_WEEK"
    MONTHLY_REPEAT = "MONTHLY_REPEAT"
    EVERY_MONTH_OBLIGATION = "EVERY_MONTH_OBLIGATION"
    CEIA = "CEIA"
    RESCUE = "RESCUE"
    GAP_FILL = "GAP_FILL"
    REORGANIZATION = "REORGANIZATION"
    SYNCHRONIZATION = "SYNCHRONIZATION"
    NO_ALLOCATION = "NO_ALLOCATION"


@dataclass(frozen=True)
class CandidateEvaluation:
    """Trace pequeno para explicar por que um candidato foi aceito/rejeitado."""

    candidato: str
    resultado: str
    motivo: str
    passada: str = ""
    ordem: int | None = None
    prioridade: int | None = None
    elegivel: bool = False
    motivos_rejeicao: list[str] = field(default_factory=list)
    ocorrencias_mes: int | None = None
    limite_mensal: int | None = None
    repeticao_mensal: int | None = None
    alocar_todos_os_meses: bool = False
    ceia_no_mes: int | None = None


@dataclass(frozen=True)
class DecisionTrace:
    """Resumo auditavel da decisao de uma vaga."""

    intent: AllocationIntent
    consome_hierarquia: bool
    conta_repeticao_mensal: bool
    cursor_antes: str | None = None
    cursor_depois: str | None = None
    data: str = ""
    tipo_dia: str = ""
    politica_selecao: str = ""
    selecionado: str | None = None
    motivo_escolha: str = ""
    obrigacao_satisfeita: str = ""
    prioridade_selecionado: int | None = None
    hierarquia: list[str] = field(default_factory=list)
    avaliacoes: list[CandidateEvaluation] = field(default_factory=list)
