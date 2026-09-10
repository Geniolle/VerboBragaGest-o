"""Conversao das linhas cruas das sheets (list[list[str]]) para os modelos
tipados do orquestrador. Equivalente ao idxAlg()/idxAg() + loops de leitura
do Apps Script original: acesso as colunas sempre por NOME do cabecalho,
nunca por posicao fixa, para tolerar colunas reordenadas/adicionadas."""

from __future__ import annotations

import json
from datetime import date

from pastoreio_orquestrador.columns import (
    ColAppAnualGlobal,
    ColBpAlgoritimo,
    ColBpLog,
    ColConfAlgoritimo,
    ColLivros,
    ColLogAlgoritimo,
)
from pastoreio_orquestrador.models import (
    RegistroBpLog,
    RegraColaborador,
    SlotAgenda,
    TemaClassificado,
)
from pastoreio_orquestrador.parsing_utils import (
    is_last_occurrence_of_month,
    month_key,
    parse_bool,
    parse_date_ddmmyyyy,
    parse_int,
    week_of_month,
)


def build_header_index(header: list[str]) -> dict[str, int]:
    return {nome.strip(): i for i, nome in enumerate(header)}


def get(row: list[str], idx: dict[str, int], nome_coluna: str, default: str = "") -> str:
    i = idx.get(nome_coluna)
    if i is None or i >= len(row):
        return default
    return row[i]


def carregar_regras_colaboradores(valores: list[list[str]]) -> list[RegraColaborador]:
    """Le BP ALGORITIMO e devolve apenas as regras com ATIVO=true."""
    if not valores:
        return []
    idx = build_header_index(valores[0])
    regras: list[RegraColaborador] = []

    for row_i, row in enumerate(valores[1:], start=1):
        if not parse_bool(get(row, idx, ColBpAlgoritimo.ATIVO)):
            continue
        nome = get(row, idx, ColBpAlgoritimo.NOME).strip()
        departamento = get(row, idx, ColBpAlgoritimo.DEPARTAMENTO).strip()
        funcao = get(row, idx, ColBpAlgoritimo.FUNCAO).strip()
        dia_da_semana = get(row, idx, ColBpAlgoritimo.DIA_DA_SEMANA).strip().upper()
        if not (nome and departamento and funcao and dia_da_semana):
            # Linhas so-departamento (sem funcao/dia definidos) nao formam
            # uma regra de escala executavel.
            continue

        temas_raw = get(row, idx, ColBpAlgoritimo.TEMA).strip()
        temas = [t.strip() for t in temas_raw.split(";") if t.strip()] if temas_raw else []

        sinc = get(row, idx, ColBpAlgoritimo.SINC_COLABORADOR).strip()

        regras.append(
            RegraColaborador(
                id_table=get(row, idx, ColBpAlgoritimo.ID_TABLE),
                nome=nome,
                departamento=departamento,
                funcao=funcao,
                dia_da_semana=dia_da_semana,
                prioridade=parse_int(get(row, idx, ColBpAlgoritimo.PRIORIDADE), default=999),
                repeticao_mensal=parse_int(get(row, idx, ColBpAlgoritimo.REPETICAO_MENSAL), default=1),
                alocar_todos_os_meses=parse_bool(get(row, idx, ColBpAlgoritimo.ALOCAR_TODOS_OS_MESES)),
                semana_preferencial=parse_int(get(row, idx, ColBpAlgoritimo.SEMANA_PREFERENCIAL), default=0),
                ceia_alternada=parse_bool(get(row, idx, ColBpAlgoritimo.CEIA_ALTERNADA)),
                semana_alternada=parse_bool(get(row, idx, ColBpAlgoritimo.SEMANA_ALTERNADA)),
                alocacao_extra=parse_int(get(row, idx, ColBpAlgoritimo.ALOCACAO_EXTRA), default=0),
                atribuir_aos_recados=parse_bool(get(row, idx, ColBpAlgoritimo.ATRIBUIR_AOS_RECADOS)),
                perfil_autorizacao=parse_bool(get(row, idx, ColBpAlgoritimo.PERFIL_AUTORIZACAO)),
                sinc_colaborador=sinc or None,
                sinc_sem_alocacao=parse_bool(get(row, idx, ColBpAlgoritimo.SINC_SEM_ALOCACAO)),
                temas=temas,
                ativo=True,
                row_index_bp=row_i,
            )
        )
    return regras


def extrair_assiduidade_da_linha(row: list[str], idx: dict[str, int]) -> dict[str, str]:
    """Le as 30 colunas ASSIDUIDADE1..30 de uma linha de AppAnualGlobal --
    cada uma registra o colaborador AUSENTE (indisponivel para escala)
    naquela data, nao sao genericas nem ruido. Qual ASSIDUIDADEn conflita
    com qual departamento/funcao e resolvido consultando a aba Excluse (ver
    `esta_bloqueado_por_excluse` em motor.py)."""
    return {
        col: valor
        for col in ColAppAnualGlobal.colunas_assiduidade()
        if (valor := get(row, idx, col).strip())
    }


