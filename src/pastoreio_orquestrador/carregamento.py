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
from pastoreio_orquestrador.historico import dentro_do_historico_do_novo_motor
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


# Colunas de BP ALGORITIMO sem as quais uma regra nao pode ser avaliada
# corretamente -- se QUALQUER uma faltar no cabecalho, `get()` devolveria o
# valor default silenciosamente (ex.: prioridade=999 para todo mundo) em vez
# de falhar de forma visivel.
#
# Adicionado 2026-09-11 (pedido do Clayton, investigacao do grupo novo
# D. MINISTROS/CEIA): o cabecalho de "CLAUDE_BP ALGORITIMO" ficou com a
# coluna G em branco (deveria ser "PRIORIDADE NA ALOCAÇÃO") depois de
# "SEMANA PREFERENCIAL" ter sido reposicionada em 2026-09-08 sem atualizar o
# texto do cabecalho -- `idx.get("PRIORIDADE NA ALOCAÇÃO")` devolvia `None`
# e TODO MUNDO, em TODOS os grupos, era carregado com prioridade=999 sem
# nenhum aviso. So nao tinha quebrado nenhum resultado ate entao porque a
# ordem das linhas na sheet coincidia, por acaso, com a ordem de prioridade
# pretendida (o desempate por ordem de insercao mascarava o problema). Esta
# checagem torna esse tipo de corrupcao de cabecalho um erro alto e claro,
# em vez de um defeito silencioso.
COLUNAS_OBRIGATORIAS_BP_ALGORITIMO = (
    ColBpAlgoritimo.NOME,
    ColBpAlgoritimo.DEPARTAMENTO,
    ColBpAlgoritimo.FUNCAO,
    ColBpAlgoritimo.DIA_DA_SEMANA,
    ColBpAlgoritimo.PRIORIDADE,
    ColBpAlgoritimo.REPETICAO_MENSAL,
    ColBpAlgoritimo.ALOCAR_TODOS_OS_MESES,
    ColBpAlgoritimo.SEMANA_PREFERENCIAL,
    ColBpAlgoritimo.CEIA_ALTERNADA,
    ColBpAlgoritimo.SEMANA_ALTERNADA,
    ColBpAlgoritimo.ALOCACAO_EXTRA,
    ColBpAlgoritimo.ATIVO,
)


def validar_cabecalho_bp_algoritimo(idx: dict[str, int]) -> list[str]:
    """Devolve os nomes de coluna obrigatorios que nao existem no
    cabecalho (idx construido por `build_header_index`)."""
    return [nome for nome in COLUNAS_OBRIGATORIAS_BP_ALGORITIMO if nome not in idx]


def _normalizar_tipo_alocacao(valor: str) -> str | None:
    valor = valor.strip().upper()
    return valor or None


def _carregar_config_recorrencia_fixa(
    row: list[str],
    idx: dict[str, int],
    *,
    nome: str,
    semana_preferencial: int,
) -> tuple[str | None, int | None, date | None]:
    tipo_alocacao = _normalizar_tipo_alocacao(get(row, idx, ColBpAlgoritimo.TIPO_ALOCACAO))
    if tipo_alocacao != "FIXO_RECORRENTE":
        return tipo_alocacao, None, None

    intervalo_raw = get(row, idx, ColBpAlgoritimo.INTERVALO_MESES).strip()
    if not intervalo_raw:
        raise ValueError(f"{nome}: FIXO_RECORRENTE exige INTERVALO MESES.")
    try:
        intervalo_meses = int(intervalo_raw)
    except ValueError as exc:
        raise ValueError(f"{nome}: INTERVALO MESES invalido para FIXO_RECORRENTE: {intervalo_raw!r}.") from exc
    if intervalo_meses <= 0:
        raise ValueError(f"{nome}: INTERVALO MESES deve ser positivo para FIXO_RECORRENTE.")

    data_raw = get(row, idx, ColBpAlgoritimo.DATA_INICIO_RECORRENCIA).strip()
    if not data_raw:
        raise ValueError(f"{nome}: FIXO_RECORRENTE exige DATA INÍCIO RECORRÊNCIA.")
    partes_data = data_raw.split("/")
    if len(partes_data) != 3 or [len(parte) for parte in partes_data] != [2, 2, 4]:
        raise ValueError(f"{nome}: DATA INÍCIO RECORRÊNCIA invalida para FIXO_RECORRENTE: {data_raw!r}.")
    data_inicio = parse_date_ddmmyyyy(data_raw)
    if data_inicio is None:
        raise ValueError(f"{nome}: DATA INÍCIO RECORRÊNCIA invalida para FIXO_RECORRENTE: {data_raw!r}.")

    if semana_preferencial < 1 or semana_preferencial > 5:
        raise ValueError(f"{nome}: FIXO_RECORRENTE exige SEMANA PREFERENCIAL entre 1 e 5.")

    return tipo_alocacao, intervalo_meses, data_inicio


