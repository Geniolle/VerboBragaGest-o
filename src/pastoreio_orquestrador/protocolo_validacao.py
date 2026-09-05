"""Proposta F: protocolo de validacao por grupo. Sem risco (disciplina de
trabalho): so compara os grupos ativos em BP ALGORITIMO com o registro em
`GRUPOS_VALIDADOS.md`, para deixar explicito quais grupos ainda nao tiveram
um teste de integracao real revisado por um humano."""

from __future__ import annotations

from dataclasses import dataclass, field

from pastoreio_orquestrador.models import RegraColaborador


@dataclass
class RelatorioValidacaoGrupos:
    validados: list[str] = field(default_factory=list)
    pendentes: list[str] = field(default_factory=list)


def parse_grupos_validados(conteudo_markdown: str) -> set[str]:
    """Extrai as chaves de grupo (`DEPARTAMENTO###FUNÇÃO###DIA`) listadas em
    GRUPOS_VALIDADOS.md, ignorando comentarios (#) e linhas vazias/titulos."""
    grupos: set[str] = set()
    for linha in conteudo_markdown.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if "###" in linha:
            grupos.add(linha)
    return grupos


def avaliar_grupos(
    regras_ativas: list[RegraColaborador], grupos_validados: set[str]
) -> RelatorioValidacaoGrupos:
    """`regras_ativas` deve ser a lista ja filtrada por ATIVO=true."""
    chaves = sorted({r.chave_grupo for r in regras_ativas})
    relatorio = RelatorioValidacaoGrupos()
    for chave in chaves:
        if chave in grupos_validados:
            relatorio.validados.append(chave)
        else:
            relatorio.pendentes.append(chave)
    return relatorio