# Colunas de AppAnualGlobal que NAO representam um "papel" (funcao com um
# colaborador alocado) -- sao metadados da linha ou rotulos de secao (cujo
# proprio valor e so o nome da secao, ex.: DIACONATO="DIACONATO"). Excluidas
# de `extrair_papeis_da_linha` junto com toda coluna "EMAIL ..." e
# "ASSIDUIDADE<n>" (essa ultima tratada a parte, ver `extrair_assiduidade_da_linha`).
_COLUNAS_METADADOS_APPANUALGLOBAL = {
    "PERÍODO", "MÊS", "DIA DA SEMANA", "DATA", "MINISTROS", "EVENTO 1",
    "TEMA", "LINK", "TEMA DA MINISTRAÇÃO", "SLIDES", "VIDEO", "YOUTUBE",
    "DIACONATO", "CRIANÇAS", "LOUVOR", "COMUNICAÇÃO", "LIVRARIA", "CANTINA",
    "CENTRO DE CURA", "LIÇÃO (D.I)", "LIÇÃO (S2)", "LIÇÃO (S3)", "LIÇÃO (S4)",
} | {f"VERSICULO{i}" for i in range(1, 11)}


def extrair_papeis_da_linha(row: list[str], idx: dict[str, int]) -> dict[str, str]:
    """Le todas as colunas de "papel" (funcao com um colaborador alocado,
    ex.: "PORTARIA FRENTE1", "PROFESSOR(A) (S1)") de uma linha de
    AppAnualGlobal -- qualquer coluna que nao seja metadado/rotulo de
    secao, "EMAIL ..." ou "ASSIDUIDADE<n>" -- mapeando NOME DO PAPEL (igual
    ao usado na coluna "COLUNAS" da aba Excluse) para o NOME do colaborador
    alocado ali nessa data. Usado por `esta_bloqueado_por_excluse` em
    motor.py para achar conflitos reais entre papeis (ver nota no topo do
    motor.py)."""
    papeis: dict[str, str] = {}
    for col_name, col_i in idx.items():
        if col_name in _COLUNAS_METADADOS_APPANUALGLOBAL:
            continue
        if col_name.upper().startswith("EMAIL"):
            continue
        if col_name.upper().startswith("ASSIDUIDADE"):
            continue
        valor = row[col_i].strip() if col_i < len(row) else ""
        if valor:
            papeis[col_name] = valor
    return papeis


def carregar_slots_agenda(valores: list[list[str]]) -> list[SlotAgenda]:
    """Le AppAnualGlobal e devolve os metadados de cada linha (data, dia da
    semana, tema, semana do mes, assiduidade). A leitura/escrita da coluna
    especifica de cada funcao (ex.: MINISTRO, CEIA) e feita à parte, por
    linha, quando o motor avalia um grupo departamento+funcao+dia."""
    if not valores:
        return []
    idx = build_header_index(valores[0])
    slots: list[SlotAgenda] = []

    for row_i, row in enumerate(valores[1:], start=1):
        data_txt = get(row, idx, ColAppAnualGlobal.DATA).strip()
        d = parse_date_ddmmyyyy(data_txt)
        if d is None:
            continue
        slots.append(
            SlotAgenda(
                row_index=row_i,
                data=d,
                dia_da_semana=get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip(),
                tema=get(row, idx, ColAppAnualGlobal.TEMA).strip(),
                mes_key=month_key(d),
                semana_do_mes=week_of_month(d),
                is_ultima_ocorrencia_do_mes=is_last_occurrence_of_month(d),
                assiduidade=extrair_assiduidade_da_linha(row, idx),
                papeis=extrair_papeis_da_linha(row, idx),
            )
        )
    return slots


def carregar_temas(valores: list[list[str]]) -> list[TemaClassificado]:
    if not valores:
        return []
    idx = build_header_index(valores[0])
    temas: list[TemaClassificado] = []
    for row in valores[1:]:
        tema = get(row, idx, ColLivros.TEMA).strip()
        if not tema:
            continue
        temas.append(
            TemaClassificado(
                dia_da_semana=get(row, idx, ColLivros.DIA_DA_SEMANA).strip().upper(),
                tema=tema,
                classificacao=get(row, idx, ColLivros.CLASSIFICACAO).strip().upper(),
            )
        )
    return temas


def carregar_conf_algoritimo(valores: list[list[str]]) -> dict[str, str]:
    if not valores:
        return {}
    idx = build_header_index(valores[0])
    conf: dict[str, str] = {}
    for row in valores[1:]:
        processo = get(row, idx, ColConfAlgoritimo.PROCESSO).strip()
        if processo:
            conf[processo] = get(row, idx, ColConfAlgoritimo.VALOR).strip()
    return conf