def carregar_regras_colaboradores(valores: list[list[str]]) -> list[RegraColaborador]:
    """Le BP ALGORITIMO e devolve apenas as regras com ATIVO=true."""
    if not valores:
        return []
    idx = build_header_index(valores[0])
    faltando = validar_cabecalho_bp_algoritimo(idx)
    if faltando:
        raise ValueError(
            "Cabecalho de BP ALGORITIMO sem coluna(s) obrigatoria(s): "
            + ", ".join(repr(n) for n in faltando)
            + ". Provavel corrupcao/reposicionamento de coluna sem atualizar o cabecalho."
        )
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
        semana_preferencial = parse_int(get(row, idx, ColBpAlgoritimo.SEMANA_PREFERENCIAL), default=0)
        tipo_alocacao, intervalo_meses, data_inicio_recorrencia = _carregar_config_recorrencia_fixa(
            row,
            idx,
            nome=nome,
            semana_preferencial=semana_preferencial,
        )

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
                semana_preferencial=semana_preferencial,
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
                tipo_alocacao=tipo_alocacao,
                intervalo_meses=intervalo_meses,
                data_inicio_recorrencia=data_inicio_recorrencia,
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


def contar_ocorrencias_mensais_por_colaborador(
    agenda_valores: list[list[str]],
    dia_da_semana: str,
    colunas_participacao: list[str] | tuple[str, ...],
    nomes_validos: dict[str, str] | None = None,
    *,
    data_corte_historico: date | None = None,
) -> dict[str, dict[str, int]]:
    """Conta participacoes reais por colaborador+mes na AppAnualGlobal.

    A funcao e deliberadamente parametrizada por colunas: para
    D. MINISTROS/MINISTRO/DOMINGO, a quota mensal pode considerar a coluna
    MINISTRO (quando a propria agenda e a fonte unica da simulacao) e a
    coluna CEIA (quando a CEIA ja foi escrita por seu processo proprio).
    Auditoria/log nao entram aqui para evitar dupla contagem.
    """
    if not agenda_valores:
        return {}
    idx = build_header_index(agenda_valores[0])
    nomes_validos = nomes_validos or {}
    resultado: dict[str, dict[str, int]] = {}
    for row in agenda_valores[1:]:
        dia = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if dia_da_semana.strip().upper() not in dia:
            continue
        data = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if data is None:
            continue
        if not dentro_do_historico_do_novo_motor(data, data_corte_historico):
            continue
        mes = month_key(data)
        for coluna in colunas_participacao:
            nome = get(row, idx, coluna).strip()
            if not nome or nome.upper() == "SEM ALOCAÇÃO":
                continue
            nome = nomes_validos.get(nome.upper(), nome)
            contagem_nome = resultado.setdefault(nome, {})
            contagem_nome[mes] = contagem_nome.get(mes, 0) + 1
    return resultado


