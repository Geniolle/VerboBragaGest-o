"""Verificacoes de sanidade da estrutura da spreadsheet configurada.

Compara, so por leitura (nunca escreve nada), o que `columns.py` espera de
cada aba com o que existe de facto na spreadsheet real. Serve para detetar
cedo uma aba renomeada ou uma coluna removida, antes de rodar o motor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pastoreio_orquestrador.carregamento import build_header_index
from pastoreio_orquestrador.columns import (
    ColAppAnualGlobal,
    ColBpAlgoritimo,
    ColBpLog,
    ColConfAlgoritimo,
    ColExcluse,
    ColLivros,
    ColLogAlgoritimo,
)
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

ABAS_ESPERADAS = [
    "BP ALGORITIMO",
    "AppAnualGlobal",
    "Excluse",
    "CONF_ALGORITIMO",
    "Livros",
    "BP LOG",
    "LOG ALGORITIMO",
]

COLUNAS_ESPERADAS_POR_ABA: dict[str, list[str]] = {
    "BP ALGORITIMO": [
        ColBpAlgoritimo.ID_TABLE,
        ColBpAlgoritimo.NOME,
        ColBpAlgoritimo.DEPARTAMENTO,
        ColBpAlgoritimo.FUNCAO,
        ColBpAlgoritimo.DIA_DA_SEMANA,
        ColBpAlgoritimo.ATIVO,
    ],
    "AppAnualGlobal": [
        ColAppAnualGlobal.DIA_DA_SEMANA,
        ColAppAnualGlobal.DATA,
        ColAppAnualGlobal.TEMA,
    ],
    "Excluse": [ColExcluse.COLUNAS],
    "CONF_ALGORITIMO": [ColConfAlgoritimo.PROCESSO, ColConfAlgoritimo.VALOR],
    "Livros": [ColLivros.DIA_DA_SEMANA, ColLivros.TEMA, ColLivros.CLASSIFICACAO],
    "BP LOG": [
        ColBpLog.DEPARTAMENTO,
        ColBpLog.PROCESSO,
        ColBpLog.NOME,
        ColBpLog.DISPONIBILIDADE,
    ],
    "LOG ALGORITIMO": [
        ColLogAlgoritimo.DATA_EXECUCAO,
        ColLogAlgoritimo.ALOCACOES_JSON,
        ColLogAlgoritimo.STATUS,
    ],
}


@dataclass
class RelatorioDiagnostico:
    abas_encontradas: list[str] = field(default_factory=list)
    abas_em_falta: list[str] = field(default_factory=list)
    colunas_em_falta_por_aba: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.abas_em_falta and not self.colunas_em_falta_por_aba


def diagnosticar(guard: SpreadsheetGuard) -> RelatorioDiagnostico:
    """Le a estrutura real da spreadsheet e compara com o que `columns.py`
    espera. Nunca escreve nada (so usa `list_worksheet_titles`/`read_worksheet`,
    que sao permitidos em qualquer aba, inclusive originais)."""
    relatorio = RelatorioDiagnostico()
    titulos = guard.list_worksheet_titles()
    relatorio.abas_encontradas = titulos
    relatorio.abas_em_falta = [aba for aba in ABAS_ESPERADAS if aba not in titulos]

    for aba, colunas_esperadas in COLUNAS_ESPERADAS_POR_ABA.items():
        if aba not in titulos:
            continue
        valores = guard.read_worksheet(aba)
        if not valores:
            relatorio.colunas_em_falta_por_aba[aba] = list(colunas_esperadas)
            continue
        idx = build_header_index(valores[0])
        faltando = [c for c in colunas_esperadas if c not in idx]
        if faltando:
            relatorio.colunas_em_falta_por_aba[aba] = faltando

    return relatorio