def carregar_bp_log(valores: list[list[str]]) -> list[RegistroBpLog]:
    if not valores:
        return []
    idx = build_header_index(valores[0])
    registros: list[RegistroBpLog] = []
    for row in valores[1:]:
        nome = get(row, idx, ColBpLog.NOME).strip()
        if not nome:
            continue
        registros.append(
            RegistroBpLog(
                departamento=get(row, idx, ColBpLog.DEPARTAMENTO).strip(),
                processo=get(row, idx, ColBpLog.PROCESSO).strip(),
                nome=nome,
                mes_nao_alocados=get(row, idx, ColBpLog.MES_NAO_ALOCADOS).strip(),
                disponibilidade=parse_bool(get(row, idx, ColBpLog.DISPONIBILIDADE)),
                timestamp_utilizacao=get(row, idx, ColBpLog.TIMESTAMP_UTILIZACAO).strip(),
            )
        )
    return registros


def carregar_historico_alocacoes(valores: list[list[str]], funcao: str) -> dict[str, int]:
    """Le LOG ALGORITIMO (execucoes passadas com Status='Ativo') e conta
    quantas vezes cada colaborador ja foi alocado na `funcao` dada, a partir
    do JSON de "Alocações (JSON)". Usado como historico_total no desempate,
    para dar prioridade a quem foi alocado menos vezes no passado."""
    if not valores:
        return {}
    idx = build_header_index(valores[0])
    historico: dict[str, int] = {}
    for row in valores[1:]:
        if get(row, idx, ColLogAlgoritimo.STATUS).strip() != "Ativo":
            continue
        alocacoes_txt = get(row, idx, ColLogAlgoritimo.ALOCACOES_JSON).strip()
        if not alocacoes_txt:
            continue
        try:
            alocacoes = json.loads(alocacoes_txt)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in alocacoes:
            if not isinstance(item, dict):
                continue
            if item.get("funcao", "").strip().upper() != funcao.strip().upper():
                continue
            nome = item.get("nome", "").strip()
            if nome:
                historico[nome] = historico.get(nome, 0) + 1
    return historico


def carregar_zumbis_prioritarios(
    bp_log: list[RegistroBpLog], departamento: str, processo: str
) -> set[str]:
    """Colaboradores com um registro em BP LOG ainda pendente de recuperacao
    (DISPONIBILIDADE=TRUE = ainda nao foram priorizados numa alocacao
    seguinte) para o departamento/processo dado."""
    return {
        r.nome
        for r in bp_log
        if r.departamento == departamento
        and r.processo.strip().upper() == processo.strip().upper()
        and r.disponibilidade
    }


def carregar_excluse_matriz(valores: list[list[str]]) -> tuple[dict[str, int], list[list[str]]]:
    """Devolve (indice_de_cabecalho, linhas_de_dados) da aba Excluse, para
    ser consultada por checkAssignment de acordo com o PROCESSO/COLUNAS."""
    if not valores:
        return {}, []
    return build_header_index(valores[0]), valores[1:]


def carregar_compromissos_cruzados(
    agenda_valores: list[list[str]],
    col_nome: str,
    dia_da_semana_excluido: str,
) -> dict[str, list[date]]:
    """Le AppAnualGlobal/CLAUDE_AppAnualGlobal inteira e devolve, para a MESMA
    coluna de funcao (`col_nome`, ex.: "MINISTRO") mas em qualquer DIA DA
    SEMANA diferente de `dia_da_semana_excluido`, {NOME em maiusculas:
    [datas ja confirmadas]}. Usado para o filtro "descanso minimo cruzado"
    (2026-09-08, pedido do Clayton): a mesma pessoa nao pode ser escalada na
    MESMA funcao em dois dias da semana diferentes (ex.: domingo e a quarta-
    feira seguinte) se a distancia for menor que `DESCANSO_MINIMO_DIAS` --
    ver `esta_bloqueado_por_descanso_cruzado` em motor.py. Ignora celulas
    vazias e o literal "SEM ALOCAÇÃO" (nao e um compromisso real)."""
    if not agenda_valores:
        return {}
    idx = build_header_index(agenda_valores[0])
    compromissos: dict[str, list[date]] = {}
    for row in agenda_valores[1:]:
        dia = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if not dia or dia_da_semana_excluido.strip().upper() in dia:
            continue
        nome = get(row, idx, col_nome).strip()
        if not nome or nome.upper() == "SEM ALOCAÇÃO":
            continue
        data = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if data is None:
            continue
        compromissos.setdefault(nome.upper(), []).append(data)
    return compromissos


def carregar_aniversarios(valores: list[list[str]]) -> dict[str, date]:
    """Le a aba BP SERVICE e devolve {NOME em maiusculas: data_de_nascimento},
    para o filtro obrigatorio de "nao alocar o aniversariante no proprio dia
    de servico" (pedido do Clayton, 2026-09-07 -- ver caso real do Ronda 1:
    Patricia Lopes nasceu em 25/10 e foi alocada em 25/10/2026). Linhas sem
    NOME ou sem DATA NASCIMENTO parseavel sao ignoradas."""
    if not valores:
        return {}
    idx = build_header_index(valores[0])
    aniversarios: dict[str, date] = {}
    for row in valores[1:]:
        nome = get(row, idx, "NOME").strip().upper()
        if not nome:
            continue
        nascimento = parse_date_ddmmyyyy(get(row, idx, "DATA NASCIMENTO").strip())
        if nascimento is None:
            continue
        aniversarios[nome] = nascimento
    return aniversarios