def carregar_historico_coluna_agenda(
    agenda_valores: list[list[str]],
    dia_da_semana: str,
    coluna_participacao: str,
    nomes_validos: dict[str, str] | None = None,
    *,
    somente_primeiro_domingo: bool = False,
    antes_de: date | None = None,
) -> list[str]:
    """Le vencedores reais de uma coluna da agenda em ordem cronologica.

    Usado para reconstruir rodizios que precisam sobreviver a novas execucoes
    do processo Python. A AppAnualGlobal continua sendo a fonte da escala real:
    auditoria explica a decisao, mas o historico de participantes precisa
    confirmar quem ficou persistido na agenda.
    """
    if not agenda_valores:
        return []

    idx = build_header_index(agenda_valores[0])
    nomes_validos = nomes_validos or {}
    registros: list[tuple[date, int, str]] = []

    for row_i, row in enumerate(agenda_valores[1:], start=1):
        dia = get(row, idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if dia_da_semana.strip().upper() not in dia:
            continue

        data = parse_date_ddmmyyyy(get(row, idx, ColAppAnualGlobal.DATA).strip())
        if data is None:
            continue
        if antes_de is not None and data >= antes_de:
            continue
        if somente_primeiro_domingo and week_of_month(data) != 1:
            continue

        nome = get(row, idx, coluna_participacao).strip()
        if not nome or nome.upper() == "SEM ALOCAÇÃO":
            continue
        registros.append((data, row_i, nomes_validos.get(nome.upper(), nome)))

    registros.sort(key=lambda item: (item[0], item[1]))
    return [nome for _, _, nome in registros]


def _header_index_upper(header: list[str]) -> dict[str, int]:
    return {str(nome).strip().upper(): i for i, nome in enumerate(header)}


def _get_upper(row: list[str], idx: dict[str, int], nome_coluna: str, default: str = "") -> str:
    i = idx.get(nome_coluna.strip().upper())
    if i is None or i >= len(row):
        return default
    return str(row[i])


def _parse_data_historico(valor: str) -> date | None:
    valor = str(valor).strip()
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return parse_date_ddmmyyyy(valor)


def _linha_auditoria_ceia(row: list[str], idx: dict[str, int]) -> bool:
    intent = _get_upper(row, idx, "INTENCAO_ALOCACAO").strip().upper()
    tipo = _get_upper(row, idx, "TIPO_ALOCACAO").strip().upper()
    motivo = _get_upper(row, idx, "MOTIVO").strip().upper()
    return intent == "CEIA" or tipo == "CEIA" or motivo == "CEIA ALTERNADA"


def carregar_historico_ceia_persistido(
    agenda_valores: list[list[str]],
    auditoria_valores: list[list[str]],
    dia_da_semana: str,
    coluna_alocacao: str,
    nomes_validos: dict[str, str] | None = None,
    *,
    antes_de: date | None = None,
    data_corte_historico: date | None = None,
) -> list[str]:
    """Reconstrui a sequencia real de CEIA a partir de dados persistidos.

    Para o fluxo D. MINISTROS/MINISTRO/DOMINGO, a CEIA pode estar escrita na
    coluna MINISTRO. Por isso, a data so entra no historico quando a auditoria
    identifica aquela alocacao como CEIA e a agenda confirma que o mesmo
    vencedor continua persistido na coluna lida. O motor atual nao e usado
    para recalcular quem "deveria" ter vencido no passado.
    """
    if not agenda_valores or not auditoria_valores:
        return []

    agenda_idx = build_header_index(agenda_valores[0])
    auditoria_idx = _header_index_upper(auditoria_valores[0])
    nomes_validos = nomes_validos or {}

    agenda_por_data: dict[date, str] = {}
    row_por_data: dict[date, int] = {}
    for row_i, row in enumerate(agenda_valores[1:], start=1):
        dia = get(row, agenda_idx, ColAppAnualGlobal.DIA_DA_SEMANA).strip().upper()
        if dia_da_semana.strip().upper() not in dia:
            continue
        data = parse_date_ddmmyyyy(get(row, agenda_idx, ColAppAnualGlobal.DATA).strip())
        if data is None:
            continue
        if not dentro_do_historico_do_novo_motor(data, data_corte_historico):
            continue
        if antes_de is not None and data >= antes_de:
            continue
        nome = get(row, agenda_idx, coluna_alocacao).strip()
        if not nome or nome.upper() == "SEM ALOCAÇÃO":
            continue
        agenda_por_data[data] = nome
        row_por_data[data] = row_i

    registros: list[tuple[date, int, str]] = []
    datas_vistas: set[date] = set()
    for row in auditoria_valores[1:]:
        if not _linha_auditoria_ceia(row, auditoria_idx):
            continue
        data = _parse_data_historico(_get_upper(row, auditoria_idx, "DATA_SLOT"))
        if data is None or data in datas_vistas:
            continue
        if not dentro_do_historico_do_novo_motor(data, data_corte_historico):
            continue
        if antes_de is not None and data >= antes_de:
            continue
        vencedor_auditoria = _get_upper(row, auditoria_idx, "VENCEDOR").strip()
        vencedor_agenda = agenda_por_data.get(data, "").strip()
        if not vencedor_auditoria or not vencedor_agenda:
            continue
        if vencedor_auditoria.upper() != vencedor_agenda.upper():
            continue
        datas_vistas.add(data)
        registros.append((data, row_por_data.get(data, 0), nomes_validos.get(vencedor_agenda.upper(), vencedor_agenda)))

    registros.sort(key=lambda item: (item[0], item[1]))
    return [nome for _, _, nome in registros]


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


def carregar_emails(valores: list[list[str]]) -> dict[str, str]:
    """Le a aba BP SERVICE e devolve {NOME em maiusculas: EMAIL}, para
    escrever automaticamente o email do colaborador alocado na coluna
    "EMAIL <FUNÇÃO>" ao lado da coluna de alocacao em AppAnualGlobal (pedido
    do Clayton, 2026-09-11 -- ex.: quem for escrito em MINISTRO tem o email
    escrito em "EMAIL MINISTRO", quem for escrito em CEIA tem o email
    escrito em "EMAIL CEIA"). Usa a coluna "EMAIL" (nao "USEREMAIL", que
    registra quem sincronizou o cadastro, nao o proprio email da pessoa).
    Linhas sem NOME ou sem EMAIL sao ignoradas -- nomes sem email cadastrado
    (ex.: "Culto de Oração", que e um placeholder, nao uma pessoa) apenas
    nao geram entrada, e a celula de email fica em branco."""
    if not valores:
        return {}
    idx = build_header_index(valores[0])
    emails: dict[str, str] = {}
    for row in valores[1:]:
        nome = get(row, idx, "NOME").strip().upper()
        if not nome:
            continue
        email = get(row, idx, "EMAIL").strip()
        if not email:
            continue
        emails[nome] = email
    return emails
