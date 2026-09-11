"""Sincroniza BP SERVICE -> BP ALGORITIMO (vinculo pessoa+departamento).

Porta as duas rotinas do Apps Script original (`ProcessarBPService_
BPAlgoritimo_v12` e `ReverterBPService_BPAlgoritimo`) para o orquestrador
Python, com duas mudancas de regra de negocio pedidas pelo Clayton
(2026-09-11):

1. Contas de sistema nunca entram na selecao. Uma linha de BP SERVICE com a
   coluna TYPE preenchida (ex.: "SY") e uma conta de sistema, nao uma
   pessoa -- so TYPE vazio conta como elegivel.
2. A "reversao" deixou de apagar linhas de BP ALGORITIMO. Em vez de
   `deleteRow`, quando um vinculo pessoa+departamento deixa de bater com a
   selecao atual de BP SERVICE (pessoa ficou inativa, virou conta de
   sistema, ou desmarcou o departamento), a linha correspondente e apenas
   marcada ATIVO=FALSE -- nada e removido fisicamente. Pelo mesmo motivo,
   se um vinculo ja desativado volta a bater com a selecao, e reativado
   (ATIVO=TRUE) em vez de gerar uma linha duplicada.

A coluna ID_TABLE tambem deixou de ser uma numeracao sequencial (1, 2, 3...)
recalculada a cada execucao -- agora recebe o ID_USER da pessoa em BP
SERVICE, servindo como referencia ao cadastro de origem.

Este e o PRIMEIRO passo do fluxo do orquestrador: roda antes de qualquer
alocacao, para garantir que BP ALGORITIMO reflita o cadastro atual de BP
SERVICE antes do motor de regras (`motor.py`) usar essas linhas. Linhas
recem-inseridas ficam sem FUNCAO/DIA DA SEMANA (a regra de alocacao em si e
configurada a parte, manualmente, na spreadsheet) -- `carregar_regras_
colaboradores` em carregamento.py ja ignora linhas so-departamento sem
FUNCAO/DIA DA SEMANA, entao isso nao interfere no motor de alocacao.

Segue o mesmo padrao de `zumbi_writeback.py`: calculo puro (testavel sem
sheets) separado da escrita real, que so e permitida numa copia `CLAUDE_`
(imposto por `SpreadsheetGuard`, ver README.md / regra de seguranca).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pastoreio_orquestrador.carregamento import build_header_index, get
from pastoreio_orquestrador.columns import ColBpAlgoritimo, ColBpService, ColIdDepartamentos
from pastoreio_orquestrador.parsing_utils import parse_bool
from pastoreio_orquestrador.sheets_client import SpreadsheetGuard

COLUNAS_OBRIGATORIAS_BP_SERVICE = (
    ColBpService.NOME,
    ColBpService.DEPARTAMENTOS,
    ColBpService.INATIVO,
)

COLUNAS_OBRIGATORIAS_DESTINO = (
    ColBpAlgoritimo.NOME,
    ColBpAlgoritimo.DEPARTAMENTO,
    ColBpAlgoritimo.EMAIL_LIDER,
    ColBpAlgoritimo.ID_TABLE,
    ColBpAlgoritimo.ATIVO,
)

CABECALHOS_BASE_BP_ALGORITIMO = list(COLUNAS_OBRIGATORIAS_DESTINO)


@dataclass(frozen=True)
class VinculoElegivel:
    """Um par pessoa+departamento que a selecao atual de BP SERVICE
    considera valido (equivalente a um `item` de `listaNovosDados` no
    script original)."""

    nome: str
    departamento: str
    id_user: str
    email_lider: str

    @property
    def chave(self) -> tuple[str, str]:
        return (self.nome, self.departamento)


@dataclass
class AtualizacaoCelula:
    linha_bp_algoritimo: int  # 1-based dentro da aba, ja contando o cabecalho
    coluna: str
    valor: str
    motivo: str


@dataclass
class PlanoSincronizacao:
    inserir: list[VinculoElegivel] = field(default_factory=list)
    atualizacoes: list[AtualizacaoCelula] = field(default_factory=list)

    @property
    def vazio(self) -> bool:
        return not self.inserir and not self.atualizacoes


def _validar_cabecalho(idx: dict[str, int], obrigatorias: tuple[str, ...], aba: str) -> None:
    faltando = [nome for nome in obrigatorias if nome not in idx]
    if faltando:
        raise ValueError(
            f"Cabecalho de {aba} sem coluna(s) obrigatoria(s): "
            + ", ".join(repr(n) for n in faltando)
        )


def detectar_colunas_departamento(header_bp_service: list[str]) -> list[str]:
    """Colunas de BP SERVICE que representam um departamento (prefixo
    "D. "), exceto `ColBpService.DEPARTAMENTO_EXCLUIDO`."""
    excluida = ColBpService.DEPARTAMENTO_EXCLUIDO.strip().upper()
    return [
        h
        for h in header_bp_service
        if h.strip().upper().startswith(ColBpService.DEPARTAMENTO_PREFIXO)
        and h.strip().upper() != excluida
    ]


def carregar_email_por_departamento(valores_id_departamentos: list[list[str]]) -> dict[str, str]:
    """Le ID_DEPARTAMENTOS e devolve {DEPARTAMENTO em maiusculas: EMAIL}.

    Nota (2026-09-11): a aba ID_DEPARTAMENTOS real hoje nao tem coluna
    EMAIL (so DEPARTAMENTOS/DESCRIÇÃO/TIPO) -- nesse caso devolve {} e
    nenhum email e preenchido por esta sincronizacao, igual ao
    comportamento do script original quando a coluna EMAIL faltava."""
    if not valores_id_departamentos:
        return {}
    idx = build_header_index(valores_id_departamentos[0])
    if ColIdDepartamentos.DEPARTAMENTOS not in idx or ColIdDepartamentos.EMAIL not in idx:
        return {}
    mapa: dict[str, str] = {}
    for row in valores_id_departamentos[1:]:
        dept = get(row, idx, ColIdDepartamentos.DEPARTAMENTOS).strip().upper()
        if dept:
            mapa[dept] = get(row, idx, ColIdDepartamentos.EMAIL).strip()
    return mapa


def selecionar_vinculos_elegiveis(
    valores_bp_service: list[list[str]],
    email_por_departamento: dict[str, str] | None = None,
) -> list[VinculoElegivel]:
    """Le BP SERVICE e devolve todos os vinculos pessoa+departamento
    elegiveis. Regras de selecao:

    - NOME preenchido;
    - INATIVO != verdadeiro;
    - DEPARTAMENTOS (flag geral) == verdadeiro;
    - TYPE vazio -- TYPE preenchido (ex.: "SY") marca uma conta de sistema,
      nunca elegivel (pedido do Clayton, 2026-09-11);
    - para cada coluna "D. X" marcada como verdadeira (exceto D. CENTRO DE
      CURA), gera um `VinculoElegivel`.
    """
    if not valores_bp_service:
        return []
    email_por_departamento = email_por_departamento or {}
    idx = build_header_index(valores_bp_service[0])
    _validar_cabecalho(idx, COLUNAS_OBRIGATORIAS_BP_SERVICE, "BP SERVICE")
    colunas_dept = detectar_colunas_departamento(valores_bp_service[0])

    vinculos: list[VinculoElegivel] = []
    for row in valores_bp_service[1:]:
        nome = get(row, idx, ColBpService.NOME).strip()
        if not nome:
            continue
        if parse_bool(get(row, idx, ColBpService.INATIVO)):
            continue
        if not parse_bool(get(row, idx, ColBpService.DEPARTAMENTOS)):
            continue
        if get(row, idx, ColBpService.TYPE).strip():
            continue  # conta de sistema -- nunca elegivel

        id_user = get(row, idx, ColBpService.ID_USER).strip()
        for dept_col in colunas_dept:
            if parse_bool(get(row, idx, dept_col)):
                email = email_por_departamento.get(dept_col.strip().upper(), "")
                vinculos.append(
                    VinculoElegivel(nome=nome, departamento=dept_col, id_user=id_user, email_lider=email)
                )
    return vinculos


def calcular_plano_sincronizacao(
    vinculos_elegiveis: list[VinculoElegivel],
    valores_bp_algoritimo: list[list[str]],
) -> PlanoSincronizacao:
    """Compara a selecao atual de BP SERVICE (`vinculos_elegiveis`) com o
    que ja existe em BP ALGORITIMO e devolve o plano de mudancas. Funcao
    pura -- nao acede a rede, so calcula; quem aplica e `aplicar_plano`.

    - `inserir`: vinculos novos (nome+departamento ainda nao existe em BP
      ALGORITIMO), com ID_TABLE = ID_USER de origem e ATIVO=TRUE.
    - `atualizacoes`:
        - EMAIL LIDER vazio corrigido, se a origem tiver um valor;
        - ID_TABLE vazio corrigido com o ID_USER de origem;
        - ATIVO=FALSE quando o vinculo existente deixou de bater com a
          selecao atual (a "reversao" pedida pelo Clayton -- nunca apaga a
          linha);
        - ATIVO=TRUE quando um vinculo antes desativado volta a bater com
          a selecao atual (reativacao, complemento necessario da regra
          acima para nao deixar o vinculo preso em FALSE para sempre).
    """
    plano = PlanoSincronizacao()
    if not valores_bp_algoritimo:
        plano.inserir.extend(vinculos_elegiveis)
        return plano

    idx = build_header_index(valores_bp_algoritimo[0])
    _validar_cabecalho(idx, COLUNAS_OBRIGATORIAS_DESTINO, "BP ALGORITIMO")

    elegiveis_por_chave = {v.chave: v for v in vinculos_elegiveis}
    chaves_existentes: set[tuple[str, str]] = set()

    for i, row in enumerate(valores_bp_algoritimo[1:], start=1):
        linha_sheet = i + 1  # +1 para contar a linha de cabecalho
        nome = get(row, idx, ColBpAlgoritimo.NOME).strip()
        dept = get(row, idx, ColBpAlgoritimo.DEPARTAMENTO).strip()
        if not nome or not dept:
            continue
        chave = (nome, dept)
        chaves_existentes.add(chave)

        vinculo_atual = elegiveis_por_chave.get(chave)
        email_atual = get(row, idx, ColBpAlgoritimo.EMAIL_LIDER).strip()
        id_table_atual = get(row, idx, ColBpAlgoritimo.ID_TABLE).strip()
        ativo_atual = parse_bool(get(row, idx, ColBpAlgoritimo.ATIVO))

        if vinculo_atual is not None:
            if not email_atual and vinculo_atual.email_lider:
                plano.atualizacoes.append(
                    AtualizacaoCelula(
                        linha_sheet,
                        ColBpAlgoritimo.EMAIL_LIDER,
                        vinculo_atual.email_lider,
                        "EMAIL LIDER vazio corrigido a partir de BP SERVICE",
                    )
                )
            if not id_table_atual and vinculo_atual.id_user:
                plano.atualizacoes.append(
                    AtualizacaoCelula(
                        linha_sheet,
                        ColBpAlgoritimo.ID_TABLE,
                        vinculo_atual.id_user,
                        "ID_TABLE vazio corrigido com o ID_USER de BP SERVICE",
                    )
                )
            if not ativo_atual:
                plano.atualizacoes.append(
                    AtualizacaoCelula(
                        linha_sheet,
                        ColBpAlgoritimo.ATIVO,
                        "TRUE",
                        "vinculo voltou a bater na selecao atual de BP SERVICE -- reativado",
                    )
                )
        else:
            if ativo_atual:
                plano.atualizacoes.append(
                    AtualizacaoCelula(
                        linha_sheet,
                        ColBpAlgoritimo.ATIVO,
                        "FALSE",
                        "vinculo nao esta mais na selecao atual de BP SERVICE "
                        "(pessoa inativa, conta de sistema, ou departamento desmarcado)",
                    )
                )

    plano.inserir = [v for v in vinculos_elegiveis if v.chave not in chaves_existentes]
    return plano


def montar_linhas_para_inserir(header_bp_algoritimo: list[str], novos: list[VinculoElegivel]) -> list[list[str]]:
    idx = build_header_index(header_bp_algoritimo)
    _validar_cabecalho(idx, COLUNAS_OBRIGATORIAS_DESTINO, "BP ALGORITIMO")
    linhas: list[list[str]] = []
    for v in novos:
        linha = [""] * len(header_bp_algoritimo)
        linha[idx[ColBpAlgoritimo.NOME]] = v.nome
        linha[idx[ColBpAlgoritimo.DEPARTAMENTO]] = v.departamento
        linha[idx[ColBpAlgoritimo.EMAIL_LIDER]] = v.email_lider
        linha[idx[ColBpAlgoritimo.ID_TABLE]] = v.id_user
        linha[idx[ColBpAlgoritimo.ATIVO]] = "TRUE"
        linhas.append(linha)
    return linhas


def garantir_cabecalhos_bp_algoritimo(guard: SpreadsheetGuard, titulo_bp_algoritimo: str) -> list[str]:
    """Garante que `titulo_bp_algoritimo` (DEVE ser copia CLAUDE_) tem pelo
    menos as colunas usadas por esta sincronizacao, acrescentando as que
    faltarem no fim. Devolve o cabecalho final. Nao apaga nem reordena
    colunas existentes."""
    valores_atuais = guard.read_worksheet(titulo_bp_algoritimo)
    header = valores_atuais[0] if valores_atuais else []
    faltando = [c for c in CABECALHOS_BASE_BP_ALGORITIMO if c not in header]
    if not header:
        guard.update_worksheet(titulo_bp_algoritimo, [CABECALHOS_BASE_BP_ALGORITIMO])
        return list(CABECALHOS_BASE_BP_ALGORITIMO)
    if faltando:
        novo_header = header + faltando
        guard.update_worksheet(titulo_bp_algoritimo, [novo_header])
        return novo_header
    return header


def aplicar_plano(
    guard: SpreadsheetGuard,
    titulo_bp_algoritimo: str,
    header_bp_algoritimo: list[str],
    plano: PlanoSincronizacao,
) -> None:
    """Escreve o plano calculado. `titulo_bp_algoritimo` DEVE ser uma copia
    com prefixo CLAUDE_ -- `SpreadsheetGuard` bloqueia qualquer outra coisa
    (`TentativaDeAlteracaoOriginalError`)."""
    if plano.atualizacoes:
        idx = build_header_index(header_bp_algoritimo)
        updates = [
            (a.linha_bp_algoritimo, idx[a.coluna] + 1, a.valor)
            for a in plano.atualizacoes
        ]
        guard.batch_update_cells(titulo_bp_algoritimo, updates)

    if plano.inserir:
        linhas = montar_linhas_para_inserir(header_bp_algoritimo, plano.inserir)
        guard.append_rows(titulo_bp_algoritimo, linhas)
