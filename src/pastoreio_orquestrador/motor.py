"""Motor de regras: porte do nucleo do Algoritimo_Input_Escala_Automatico_v63.

Reproduz, em Python puro (sem tocar em nenhuma sheet), a cascata de decisao
do script original:
  1. Agregacao das regras ativas por grupo (departamento + funcao + dia).
  2. Calculo de demanda por "onda expansiva" (capacidade base vs vagas reais,
     ativando cota extra quando ha mais vagas do que capacidade base).
  3. Cascata de filtros obrigatorios por slot (quota mensal, semana
     preferencial, exclusao, conflito de vizinhanca, compatibilidade de
     tema, descanso minimo de 7 dias — com override de sincronizacao).
  4. Desempate (sorter) por ordem de precedencia.
  5. Logica de resgate quando ninguem sobrevive a cascata completa.

NOTA (validado contra dados reais em 2026-09-05): a checagem de bloqueio via
aba "Excluse" foi confirmada lendo a spreadsheet real. A aba Excluse mapeia
FUNCAO (coluna "COLUNAS", ex.: "MINISTRO", "AUXILIAR", "CEIA") -> para cada
departamento, uma coluna "ID_<DEPARTAMENTO>" cujo VALOR e o NOME de uma das
30 colunas genericas ASSIDUIDADE1..30 de AppAnualGlobal. Diferente da
suposicao inicial, essas colunas ASSIDUIDADE nao guardam um booleano: elas
guardam o NOME de um colaborador especifico que fica excluido daquela
funcao/departamento NAQUELA DATA (linha). Ou seja, o bloqueio e por
colaborador + data, nao por departamento inteiro. Ex. real observado: a
funcao MINISTRO usa sempre ASSIDUIDADE1 (para todos os departamentos, ja
que o mesmo numero de coluna e reaproveitado conforme a funcao, nao o
departamento), e em 01/11/2026 a celula ASSIDUIDADE1 continha "Fernando
Maurício" — isso bloquearia especificamente esse colaborador de ser MINISTRO
nessa data, sem afetar os demais candidatos do grupo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from pastoreio_orquestrador.models import (
    CandidatoRuntime,
    DecisaoAlocacao,
    RegraColaborador,
    SlotAgenda,
    TemaClassificado,
)
from pastoreio_orquestrador.parsing_utils import diff_days, is_valid_preferred_week

DESCANSO_MINIMO_DIAS = 7
MAX_ITERACOES_ONDA_EXPANSIVA = 8


# ---------------------------------------------------------------------------
# 1. Agregacao de regras em grupos
# ---------------------------------------------------------------------------


def agregar_por_grupo(regras: list[RegraColaborador]) -> dict[str, list[RegraColaborador]]:
    grupos: dict[str, list[RegraColaborador]] = {}
    for r in regras:
        grupos.setdefault(r.chave_grupo, []).append(r)
    return grupos


def ordem_processamento_grupos(chaves: list[str]) -> list[str]:
    """Processa primeiro os grupos de QUARTA-FEIRA, como no script original."""
    def chave_ordenacao(chave: str) -> tuple[int, str]:
        eh_quarta = "QUARTA" in chave.upper()
        return (0 if eh_quarta else 1, chave)

    return sorted(chaves, key=chave_ordenacao)


# ---------------------------------------------------------------------------
# 2. Demanda por onda expansiva
# ---------------------------------------------------------------------------


@dataclass
class ResultadoDemanda:
    capacidade_base: int
    capacidade_total: int
    demanda_calculada: int
    usa_cota_extra: bool
    mapa_limites_locais: dict[str, int] = field(default_factory=dict)


def calcular_demanda_onda_expansiva(
    candidatos: list[RegraColaborador],
    vagas_reais_no_periodo: int,
    meses_tocados: int,
) -> ResultadoDemanda:
    def capacidade(usar_extra: bool) -> tuple[int, dict[str, int]]:
        limites: dict[str, int] = {}
        total = 0
        for c in candidatos:
            limite = c.cota_base + (c.alocacao_extra if usar_extra else 0)
            if c.alocar_todos_os_meses:
                limite *= max(1, meses_tocados)
            limites[c.nome] = limite
            total += limite
        return total, limites

    capacidade_base, mapa_base = capacidade(usar_extra=False)

    usa_extra = vagas_reais_no_periodo > capacidade_base
    capacidade_total, mapa_total = (
        capacidade(usar_extra=True) if usa_extra else (capacidade_base, mapa_base)
    )

    demanda_calculada = min(vagas_reais_no_periodo, capacidade_total)

    return ResultadoDemanda(
        capacidade_base=capacidade_base,
        capacidade_total=capacidade_total,
        demanda_calculada=demanda_calculada,
        usa_cota_extra=usa_extra,
        mapa_limites_locais=mapa_total,
    )


# ---------------------------------------------------------------------------
# 3. Filtros obrigatorios
# ---------------------------------------------------------------------------


def respeita_descanso_minimo(
    ultima_data_usada: date | None,
    data_slot: date,
    dias_minimos: int = DESCANSO_MINIMO_DIAS,
) -> bool:
    if ultima_data_usada is None:
        return True
    return diff_days(ultima_data_usada, data_slot) >= dias_minimos


def has_neighbor_conflict(nome: str, nomes_ja_usados_em_linhas_vizinhas: set[str]) -> bool:
    return nome in nomes_ja_usados_em_linhas_vizinhas


def is_tema_compativel(
    candidato_temas: list[str],
    requisito_real: str | None,
    funcao: str,
    dia_da_semana: str,
) -> bool:
    """Se nao ha requisito de tema para este slot, qualquer candidato passa.
    Excecao: 'D. MINISTROS' fora de quarta-feira nunca exige tema."""
    if funcao.upper() == "D. MINISTROS" and "QUARTA" not in dia_da_semana.upper():
        return True
    if not requisito_real:
        return True
    return requisito_real.upper() in {t.upper() for t in candidato_temas}


def esta_bloqueado_por_excluse(
    nome_candidato: str,
    departamento: str,
    funcao: str,
    slot: SlotAgenda,
    excluse_header: dict[str, int],
    excluse_rows: list[list[str]],
) -> bool:
    """True se `nome_candidato` estiver especificamente excluido de
    `funcao`/`departamento` na data de `slot` (ver nota no topo do modulo)."""
    from pastoreio_orquestrador.columns import ColExcluse

    id_col = ColExcluse.id_col(departamento)
    if id_col not in excluse_header:
        return False

    col_processo_idx = excluse_header.get(ColExcluse.COLUNAS)
    if col_processo_idx is None:
        return False

    for row in excluse_rows:
        if not row or col_processo_idx >= len(row):
            continue
        if row[col_processo_idx].strip().upper() != funcao.strip().upper():
            continue
        idx_id = excluse_header[id_col]
        if idx_id >= len(row):
            continue
        nome_coluna_assiduidade = row[idx_id].strip()
        if not nome_coluna_assiduidade:
            return False
        valor = slot.assiduidade.get(nome_coluna_assiduidade, "").strip()
        return valor.upper() == nome_candidato.strip().upper()

    return False


# ---------------------------------------------------------------------------
# 4. Requisitos de tema (Fase 0 - forca-tarefa P1 para D. MINISTROS/QUARTA)
# ---------------------------------------------------------------------------


def montar_requisito_tema_por_slot(
    slots_do_grupo: list[SlotAgenda],
    temas_livros: list[TemaClassificado],
) -> dict[int, str]:
    """Para cada bloco de tema (classificado em Livros por dia da semana),
    o primeiro dia do bloco exige P1, o ultimo exige P2 e os do meio exigem
    P3. Devolve {row_index_do_slot: classificacao_exigida}."""
    requisito: dict[int, str] = {}
    if not slots_do_grupo:
        return requisito

    slots_ordenados = sorted(slots_do_grupo, key=lambda s: s.data)
    temas_por_texto = {t.tema.strip().upper(): t.classificacao for t in temas_livros}

    bloco_atual: list[SlotAgenda] = []
    tema_atual: str | None = None

    def fechar_bloco():
        if not bloco_atual:
            return
        classificacao = temas_por_texto.get(tema_atual)
        if not classificacao:
            return
        if classificacao == "P3" and len(bloco_atual) > 1:
            # Bloco de varias semanas sobre o mesmo tema P3: a primeira aula
            # exige um ministro P1 (mais experiente), a ultima exige P2
            # (revisao) e as do meio exigem P3 (nivel regular do tema).
            requisito[bloco_atual[0].row_index] = "P1"
            requisito[bloco_atual[-1].row_index] = "P2"
            for meio in bloco_atual[1:-1]:
                requisito[meio.row_index] = "P3"
        else:
            for slot in bloco_atual:
                requisito[slot.row_index] = classificacao

    for slot in slots_ordenados:
        tema_norm = slot.tema.strip().upper()
        if tema_norm != tema_atual:
            fechar_bloco()
            bloco_atual = []
            tema_atual = tema_norm
        bloco_atual.append(slot)
    fechar_bloco()

    return requisito


# ---------------------------------------------------------------------------
# 5. Sorter (desempate)
# ---------------------------------------------------------------------------


@dataclass
class ContextoDesempate:
    slot: SlotAgenda
    uso_mes_anterior: dict[str, int]
    ja_usou_no_mes_atual: dict[str, bool]
    historico_total: dict[str, int]
    zumbis_prioritarios: set[str]
    funcao_tem_restricao_ceia: bool
    slot_e_ceia: bool


def chave_ordenacao_candidato(cand: CandidatoRuntime, ctx: ContextoDesempate) -> tuple:
    r = cand.regra

    sinc_vence = not (cand.is_sinc_forced or cand.is_sinc_natural)
    semana_valida = not is_valid_preferred_week(r.semana_preferencial, ctx.slot.data)
    teve_credito_mes_anterior = not (
        ctx.uso_mes_anterior.get(r.nome, 0) < r.cota_base
    )
    ainda_nao_usou_all_months = not (
        r.alocar_todos_os_meses and not ctx.ja_usou_no_mes_atual.get(r.nome, False)
    )
    eh_quarta = "QUARTA" in ctx.slot.dia_da_semana.upper()
    zumbi_vence = not (eh_quarta and r.nome in ctx.zumbis_prioritarios)
    historico = ctx.historico_total.get(r.nome, 0)
    reserva_ceia_penalizada = (
        ctx.funcao_tem_restricao_ceia and not ctx.slot_e_ceia and r.ceia_alternada
    )
    prioridade = r.prioridade
    desempate_aleatorio = random.random()

    return (
        sinc_vence,
        semana_valida,
        teve_credito_mes_anterior,
        ainda_nao_usou_all_months,
        zumbi_vence,
        historico,
        reserva_ceia_penalizada,
        prioridade,
        desempate_aleatorio,
    )


def ordenar_candidatos(
    candidatos: list[CandidatoRuntime], ctx: ContextoDesempate
) -> list[CandidatoRuntime]:
    return sorted(candidatos, key=lambda c: chave_ordenacao_candidato(c, ctx))


# ---------------------------------------------------------------------------
# 6. Loop principal + resgate
# ---------------------------------------------------------------------------


@dataclass
class EstadoExecucaoGrupo:
    uso_no_mes: dict[str, int] = field(default_factory=dict)
    ultima_data_usada: dict[str, date] = field(default_factory=dict)
    historico_total: dict[str, int] = field(default_factory=dict)
    zumbis_prioritarios: set[str] = field(default_factory=set)
    nomes_usados_por_linha_vizinha: dict[int, set[str]] = field(default_factory=dict)


def avaliar_candidatos_para_slot(
    candidatos: list[RegraColaborador],
    slot: SlotAgenda,
    estado: EstadoExecucaoGrupo,
    mapa_limites_locais: dict[str, int],
    requisito_tema: str | None,
    ignorar_vizinhanca_e_descanso: bool,
    excluse_header: dict[str, int] | None = None,
    excluse_rows: list[list[str]] | None = None,
) -> tuple[list[CandidatoRuntime], list[CandidatoRuntime]]:
    """Devolve (validos, violadores_de_semana_alternada_mas_ainda_elegiveis)."""
    validos: list[CandidatoRuntime] = []
    violadores_sem_alt: list[CandidatoRuntime] = []

    vizinhos = estado.nomes_usados_por_linha_vizinha.get(slot.row_index, set())

    for regra in candidatos:
        limite = mapa_limites_locais.get(regra.nome, regra.cota_base)
        if estado.uso_no_mes.get(regra.nome, 0) >= limite:
            continue
        if excluse_header is not None and excluse_rows is not None:
            if esta_bloqueado_por_excluse(
                regra.nome, regra.departamento, regra.funcao, slot, excluse_header, excluse_rows
            ):
                continue
        if not is_valid_preferred_week(regra.semana_preferencial, slot.data):
            # Semana preferencial e considerada no sorter, nao aqui, exceto
            # quando sem0 aponta para uma semana totalmente incompativel com
            # ALOCAR_TODOS_OS_MESES=false: mantemos permissivo aqui e deixamos
            # o desempate priorizar quem respeita a preferencia.
            pass
        if not is_tema_compativel(regra.temas, requisito_tema, regra.funcao, regra.dia_da_semana):
            continue

        cand = CandidatoRuntime(regra=regra)
        cand.is_zombie_recuperado = regra.nome in estado.zumbis_prioritarios

        tem_conflito_vizinhanca = has_neighbor_conflict(regra.nome, vizinhos)
        respeita_descanso = respeita_descanso_minimo(
            estado.ultima_data_usada.get(regra.nome), slot.data
        )

        if not ignorar_vizinhanca_e_descanso:
            if regra.sinc_colaborador and regra.sinc_colaborador in vizinhos:
                cand.is_sinc_natural = True
            if tem_conflito_vizinhanca and not cand.is_sinc_natural:
                continue
            if not respeita_descanso:
                if regra.sinc_colaborador:
                    cand.is_sinc_forced = True
                else:
                    continue

        validos.append(cand)

    if ignorar_vizinhanca_e_descanso:
        # Fase de resgate: quem violaria "semana alternada" por causa do
        # descanso ignorado fica marcado e penalizado (vai para o fim da
        # ordenacao), mas continua elegivel.
        for cand in validos:
            if cand.regra.semana_alternada:
                respeita_descanso = respeita_descanso_minimo(
                    estado.ultima_data_usada.get(cand.regra.nome), slot.data
                )
                if not respeita_descanso:
                    cand.is_sem_alt_violation = True
                    violadores_sem_alt.append(cand)

    return validos, violadores_sem_alt


def alocar_grupo(
    regras_grupo: list[RegraColaborador],
    slots_grupo: list[SlotAgenda],
    estado: EstadoExecucaoGrupo,
    mapa_limites_locais: dict[str, int],
    requisitos_tema_por_slot: dict[int, str] | None = None,
    funcao_tem_restricao_ceia: bool = False,
    slots_ceia: set[int] | None = None,
    excluse_header: dict[str, int] | None = None,
    excluse_rows: list[list[str]] | None = None,
) -> list[DecisaoAlocacao]:
    requisitos_tema_por_slot = requisitos_tema_por_slot or {}
    slots_ceia = slots_ceia or set()
    decisoes: list[DecisaoAlocacao] = []

    for slot in sorted(slots_grupo, key=lambda s: s.data):
        requisito_tema = requisitos_tema_por_slot.get(slot.row_index)

        validos, _ = avaliar_candidatos_para_slot(
            regras_grupo, slot, estado, mapa_limites_locais, requisito_tema,
            ignorar_vizinhanca_e_descanso=False,
            excluse_header=excluse_header, excluse_rows=excluse_rows,
        )

        usou_resgate = False
        if not validos:
            usou_resgate = True
            validos, violadores = avaliar_candidatos_para_slot(
                regras_grupo, slot, estado, mapa_limites_locais, requisito_tema,
                ignorar_vizinhanca_e_descanso=True,
                excluse_header=excluse_header, excluse_rows=excluse_rows,
            )

        if not validos:
            decisoes.append(
                DecisaoAlocacao(
                    slot=slot, vencedor=None, motivo="SEM ALOCAÇÃO",
                    sem_alocacao=True,
                )
            )
            continue

        ctx = ContextoDesempate(
            slot=slot,
            uso_mes_anterior=estado.uso_no_mes,
            ja_usou_no_mes_atual={
                nome: estado.uso_no_mes.get(nome, 0) > 0 for nome in estado.uso_no_mes
            },
            historico_total=estado.historico_total,
            zumbis_prioritarios=estado.zumbis_prioritarios,
            funcao_tem_restricao_ceia=funcao_tem_restricao_ceia,
            slot_e_ceia=slot.row_index in slots_ceia,
        )
        ordenados = ordenar_candidatos(validos, ctx)
        vencedor = ordenados[0]
        runner_up = ordenados[1] if len(ordenados) > 1 else None

        motivo = "RESGATE" if usou_resgate else "ALOCAÇÃO NORMAL"
        if vencedor.is_sinc_forced or vencedor.is_sinc_natural:
            motivo = "SINCRONIZAÇÃO"

        estado.uso_no_mes[vencedor.nome] = estado.uso_no_mes.get(vencedor.nome, 0) + 1
        estado.ultima_data_usada[vencedor.nome] = slot.data
        estado.historico_total[vencedor.nome] = estado.historico_total.get(vencedor.nome, 0) + 1
        estado.nomes_usados_por_linha_vizinha.setdefault(slot.row_index, set()).add(vencedor.nome)
        estado.zumbis_prioritarios.discard(vencedor.nome)

        decisoes.append(
            DecisaoAlocacao(
                slot=slot,
                vencedor=vencedor.nome,
                motivo=motivo,
                candidatos_avaliados=[c.nome for c in ordenados],
                runner_up=runner_up.nome if runner_up else None,
            )
        )

    return decisoes
