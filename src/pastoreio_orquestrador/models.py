"""Modelos de dados do orquestrador, espelhando as entidades do algoritmo
Algoritimo_Input_Escala_Automatico_v63."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class RegraColaborador:
    """Uma linha ativa de BP ALGORITIMO (uma regra colaborador+depto+funcao)."""

    id_table: str
    nome: str
    departamento: str
    funcao: str
    dia_da_semana: str
    prioridade: int
    repeticao_mensal: int
    alocar_todos_os_meses: bool
    semana_preferencial: int
    ceia_alternada: bool
    semana_alternada: bool
    alocacao_extra: int
    atribuir_aos_recados: bool
    sinc_colaborador: str | None
    sinc_sem_alocacao: bool
    temas: list[str]
    ativo: bool
    row_index_bp: int

    @property
    def chave_grupo(self) -> str:
        return f"{self.departamento}###{self.funcao}###{self.dia_da_semana}"

    @property
    def cota_base(self) -> int:
        return max(1, self.repeticao_mensal)


@dataclass
class SlotAgenda:
    """Uma linha de AppAnualGlobal candidata a receber uma alocacao."""

    row_index: int
    data: date
    dia_da_semana: str
    tema: str
    mes_key: str
    semana_do_mes: int
    is_ultima_ocorrencia_do_mes: bool
    valor_atual: str = ""
    assiduidade: dict[str, str] = field(default_factory=dict)


@dataclass
class TemaClassificado:
    dia_da_semana: str
    tema: str
    classificacao: str  # P1 / P2 / P3


@dataclass
class CandidatoRuntime:
    """Estado mutavel de um candidato durante a avaliacao de UM slot.
    Resetado a cada slot avaliado."""

    regra: RegraColaborador
    is_sinc_forced: bool = False
    is_sinc_natural: bool = False
    is_sem_alt_violation: bool = False
    is_zombie_recuperado: bool = False

    @property
    def nome(self) -> str:
        return self.regra.nome


@dataclass
class DecisaoAlocacao:
    slot: SlotAgenda
    vencedor: str | None
    motivo: str
    candidatos_avaliados: list[str] = field(default_factory=list)
    runner_up: str | None = None
    sem_alocacao: bool = False


@dataclass
class RegistroBpLog:
    departamento: str
    processo: str
    nome: str
    mes_nao_alocados: str
    disponibilidade: bool
    timestamp_utilizacao: str
