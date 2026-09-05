"""Proposta B: fecha o ciclo dos "zumbis" de BP LOG.

Quando o motor aloca um colaborador que tinha um registro pendente em
BP LOG (DISPONIBILIDADE=TRUE), esse registro precisa ser marcado como
recuperado (DISPONIBILIDADE=FALSE + timestamp), senao ele continua sendo
tratado como prioritario para sempre.

Risco medio (escreve em dado hoje so lido): por isso este modulo so CALCULA
as atualizacoes necessarias (funcao pura, testavel sem sheets). A escrita
de fato deve, por ora, ser feita sempre numa copia de teste `CLAUDE_BP LOG`
(nunca na aba `BP LOG` original) ate a logica ser validada exaustivamente
contra dados reais, conforme a propria proposta pede.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pastoreio_orquestrador.columns import ColBpLog
from pastoreio_orquestrador.models import DecisaoAlocacao, RegistroBpLog
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard


@dataclass
class AtualizacaoZumbiRecuperado:
    nome: str
    departamento: str
    processo: str
    row_index_bp_log: int  # posicao 1-based dentro de bp_log (sem contar cabecalho)


def montar_atualizacoes_zumbis_recuperados(
    decisoes: list[DecisaoAlocacao],
    bp_log: list[RegistroBpLog],
    departamento: str,
    processo: str,
) -> list[AtualizacaoZumbiRecuperado]:
    """Para cada decisao com vencedor, verifica se esse vencedor tinha um
    registro pendente (DISPONIBILIDADE=TRUE) em BP LOG para este
    departamento/processo e, se sim, monta a atualizacao que o marcaria
    como recuperado. Nao escreve nada."""
    vencedores = {d.vencedor for d in decisoes if d.vencedor}
    atualizacoes: list[AtualizacaoZumbiRecuperado] = []

    for idx, registro in enumerate(bp_log, start=1):
        if (
            registro.nome in vencedores
            and registro.departamento == departamento
            and registro.processo.strip().upper() == processo.strip().upper()
            and registro.disponibilidade
        ):
            atualizacoes.append(
                AtualizacaoZumbiRecuperado(
                    nome=registro.nome,
                    departamento=registro.departamento,
                    processo=registro.processo,
                    row_index_bp_log=idx,
                )
            )
    return atualizacoes


def aplicar_atualizacoes_em_copia_teste(
    guard: SpreadsheetGuard,
    titulo_copia_bp_log: str,
    header_idx: dict[str, int],
    atualizacoes: list[AtualizacaoZumbiRecuperado],
    timestamp: str | None = None,
) -> None:
    """Escreve as atualizacoes calculadas. `titulo_copia_bp_log` DEVE ser
    uma copia com prefixo CLAUDE_ (o SpreadsheetGuard bloqueia qualquer
    outra coisa)."""
    ts = timestamp or datetime.now().isoformat(timespec="seconds")
    col_disponibilidade = header_idx[ColBpLog.DISPONIBILIDADE] + 1  # gspread e 1-based
    col_timestamp = header_idx[ColBpLog.TIMESTAMP_UTILIZACAO] + 1

    for atualizacao in atualizacoes:
        linha_sheet = atualizacao.row_index_bp_log + 1  # +1 para pular o cabecalho
        guard.update_cell(titulo_copia_bp_log, linha_sheet, col_disponibilidade, "FALSE")
        guard.update_cell(titulo_copia_bp_log, linha_sheet, col_timestamp, ts)
