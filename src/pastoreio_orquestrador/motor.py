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

NOTA sobre a aba "Excluse" (entendimento final, confirmado por Clayton em
2026-09-07 apos tres correcoes anteriores estarem erradas): a aba tem uma
linha por PAPEL (coluna "COLUNAS", ex.: "MINISTRO", "AUXILIAR", "CEIA",
"PORTARIA FRENTE1", "PROFESSOR(A) (S1)"...) e, para cada departamento, uma
coluna "ID_<DEPARTAMENTO>" (ex.: "ID_MINISTROS", indice B). O que importa
NAO e o rotulo da linha (COLUNAS) nem se a celula esta preenchida -- e se o
NOME LITERAL de um papel aparece como VALOR em ALGUMA linha da coluna
"ID_<DEPARTAMENTO>" (busca em B2:B, nao so a linha cujo COLUNAS==funcao).

Ex. real: a coluna ID_MINISTROS tem, entre outras, a linha
COLUNAS="PROFESSOR(A) (S3)" / ID_MINISTROS="PROFESSOR(A) (S1)" -- o valor
"PROFESSOR(A) (S1)" aparece ali, entao um candidato ja alocado no papel
"PROFESSOR(A) (S1)" NAQUELA DATA fica bloqueado de tambem ser MINISTRO. Ja
"PORTARIA FRENTE1" tem sua PROPRIA linha preenchida (COLUNAS="PORTARIA
FRENTE1" / ID_MINISTROS="ASSIDUIDADE8"), mas o texto "PORTARIA FRENTE1"
nunca aparece como VALOR em nenhuma linha da coluna -- so como ROTULO (na
coluna COLUNAS) -- logo NAO bloqueia. Ter a propria linha preenchida (com
qualquer coisa) nao e o criterio; ser CITADO COMO VALOR em outra linha e.

CORRECAO 2026-09-07 (mesmo dia, dada verbatim por Clayton, apos eu ter
presumido erradamente que ASSIDUIDADE1..30 eram colunas genericas/ruido):
"tudo que temos no ID_<DEPARTAMENTO> e um nome de coluna" e "tudo que
temos no excluse e real e nada de generico" -- ou seja, TODO valor em
"ID_<DEPARTAMENTO>" e literalmente o NOME DE UMA COLUNA de AppAnualGlobal,
seja ela uma coluna nomeada real (ex.: "PROFESSOR(A) (S1)") OU uma coluna
"ASSIDUIDADEXX" (que registra que o colaborador esta AUSENTE naquela data
e por isso nao pode ser escalado -- nao e ruido nem mecanismo separado).
Em ambos os casos o tratamento e o MESMO: se o candidato ja tem seu nome
naquela coluna (real ou ASSIDUIDADEXX) na data do slot, ele fica bloqueado.
"Ja alocado/ausente no papel Y naquela data" e lido combinando
`SlotAgenda.papeis` (colunas nomeadas reais) e `SlotAgenda.assiduidade`
(colunas ASSIDUIDADE1..30) -- as duas sao consultadas por nome de coluna,
sem distincao de tratamento.

NOTA sobre "vizinhanca de DATAS" (2026-09-07, pedido do Clayton, apos ver o
Andre Luiz alocado em 22 E 29/11 -- dois domingos seguidos): esse conceito e
DIFERENTE de `has_neighbor_conflict`/`nomes_usados_por_linha_vizinha`, que e
sobre FUNCOES diferentes na MESMA linha/data (usado para SINC_COLABORADOR --
"esse doi e sobre a datas e nao sobre as funcoes", correcao dele mesmo).
"Vizinhanca de datas" e uma regra obrigatoria NOVA (`viola_vizinhanca_de_
datas`): ninguem pode vencer duas ocorrencias cronologicamente CONSECUTIVAS
da sequencia semanal do PROPRIO grupo (ex.: dois domingos seguidos), esteja
essa vitoria na Fase 1 (CEIA), Fase 3 (normais) ou Fase 4 (lacuna) do
algoritmo de CEIA ALTERNADA. Por pedido explicito do Clayton ("tens de
reorganizar os colaboradores... SEM ALOCACAO e quando e impossivel alguma
alocacao"), SEM ALOCACAO so pode ser o resultado quando for genuinamente
impossivel evitar a repeticao.

CORRECAO 2026-09-07 (mesmo dia, dada verbatim por Clayton, apos eu ter
tentado uma 1a versao errada da "reorganizacao" que ampliava a Fase 4 para o
GRUPO INTEIRO -- inclusive gente sem ALOCACAO EXTRA preenchida): "era so
preciso reorganizar os mesmos colaboradores que tinhas na linha... temos
que, dentro dos colaboradores, reordenar os dias daquela rotacao". Ou seja:
"reorganizar" NUNCA introduz alguem de fora da hierarquia legitima daquela
Ronda -- ela reordena QUAIS DATAS os MESMOS colaboradores ja elegiveis
recebem. Na Fase 4, quando a hierarquia de PREENCHIMENTO DE LACUNA
(ALOCAR_TODOS_OS_MESES=false E ALOCACAO_EXTRA=true) nao consegue fechar uma
data sem violar a vizinhanca (ex.: so 2 pessoas na hierarquia, a escolha
gulosa por prioridade colocou a mesma pessoa nas duas datas vizinhas), o
motor tenta um SWAP (`_tentar_reorganizar_lacuna`): encontra a data vizinha
JA DECIDIDA nesta mesma Fase 4 que causa o bloqueio e tenta reatribui-la a
OUTRO membro da mesma hierarquia, liberando o vencedor bloqueado para a data
atual -- os mesmos 2 (ou mais) colaboradores, so trocando qual data cada um
cobre. Se nenhum swap resolve (ex.: o substituto tambem esta bloqueado por
Excluse na data vizinha), SEM ALOCACAO e o resultado correto: e
genuinamente impossivel.

NOTA sobre "aniversario" (2026-09-07, pedido do Clayton, apos ver Patricia
Lopes -- nascida 25/10 -- alocada em 25/10/2026 na Ronda 1): novo filtro
obrigatorio, com o MESMO estatuto do Excluse (bloqueia em toda passada,
normal e resgate, e tambem dentro de `_tentar_reorganizar_lacuna`), so que a
fonte nao e a aba Excluse e sim a coluna "DATA NASCIMENTO" da aba "BP
SERVICE" (casada por "NOME"). `carregar_aniversarios` (carregamento.py) le
essa aba uma vez e devolve {NOME: data_de_nascimento}; `esta_bloqueado_por_
aniversario` compara so DIA+MES do slot com DIA+MES do nascimento (o ANO e
ignorado -- aniversario e recorrente). Ninguem pode ser alocado no proprio
dia de aniversario."""

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
from pastoreio_orquestrador.parsing_utils import diff_days, is_valid_preferred_week, month_key

DESCANSO_MINIMO_DIAS = 7
MAX_ITERACOES_ONDA_EXPANSIVA = 8


# ---------------------------------------------------------------------------
# 1. Agregacao de regras em grupos
# ---------------------------------------------------------------------------


def delimitar_uma_ronda(datas_disponiveis: list[date], n_colaboradores_ativos: int) -> list[date]:
    """Recorta, a partir de uma lista de datas disponiveis (ordenada, sem
    lacunas por ja-alocadas), exatamente as datas de UMA Ronda (ciclo
    completo): as primeiras `n_colaboradores_ativos` datas da rotacao base,
    estendidas ate fechar por completo o mes-calendario da ultima data da
    rotacao (ver CONCEITO_CICLO.md). Nunca retorna mais de uma Ronda -- cada
    execucao do write-back deve processar uma Ronda por vez.
    """
    if not datas_disponiveis or n_colaboradores_ativos <= 0:
        return []
    n = min(n_colaboradores_ativos, len(datas_disponiveis))
    mes_final = month_key(datas_disponiveis[n - 1])
    datas_ronda = list(datas_disponiveis[:n])
    for d in datas_disponiveis[n:]:
        if month_key(d) != mes_final:
            break
        datas_ronda.append(d)
    return datas_ronda


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
    mapa_limites_mensais: dict[str, int] = field(default_factory=dict)


def calcular_demanda_onda_expansiva(
    candidatos: list[RegraColaborador],
    vagas_reais_no_periodo: int,
    meses_tocados: int,
) -> ResultadoDemanda:
    def capacidade(usar_extra: bool) -> tuple[int, dict[str, int], dict[str, int]]:
        limites: dict[str, int] = {}
        limites_mensais: dict[str, int] = {}
        total = 0
        for c in candidatos:
            limite_mensal = c.cota_base + (c.alocacao_extra if usar_extra else 0)
            limite = limite_mensal * max(1, meses_tocados)
            limites[c.nome] = limite
            limites_mensais[c.nome] = limite_mensal
            total += limite
        return total, limites, limites_mensais

    capacidade_base, mapa_base, mapa_base_mensal = capacidade(usar_extra=False)

    usa_extra = vagas_reais_no_periodo > capacidade_base
    capacidade_total, mapa_total, mapa_total_mensal = (
        capacidade(usar_extra=True)
        if usa_extra
        else (capacidade_base, mapa_base, mapa_base_mensal)
    )

    demanda_calculada = min(vagas_reais_no_periodo, capacidade_total)

    return ResultadoDemanda(
        capacidade_base=capacidade_base,
        capacidade_total=capacidade_total,
        demanda_calculada=demanda_calculada,
        usa_cota_extra=usa_extra,
        mapa_limites_locais=mapa_total,
        mapa_limites_mensais=mapa_total_mensal,
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


def viola_vizinhanca_de_datas(
    nome: str,
    vizinhos_de_data: tuple[int | None, int | None],
    decisoes_por_row: dict[int, DecisaoAlocacao],
) -> bool:
    """Regra de "vizinhanca de DATAS" (2026-09-07, correcao do Clayton: "esse
    doi e sobre a datas e nao sobre as funcoes" -- distinta de
    `has_neighbor_conflict`, que e sobre funcoes diferentes na MESMA
    linha/data, usada para SINC_COLABORADOR, e continua intocada). Um
    colaborador nao pode vencer duas ocorrencias cronologicamente
    CONSECUTIVAS da propria sequencia semanal do grupo (ex.: dois domingos
    seguidos). `vizinhos_de_data` e a tupla (row_index_da_data_anterior,
    row_index_da_data_seguinte) dentro da sequencia do grupo -- checa os
    DOIS lados porque, no algoritmo em fases da CEIA ALTERNADA, os vizinhos
    de uma data nem sempre sao decididos em ordem cronologica (a CEIA do mes
    seguinte pode ser decidida na Fase 1 antes do ultimo domingo normal do
    mes anterior, decidido so na Fase 3); como as decisoes sao sempre
    tomadas uma de cada vez, quem quer que seja decidido POR ULTIMO dos dois
    vizinhos sempre enxerga o outro ja gravado em `decisoes_por_row`."""
    anterior_row, seguinte_row = vizinhos_de_data
    for row_idx in (anterior_row, seguinte_row):
        if row_idx is None:
            continue
        decisao = decisoes_por_row.get(row_idx)
        if decisao is not None and decisao.vencedor == nome:
            return True
    return False


def montar_vizinhos_de_data_por_row(
    slots_ordenados: list[SlotAgenda],
) -> dict[int, tuple[int | None, int | None]]:
    """Para cada slot da propria sequencia cronologica do grupo, devolve o
    row_index da data imediatamente anterior e da imediatamente seguinte
    (ou None nas pontas) -- usado por `viola_vizinhanca_de_datas`."""
    vizinhos: dict[int, tuple[int | None, int | None]] = {}
    for i, slot in enumerate(slots_ordenados):
        anterior = slots_ordenados[i - 1].row_index if i > 0 else None
        seguinte = slots_ordenados[i + 1].row_index if i < len(slots_ordenados) - 1 else None
        vizinhos[slot.row_index] = (anterior, seguinte)
    return vizinhos


NIVEL_SENIOR = "SENIOR"
NIVEL_PLENO = "PLENO"
NIVEL_JUNIOR = "JUNIOR"


def nivel_senioridade(temas: list[str]) -> str:
    """Nivel de senioridade de um colaborador, derivado da sua lista bruta
    de classificacoes aptas (`RegraColaborador.temas`, coluna TEMA de
    CLAUDE_BP ALGORITIMO) -- pedido do Clayton em 2026-09-08: "quem tem no
    intervalo o P1 e Senior. Quem tem o P2 no intervalo, mas nao tem o P1 e
    Pleno. Quem tem so o P3 e Junior". E uma hierarquia por NIVEL MAXIMO
    (nao pelo conjunto exato de classificacoes, que e o que
    `is_tema_compativel` usava antes desta correcao) -- alguem P1;P3 (sem
    P2) ainda e Senior, por exemplo."""
    temas_upper = {t.strip().upper() for t in temas}
    if "P1" in temas_upper:
        return NIVEL_SENIOR
    if "P2" in temas_upper:
        return NIVEL_PLENO
    return NIVEL_JUNIOR


def eh_fixo_sem_rodizio_de_nivel(regra: RegraColaborador) -> bool:
    """True quando `regra` deve ficar TOTALMENTE fora do rodizio por nivel de
    senioridade (QUARTA-FEIRA) -- nao conta para o tamanho da janela, nunca e
    bloqueada por ela, e sua vitoria nao entra no historico.

    CORRECAO 2026-09-10 original: ter SEMANA PREFERENCIAL preenchida
    (`!= 0`) por si so ja tirava a pessoa do rodizio, sob a logica de que a
    propria semana preferencial ja restringe suas datas possiveis. Isso
    quebrou quando DUAS OU MAIS pessoas do mesmo NIVEL compartilham a MESMA
    semana preferencial (ex.: Fernando Mauricio e Gislane Ferreira, ambos
    PLENO + SEMANA PREFERENCIAL=5/ultima-semana): sem rodizio entre eles, o
    desempate cai direto em PRIORIDADE (`chave_ordenacao_candidato`), entao o
    de prioridade pior nunca vence, indefinidamente -- nao e falta de vaga
    compativel, e falta de alternancia entre os proprios "fixos".

    CORRECAO 2026-09-10 (pedido verbatim do Clayton, mesmo dia): a isencao de
    rodizio agora exige tambem `PERFIL DE AUTORIZAÇÃO=true`, alem de
    `SEMANA PREFERENCIAL != 0`. Quem tem semana preferencial cadastrada mas
    NAO tem esse perfil continua sujeito ao filtro obrigatorio de semana
    (`is_valid_preferred_week`, inalterado) -- so pode ser escalado na sua
    semana -- mas agora participa de ALGUMA forma de rodizio (ver
    `chave_rodizio_nivel` para os detalhes de qual)."""
    return regra.semana_preferencial != 0 and regra.perfil_autorizacao


def chave_rodizio_nivel(regra: RegraColaborador, nivel: str) -> str | None:
    """Chave de agrupamento em `EstadoExecucaoGrupo.historico_vencedores_por_nivel`
    usada pelo rodizio de QUARTA-FEIRA para `regra` dentro do nivel `nivel`
    (que ja deve ser o nivel de senioridade REAL dela -- normalmente
    `nivel_senioridade(regra.temas)`). None quando `regra` e totalmente isenta
    (ver `eh_fixo_sem_rodizio_de_nivel`).

    CORRECAO 2026-09-10 (2a do dia, apos simulacao contra dados reais revelar
    um novo problema): a correcao anterior fez todo mundo com SEMANA
    PREFERENCIAL preenchida e SEM `PERFIL DE AUTORIZAÇÃO` (ex.: Fernando
    Mauricio e Gislane Ferreira, ambos PLENO + ultima-semana) entrar na MESMA
    janela geral do nivel que os colaboradores totalmente flexiveis
    (`semana_preferencial==0`). Isso infla o tamanho dessa janela (conta gente
    que so pode ganhar numa fracao das vagas do nivel, ja que continuam
    restritos pelo filtro obrigatorio de semana) sem adicionar capacidade
    real -- confirmado numa simulacao real que isso podia bloquear
    simultaneamente TODOS os candidatos de fato flexiveis, gerando
    SEM ALOCAÇÃO onde antes nao havia nenhum.

    Fix: quem tem `SEMANA PREFERENCIAL != 0` (e nao e isento) passa a
    rodiziar numa SUB-JANELA PROPRIA, isolada da janela geral do nivel,
    compartilhada apenas com quem tem o MESMO nivel E a MESMA semana
    preferencial -- assim Fernando e Gislane alternam entre si (a unica vaga
    que os dois disputam) sem afetar o denominador dos PLENOs flexiveis."""
    if regra.semana_preferencial != 0 and regra.perfil_autorizacao:
        return None
    if regra.semana_preferencial != 0:
        return f"{nivel}#SEM{regra.semana_preferencial}"
    return nivel


def is_tema_compativel(
    candidato_temas: list[str],
    requisito_real: str | None,
    dia_da_semana: str,
) -> bool:
    """Compatibilidade de tema (Fase 0 / hierarquia de senioridade) so se
    aplica a QUARTA-FEIRA. Em qualquer outro dia da semana (ex.: DOMINGO,
    onde o tema e livre -- pedido do Clayton, 2026-09-08), o tema nunca
    bloqueia um candidato.

    Correcao 2026-09-07 (Clayton): a versao anterior comparava
    `regra.funcao` (sempre "MINISTRO") contra o literal "D. MINISTROS" (que
    e o DEPARTAMENTO, um campo diferente) -- essa comparacao nunca era
    verdadeira, entao a excecao nunca disparava de fato e o tema acabava
    sendo exigido tambem aos domingos. O criterio certo e so o dia da
    semana.

    Correcao 2026-09-08 (Clayton, hierarquia de senioridade -- ver
    `montar_requisito_tema_por_slot`): `requisito_real` deixou de ser a
    classificacao bruta do slot (P1/P2/P3) e passou a ser o NIVEL exigido
    (SENIOR/PLENO/JUNIOR, ver `nivel_senioridade`). A comparacao e exata --
    um Senior NAO cobre uma vaga de Pleno/Junior aqui; essa folga so existe
    no RESGATE (ultimo recurso), que ja ignora tema por completo."""
    if "QUARTA" not in dia_da_semana.upper():
        return True
    if not requisito_real:
        return True
    return nivel_senioridade(candidato_temas) == requisito_real.upper()


def _papeis_declarados_no_id_col(
    id_col: str,
    excluse_header: dict[str, int],
    excluse_rows: list[list[str]],
) -> set[str]:
    """Le a coluna `id_col` inteira (B2:B para ID_MINISTROS, por ex.) e
    devolve o conjunto de todos os VALORES (nao os rotulos da coluna
    COLUNAS) encontrados nela, em maiusculas. Um papel X so conflita com o
    departamento de `id_col` se o nome literal de X aparecer NESSE
    conjunto (ver nota no topo do modulo)."""
    idx_id = excluse_header.get(id_col)
    if idx_id is None:
        return set()
    return {
        row[idx_id].strip().upper()
        for row in excluse_rows
        if idx_id < len(row) and row[idx_id].strip()
    }


def esta_bloqueado_por_excluse(
    nome_candidato: str,
    departamento: str,
    funcao: str,
    slot: SlotAgenda,
    excluse_header: dict[str, int],
    excluse_rows: list[list[str]],
) -> bool:
    """True se `nome_candidato` ja aparecer, na data de `slot`, em alguma
    OUTRA coluna Y de AppAnualGlobal tal que o nome literal de Y (nome real
    de coluna, ex.: "PROFESSOR(A) (S1)", ou coluna de ausencia, ex.:
    "ASSIDUIDADE17") aparece como VALOR em alguma linha da coluna
    "ID_<DEPARTAMENTO>" da aba Excluse (ver nota no topo do modulo). O
    conteudo de cada coluna na data do slot e lido combinando
    `slot.papeis` (colunas nomeadas reais) e `slot.assiduidade` (colunas
    ASSIDUIDADE1..30, que registram ausencia) -- ambas tratadas da mesma
    forma, sem distincao."""
    from pastoreio_orquestrador.columns import ColExcluse

    id_col = ColExcluse.id_col(departamento)
    if id_col not in excluse_header:
        return False

    papeis_declarados = _papeis_declarados_no_id_col(id_col, excluse_header, excluse_rows)
    if not papeis_declarados:
        return False

    nome_alvo = nome_candidato.strip().upper()
    funcao_alvo = funcao.strip().upper()
    colunas_da_data = {**slot.assiduidade, **slot.papeis}
    for coluna, pessoa in colunas_da_data.items():
        if coluna.strip().upper() == funcao_alvo:
            continue  # a propria funcao sendo avaliada, nao um conflito
        if pessoa.strip().upper() != nome_alvo:
            continue
        if coluna.strip().upper() in papeis_declarados:
            return True
    return False


def esta_bloqueado_por_aniversario(
    nome_candidato: str,
    slot: SlotAgenda,
    aniversarios: dict[str, date],
) -> bool:
    """True se a data de `slot` cair no aniversario (dia+mes, ano ignorado)
    de `nome_candidato`, segundo a coluna DATA NASCIMENTO da aba BP SERVICE
    (`carregar_aniversarios`). Funciona como um Excluse implicito: mesmo
    filtro obrigatorio, mas para nao alocar o proprio aniversariante no dia
    de servico (pedido do Clayton, 2026-09-07 -- caso real: Patricia Lopes
    nasceu em 25/10 e havia sido alocada em 25/10/2026 antes desta regra)."""
    nascimento = aniversarios.get(nome_candidato.strip().upper())
    if nascimento is None:
        return False
    return (nascimento.day, nascimento.month) == (slot.data.day, slot.data.month)


def esta_bloqueado_por_descanso_cruzado(
    nome_candidato: str,
    data_slot: date,
    compromissos_cruzados: dict[str, list[date]],
    dias_minimos: int = DESCANSO_MINIMO_DIAS,
) -> bool:
    """True se `nome_candidato` ja tiver um compromisso confirmado na MESMA
    funcao mas em OUTRO dia da semana (ex.: MINISTRO no domingo e MINISTRO
    na quarta-feira, ver `carregar_compromissos_cruzados`) a MENOS de
    `dias_minimos` dias de `data_slot`, em qualquer direcao (o compromisso
    externo pode ser antes OU depois -- ambos os dias da semana ja tem
    Rondas gravadas de forma independente, entao ao contrario de
    `respeita_descanso_minimo` -- que so enxerga o que ja foi decidido
    cronologicamente ANTES dentro do mesmo grupo -- aqui o compromisso
    "futuro" ja e um fato conhecido e fixo).

    Generalizacao do "descanso minimo" pedida por Clayton em 2026-09-08,
    apos encontrar casos reais em `CLAUDE_AppAnualGlobal` de uma mesma
    pessoa alocada como MINISTRO num domingo e ja alocada de novo, poucos
    dias depois, na quarta-feira seguinte (ou vice-versa) -- ex.: Ana Lima
    em 11/10/2026 (domingo) e 14/10/2026 (quarta), so 3 dias de intervalo."""
    datas = compromissos_cruzados.get(nome_candidato.strip().upper())
    if not datas:
        return False
    return any(diff_days(d, data_slot) < dias_minimos for d in datas)


# ---------------------------------------------------------------------------
# 4. Requisitos de tema (Fase 0 - forca-tarefa P1 para D. MINISTROS/QUARTA)
# ---------------------------------------------------------------------------


def _requisitos_do_bloco_por_nivel(bloco: list, classificacao: str) -> dict[int, str]:
    """Distribui o NIVEL exigido (SENIOR/PLENO/JUNIOR) entre as semanas de
    um bloco de tema, segundo a hierarquia de senioridade pedida pelo
    Clayton, corrigida em 2026-09-10 (a versao de 2026-09-08 pos P3 com 2
    SENIOR -- pontas iguais ao P2 -- estava errada; o P3 e o tema mais facil
    e so precisa de 1 SENIOR na abertura, nao um segundo na revisao):

      - Tema P1: toda semana do bloco exige SENIOR (so os mais experientes
        dao o tema mais dificil).
      - Tema P2: a 1a e a ultima semana exigem SENIOR (abertura/revisao);
        as semanas do meio exigem PLENO. Ou seja, num bloco tipico de 4-5
        semanas: 2 SENIOR e o restante PLENO.
      - Tema P3: so a 1a semana exige SENIOR (abertura); a 2a semana exige
        PLENO (fixo, nao rotativo); todas as demais exigem JUNIOR. Ou seja:
        1 SENIOR, 1 PLENO e os demais JUNIOR.
      - EXCECAO da 5a semana (2026-09-10, pedido do Clayton, motivada pelo
        SEM ALOCAÇÃO real em "DOUTRINAS BÁSICAS DA BÍBLIA": bloco P3 de 5
        semanas exigia 3 semanas JUNIOR no mesmo mes, mas so ha 2
        colaboradores JUNIOR no grupo -- capacidade insuficiente por
        desenho, nao um bug de rodizio): quando o bloco P3 tem EXATAMENTE 5
        semanas, a 5a (ultima) semana exige PLENO em vez de JUNIOR --
        "sempre dar preferencia a classificacao maior". Resultado num bloco
        de 5 semanas: 1 SENIOR, 2 PLENO, 2 JUNIOR (em vez de 1 SENIOR, 1
        PLENO, 3 JUNIOR). So altera n==5 -- blocos de 4 semanas continuam
        1 SENIOR + 1 PLENO + 2 JUNIOR, sem mudanca.

    Dados reais (2026-09-08): todo bloco do ano tem 4 ou 5 semanas -- nunca
    menos --, mas o fallback abaixo cobre blocos anormalmente curtos (1 ou 2
    semanas) por robustez, mesmo sem ocorrer hoje."""
    n = len(bloco)
    requisito: dict[int, str] = {}

    if classificacao == "P1":
        for slot in bloco:
            requisito[slot.row_index] = NIVEL_SENIOR
        return requisito

    if n == 1:
        # Fallback: bloco de 1 semana so, sem espaco pra abertura/revisao
        # separada do meio -- fica com o nivel mais seguro (SENIOR).
        requisito[bloco[0].row_index] = NIVEL_SENIOR
        return requisito

    if classificacao == "P2":
        # Pontas exigem SENIOR (abertura/revisao); meio exige PLENO.
        requisito[bloco[0].row_index] = NIVEL_SENIOR
        requisito[bloco[-1].row_index] = NIVEL_SENIOR
        for slot in bloco[1:-1]:
            requisito[slot.row_index] = NIVEL_PLENO
        return requisito

    # P3: 1a semana = SENIOR (abertura), 2a semana = PLENO (fixo), demais =
    # JUNIOR. Com n == 2 nao ha "demais": fica so SENIOR + PLENO.
    requisito[bloco[0].row_index] = NIVEL_SENIOR
    requisito[bloco[1].row_index] = NIVEL_PLENO
    for slot in bloco[2:]:
        requisito[slot.row_index] = NIVEL_JUNIOR
    if n == 5:
        # Excecao da 5a semana (ver docstring): promove a ultima semana de
        # JUNIOR para PLENO -- classificacao maior tem preferencia -- para
        # nao exigir 3 semanas JUNIOR no mesmo bloco/mes.
        requisito[bloco[-1].row_index] = NIVEL_PLENO
    return requisito


def montar_requisito_tema_por_slot(
    slots_do_grupo: list[SlotAgenda],
    temas_livros: list[TemaClassificado],
) -> dict[int, str]:
    """Para cada bloco de tema (classificado em Livros por dia da semana),
    devolve {row_index_do_slot: nivel_exigido} -- nivel em
    SENIOR/PLENO/JUNIOR (ver `_requisitos_do_bloco_por_nivel` e
    `nivel_senioridade`), nao mais a classificacao bruta P1/P2/P3.

    Correcao 2026-09-08 (pedido do Clayton -- hierarquia de senioridade):
    antes desta correcao so existia uma regra especial para blocos P3 (>1
    semana), exigindo a classificacao bruta P1/P2/P3 por posicao. Agora TODA
    classificacao (P1/P2/P3) tem sua propria distribuicao de NIVEL exigido
    por semana do bloco, e o resultado e sempre um nivel (nunca mais uma
    classificacao bruta) -- ver `is_tema_compativel`, que passou a comparar
    nivel contra nivel."""
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
        requisito.update(_requisitos_do_bloco_por_nivel(bloco_atual, classificacao))

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
    ultima_data_usada: dict[str, date] = field(default_factory=dict)
    # Rodizio por TEMA (2026-09-10, pedido do Clayton: "criar ronda por
    # tema... assim contemplamos todos"). {nome: quantas vezes ja venceu
    # ESTE MESMO tema (texto exato do slot atual)} -- so populado em
    # QUARTA-FEIRA (ver `_avaliar_e_escolher`); em qualquer outro dia fica
    # vazio e o criterio de desempate abaixo vira neutro (0 para todos).
    contagem_tema_atual: dict[str, int] = field(default_factory=dict)


def chave_ordenacao_candidato(cand: CandidatoRuntime, ctx: ContextoDesempate) -> tuple:
    """Cascata de desempate.

    2026-09-06 (pedido do Clayton, revisao de codigo em andamento): reduzida
    temporariamente as 4 hierarquias de regras cadastradas, na ordem que ele
    confirmou: 1) CEIA ALTERNADA, 2) SEMANA PREFERENCIAL, 3) SEMANA
    ALTERNADA, 4) PRIORIDADE NA ALOCACAO. Os demais criterios (sinc, ATM,
    zumbi, historico, sorteio aleatorio) ficam comentados abaixo -- NAO
    apagados -- para reativar quando a revisao terminar.

    2026-09-08 (pedido do Clayton -- "SEMANA PREFERENCIAL tem prioridade
    total, as proximas linhas sim vao utilizar PRIORIDADE"): antes,
    `semana_preferencial_invalida` era um booleano que so penalizava quem
    pediu uma semana e caiu numa semana diferente -- quem NAO tem
    preferencia (pref=0) e quem TEM preferencia e ela bate com o slot
    ficavam empatados (ambos "validos"), e a decisao caia direto pra
    PRIORIDADE, ignorando que um deles pediu essa semana especificamente e
    o outro e indiferente. Agora e um ranking de 3 niveis: bater com a
    preferencia vence SEMPRE quem nao tem preferencia (mesmo que a
    prioridade cadastrada seja pior) -- so entre candidatos do MESMO nivel
    (ex.: dois que bateram a preferencia, ou dois sem preferencia nenhuma) e
    que PRIORIDADE volta a decidir."""
    r = cand.regra

    # sinc_vence = not (cand.is_sinc_forced or cand.is_sinc_natural)
    # teve_credito_mes_anterior = not (
    #     ctx.uso_mes_anterior.get(r.nome, 0) < r.cota_base
    # )
    # ainda_nao_usou_all_months = not (
    #     r.alocar_todos_os_meses and not ctx.ja_usou_no_mes_atual.get(r.nome, False)
    # )
    # eh_quarta = "QUARTA" in ctx.slot.dia_da_semana.upper()
    # zumbi_vence = not (eh_quarta and r.nome in ctx.zumbis_prioritarios)
    # historico = ctx.historico_total.get(r.nome, 0)
    # desempate_aleatorio = random.random()

    reserva_ceia_penalizada = (
        ctx.funcao_tem_restricao_ceia and not ctx.slot_e_ceia and r.ceia_alternada
    )
    if r.semana_preferencial == 0:
        rank_semana_preferencial = 1  # sem preferencia cadastrada -- neutro
    elif is_valid_preferred_week(r.semana_preferencial, ctx.slot.data):
        rank_semana_preferencial = 0  # pediu esta semana -- prioridade total
    else:
        rank_semana_preferencial = 2  # pediu OUTRA semana -- pior opcao
    semana_alternada_penalizada = r.semana_alternada and not respeita_descanso_minimo(
        ctx.ultima_data_usada.get(r.nome), ctx.slot.data
    )
    # Rodizio por TEMA (2026-09-10, pedido do Clayton): entra ANTES de
    # PRIORIDADE de proposito -- quem ainda nao fez este tema especifico
    # passa a frente de quem ja fez, mesmo com prioridade pior. E um
    # criterio de DESEMPATE (nunca desqualifica ninguem), ao contrario do
    # rodizio geral por nivel (`historico_vencedores_por_nivel`, que
    # bloqueia de verdade) -- escolha deliberada para nao repetir o mesmo
    # tipo de regressao (SEM ALOCAÇÃO novo por janela fragmentada demais)
    # ja visto ao introduzir a sub-janela de SEMANA PREFERENCIAL.
    contagem_tema = ctx.contagem_tema_atual.get(r.nome, 0)
    prioridade = r.prioridade

    return (
        reserva_ceia_penalizada,
        rank_semana_preferencial,
        semana_alternada_penalizada,
        contagem_tema,
        prioridade,
        # zumbi_vence,
        # historico,
        # sinc_vence,
        # ainda_nao_usou_all_months,
        # teve_credito_mes_anterior,
        # desempate_aleatorio,
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
    uso_por_mes: dict[str, dict[str, int]] = field(default_factory=dict)
    ultima_data_usada: dict[str, date] = field(default_factory=dict)
    historico_total: dict[str, int] = field(default_factory=dict)
    zumbis_prioritarios: set[str] = field(default_factory=set)
    nomes_usados_por_linha_vizinha: dict[int, set[str]] = field(default_factory=dict)
    # Historico cronologico (mais antigo primeiro) de quem venceu a CEIA
    # (1o domingo do mes). Usado para o rodizio completo entre TODOS os
    # elegiveis com CEIA ALTERNADA=true, nao so o ultimo vencedor: alguem so
    # pode repetir depois que todos os outros da hierarquia ja tiverem tido
    # sua vez (2026-09-07, pedido do Clayton -- ver CONCEITO_CEIA_ALTERNADA.md).
    # Precisa ser semeado com o historico REAL (rondas anteriores ja
    # gravadas na sheet) quando o processo e reiniciado, ja que cada
    # execucao de Ronda roda num processo separado e nao guarda estado em
    # memoria entre execucoes.
    historico_vencedores_ceia: list[str] = field(default_factory=list)
    # Mesma logica de rodizio completo, mas para a hierarquia de
    # PREENCHIMENTO DE LACUNA (ALOCAR TODOS OS MESES=false E ALOCAÇÃO
    # EXTRA=true): tambem precisa ser semeada com o historico real entre
    # execucoes de Ronda.
    historico_vencedores_lacuna: list[str] = field(default_factory=list)
    # Mesma logica de rodizio completo, agora por NIVEL de senioridade
    # (SENIOR/PLENO/JUNIOR) em QUARTA-FEIRA (2026-09-08, pedido do Clayton:
    # "algo parecido igual fizemos com a ceia... para todos participarem").
    # Cada nivel tem sua propria lista cronologica de vencedores; ninguem
    # repete dentro de um nivel ate todos os outros do MESMO nivel ja terem
    # tido a vez. Tambem precisa ser semeada via replay das Rondas ja
    # fechadas (acontece automaticamente, ja que o replay chama
    # `alocar_grupo` normalmente sobre os slots historicos).
    historico_vencedores_por_nivel: dict[str, list[str]] = field(default_factory=dict)
    # Rodizio por TEMA (2026-09-10, pedido do Clayton: um bloco de tema com
    # varias semanas do MESMO nivel no meio -- ex.: "VIDA DE PROSPERIDADE"
    # com 3 semanas de PLENO seguidas -- nao garantia por si so que pessoas
    # DIFERENTES circulassem POR TEMA ao longo do ano; so o rodizio geral do
    # nivel (que mistura todos os temas) evitava repeticao imediata).
    # {tema (texto normalizado): {nome: quantas vezes ja venceu ESTE tema}}
    # -- usado como CRITERIO DE DESEMPATE (nao filtro obrigatorio, ver
    # `chave_ordenacao_candidato`), entao nunca gera SEM ALOCAÇÃO novo.
    historico_vencedores_por_tema: dict[str, dict[str, int]] = field(default_factory=dict)


def avaliar_candidatos_para_slot(
    candidatos: list[RegraColaborador],
    slot: SlotAgenda,
    estado: EstadoExecucaoGrupo,
    mapa_limites_locais: dict[str, int],
    requisito_tema: str | None,
    ignorar_vizinhanca_e_descanso: bool,
    excluse_header: dict[str, int] | None = None,
    excluse_rows: list[list[str]] | None = None,
    mapa_limites_mensais: dict[str, int] | None = None,
    decisoes_por_row: dict[int, DecisaoAlocacao] | None = None,
    vizinhos_de_data: tuple[int | None, int | None] = (None, None),
    aniversarios: dict[str, date] | None = None,
    compromissos_cruzados: dict[str, list[date]] | None = None,
    ignorar_rodizio_nivel: bool = False,
) -> tuple[list[CandidatoRuntime], list[CandidatoRuntime]]:
    """Devolve (validos, violadores_de_semana_alternada_mas_ainda_elegiveis).

    `ignorar_rodizio_nivel` (2026-09-10, pedido do Clayton): usado por
    `_avaliar_e_escolher` numa passada intermediaria entre a normal e o
    RESGATE, para "quebrar" APENAS o rodizio completo por NIVEL quando ele
    e o unico motivo do SEM ALOCAÇÃO -- ver docstring de `_avaliar_e_
    escolher` para o cenario completo. Todo o resto da cascata (cota,
    Excluse, aniversario, descanso cruzado, tema, semana preferencial,
    vizinhanca, descanso minimo) continua sendo aplicado normalmente."""
    validos: list[CandidatoRuntime] = []
    violadores_sem_alt: list[CandidatoRuntime] = []

    vizinhos = estado.nomes_usados_por_linha_vizinha.get(slot.row_index, set())

    # Rodizio completo da CEIA (2026-09-07, pedido do Clayton: nao basta
    # excluir so o ultimo vencedor -- ninguem da hierarquia de CEIA
    # ALTERNADA pode repetir ate que TODOS os outros elegiveis ja tenham
    # sido escolhidos ao menos uma vez desde a ultima volta). Janela =
    # tamanho da hierarquia - 1 (o proprio "due" fica de fora da janela).
    tamanho_hierarquia_ceia = len({c.nome for c in candidatos if c.ceia_alternada})
    janela_ceia = max(0, tamanho_hierarquia_ceia - 1)
    recentes_ceia_bloqueados = (
        set(estado.historico_vencedores_ceia[-janela_ceia:]) if janela_ceia > 0 else set()
    )

    # Rodizio completo por NIVEL de senioridade (2026-09-08, pedido do
    # Clayton -- mesmo mecanismo da CEIA acima, mas por SENIOR/PLENO/JUNIOR
    # em QUARTA-FEIRA): so entra em jogo quando o slot tem um nivel exigido
    # (`requisito_tema`, ja traduzido em SENIOR/PLENO/JUNIOR por
    # `montar_requisito_tema_por_slot`). So bloqueia no RESGATE=False (passada
    # normal); o resgate ja ignora tema por completo, entao nao ha nivel pra
    # rodiziar ali.
    #
    # Quem e "fixo" (ver `eh_fixo_sem_rodizio_de_nivel`) fica totalmente fora.
    # Os demais rodiziam dentro da SUA PROPRIA chave (`chave_rodizio_nivel`):
    # flexiveis (semana_preferencial==0) competem na janela geral do nivel;
    # quem tem semana preferencial mas nao e isento compete numa sub-janela
    # isolada, so com quem compartilha a MESMA semana dentro do mesmo nivel
    # -- ver a docstring de `chave_rodizio_nivel` para o porque (2a correcao
    # de 2026-09-10, motivada por uma simulacao real que expos um SEM
    # ALOCAÇÃO novo quando as duas populacoes dividiam a mesma janela).
    recentes_nivel_bloqueados: dict[str, set[str]] = {}
    if not ignorar_vizinhanca_e_descanso and requisito_tema and "QUARTA" in slot.dia_da_semana.upper():
        nivel_alvo = requisito_tema.upper()
        chaves_do_nivel = {
            chave_rodizio_nivel(c, nivel_alvo)
            for c in candidatos
            if nivel_senioridade(c.temas) == nivel_alvo
        }
        chaves_do_nivel.discard(None)
        for chave in chaves_do_nivel:
            tamanho_bucket = len({
                c.nome for c in candidatos
                if nivel_senioridade(c.temas) == nivel_alvo and chave_rodizio_nivel(c, nivel_alvo) == chave
            })
            janela_bucket = max(0, tamanho_bucket - 1)
            if janela_bucket > 0:
                recentes_nivel_bloqueados[chave] = set(
                    estado.historico_vencedores_por_nivel.get(chave, [])[-janela_bucket:]
                )

    for regra in candidatos:
        if slot.semana_do_mes == 1 and "DOMINGO" in slot.dia_da_semana.upper():
            # Regra CEIA ALTERNADA (2026-09-06, ver CONCEITO_CEIA_ALTERNADA.md):
            # o 1o domingo do mes (= a data da CEIA) so pode ser ocupado por
            # quem tem CEIA ALTERNADA=True. Restrito a DOMINGO:
            # "semana_do_mes==1" tambem ocorre em outros dias da semana
            # (ex.: 1a quarta-feira do mes), onde a CEIA nao se aplica.
            if not regra.ceia_alternada:
                continue
            if regra.nome in recentes_ceia_bloqueados:
                continue

        if ignorar_vizinhanca_e_descanso:
            # RESGATE (corrigido 2026-09-07 pelo Clayton): unico ultimo
            # recurso para nao deixar a vaga vazia, mas restrito a quem esta
            # explicitamente disponivel para isso -- ALOCAR TODOS OS
            # MESES=false E ALOCAÇÃO EXTRA=true. Dentro desse pool restrito,
            # os UNICOS filtros aplicados sao Excluse e conflito de
            # vizinhanca; cota mensal, descanso minimo, tema e semana
            # preferencial nao bloqueiam no resgate.
            if regra.alocar_todos_os_meses or not regra.alocacao_extra:
                continue
            if excluse_header is not None and excluse_rows is not None:
                if esta_bloqueado_por_excluse(
                    regra.nome, regra.departamento, regra.funcao, slot, excluse_header, excluse_rows
                ):
                    continue
            if aniversarios and esta_bloqueado_por_aniversario(regra.nome, slot, aniversarios):
                continue
            if has_neighbor_conflict(regra.nome, vizinhos):
                continue
            if decisoes_por_row is not None and viola_vizinhanca_de_datas(
                regra.nome, vizinhos_de_data, decisoes_por_row
            ):
                continue

            cand = CandidatoRuntime(regra=regra)
            cand.is_zombie_recuperado = regra.nome in estado.zumbis_prioritarios
            if regra.semana_alternada and not respeita_descanso_minimo(
                estado.ultima_data_usada.get(regra.nome), slot.data
            ):
                # Continua elegivel, mas penalizado no desempate (vai para o
                # fim da ordenacao).
                cand.is_sem_alt_violation = True
                violadores_sem_alt.append(cand)
            validos.append(cand)
            continue

        # Passada normal: cascata completa de filtros obrigatorios.
        if mapa_limites_mensais is not None:
            # A cota e um teto POR MES-CALENDARIO (nao um total poolavel do
            # ciclo inteiro): usar tudo num mes nao pode consumir a cota de
            # outro mes, senao ALOCAR_TODOS_OS_MESES fica impossivel de
            # cumprir.
            limite_mensal = mapa_limites_mensais.get(regra.nome, regra.cota_base)
            uso_mensal = estado.uso_por_mes.get(regra.nome, {}).get(slot.mes_key, 0)
            if uso_mensal >= limite_mensal:
                continue
        else:
            limite = mapa_limites_locais.get(regra.nome, regra.cota_base)
            if estado.uso_no_mes.get(regra.nome, 0) >= limite:
                continue
        if excluse_header is not None and excluse_rows is not None:
            if esta_bloqueado_por_excluse(
                regra.nome, regra.departamento, regra.funcao, slot, excluse_header, excluse_rows
            ):
                continue
        if aniversarios and esta_bloqueado_por_aniversario(regra.nome, slot, aniversarios):
            continue
        if compromissos_cruzados and esta_bloqueado_por_descanso_cruzado(
            regra.nome, slot.data, compromissos_cruzados
        ):
            continue
        if not is_tema_compativel(regra.temas, requisito_tema, regra.dia_da_semana):
            continue
        if requisito_tema and not ignorar_rodizio_nivel:
            chave_regra = chave_rodizio_nivel(regra, requisito_tema.upper())
            if chave_regra is not None and regra.nome in recentes_nivel_bloqueados.get(chave_regra, set()):
                continue
        # SEMANA PREFERENCIAL como filtro obrigatorio (2026-09-08, pedido do
        # Clayton): quem cadastra uma preferencia so pode ser alocado
        # naquela semana -- em qualquer outra semana ele fica INELEGIVEL na
        # passada normal (nao e so penalizado no desempate, como antes).
        # Combinado com o desempate por rank (`chave_ordenacao_candidato`,
        # que ja da prioridade total a quem bate a preferencia sobre quem
        # nao tem nenhuma), isso garante que a pessoa com ALOCAR TODOS OS
        # MESES=true + preferencia cadastrada seja SEMPRE a escolhida na sua
        # semana, a menos que algum outro filtro obrigatorio (excluse,
        # aniversario, tema/nivel, descanso, vizinhanca) a bloqueie -- nesse
        # caso, ela fica de fora e outra pessoa e alocada normalmente. So se
        # aplica na passada normal: o RESGATE (ultimo recurso, mais abaixo)
        # continua ignorando semana preferencial de proposito, como ja
        # documentado ali.
        if regra.semana_preferencial != 0 and not is_valid_preferred_week(
            regra.semana_preferencial, slot.data
        ):
            continue
        if decisoes_por_row is not None and viola_vizinhanca_de_datas(
            regra.nome, vizinhos_de_data, decisoes_por_row
        ):
            continue

        cand = CandidatoRuntime(regra=regra)
        cand.is_zombie_recuperado = regra.nome in estado.zumbis_prioritarios

        tem_conflito_vizinhanca = has_neighbor_conflict(regra.nome, vizinhos)
        respeita_descanso = respeita_descanso_minimo(
            estado.ultima_data_usada.get(regra.nome), slot.data
        )

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

    return validos, violadores_sem_alt


def _avaliar_e_escolher(
    pool: list[RegraColaborador],
    slot: SlotAgenda,
    estado: EstadoExecucaoGrupo,
    mapa_limites_locais: dict[str, int],
    requisito_tema: str | None,
    funcao_tem_restricao_ceia: bool,
    slots_ceia: set[int],
    excluse_header: dict[str, int] | None,
    excluse_rows: list[list[str]] | None,
    mapa_limites_mensais: dict[str, int] | None,
    decisoes_por_row: dict[int, DecisaoAlocacao] | None = None,
    vizinhos_de_data: tuple[int | None, int | None] = (None, None),
    aniversarios: dict[str, date] | None = None,
    compromissos_cruzados: dict[str, list[date]] | None = None,
) -> tuple[CandidatoRuntime | None, list[str], bool, bool]:
    """Roda a cascata de filtros (+ quebra de rodizio de nivel e/ou resgate,
    se necessario) e o desempate sobre `pool`. Devolve (vencedor_ou_None,
    nomes_ordenados, usou_resgate, usou_quebra_rodizio).
    `decisoes_por_row`/`vizinhos_de_data` habilitam o filtro obrigatorio de
    "vizinhanca de datas" (ver `viola_vizinhanca_de_datas`); sem eles, o
    filtro simplesmente nao e aplicado (retrocompativel com chamadas que nao
    rastreiam decisoes por linha).

    QUEBRA DE RODIZIO (2026-09-10, pedido do Clayton, motivada por um SEM
    ALOCAÇÃO real em FUNDAMENTOS DA FÉ: rodizio de nivel bloqueou os 6
    PLENOs ja usados recentemente, e o unico "da vez" fora da janela estava
    de aniversario nesse dia -- ninguem sobrou): "quando nao houver alocacao
    pelo motivo do rodizio, buscar o primeiro da hierarquia, mas somente
    para fechar o gap, respeitando os [outros] bloqueios -- se necessario
    por outro bloqueio, buscar o proximo na hierarquia". Ou seja: se a
    passada normal (COM rodizio de nivel) nao acha ninguem, tenta uma 2a
    passada identica mas com o rodizio de nivel desligado (`ignorar_rodizio_
    nivel=True`) -- todo o resto da cascata continua valendo (cota, Excluse,
    aniversario, descanso cruzado, tema, semana preferencial, vizinhanca,
    descanso minimo). O desempate normal (`ordenar_candidatos`) ja ordena
    por hierarquia/prioridade, entao o vencedor dessa passada e sempre "o
    primeiro da hierarquia" entre quem sobrou -- se o 1o da hierarquia
    tambem estiver bloqueado por outro motivo (aniversario, Excluse etc.),
    ele nem aparece em `validos` e o desempate automaticamente cai pro
    proximo. So se essa 2a passada tambem vier vazia (bloqueio por outro
    motivo em TODO MUNDO, nao so rodizio) e que o RESGATE tradicional (3a
    passada, ultimo recurso) entra em jogo."""
    validos, _ = avaliar_candidatos_para_slot(
        pool, slot, estado, mapa_limites_locais, requisito_tema,
        ignorar_vizinhanca_e_descanso=False,
        excluse_header=excluse_header, excluse_rows=excluse_rows,
        mapa_limites_mensais=mapa_limites_mensais,
        decisoes_por_row=decisoes_por_row, vizinhos_de_data=vizinhos_de_data,
        aniversarios=aniversarios, compromissos_cruzados=compromissos_cruzados,
    )

    usou_resgate = False
    usou_quebra_rodizio = False
    if not validos:
        validos, _ = avaliar_candidatos_para_slot(
            pool, slot, estado, mapa_limites_locais, requisito_tema,
            ignorar_vizinhanca_e_descanso=False,
            excluse_header=excluse_header, excluse_rows=excluse_rows,
            mapa_limites_mensais=mapa_limites_mensais,
            decisoes_por_row=decisoes_por_row, vizinhos_de_data=vizinhos_de_data,
            aniversarios=aniversarios, compromissos_cruzados=compromissos_cruzados,
            ignorar_rodizio_nivel=True,
        )
        usou_quebra_rodizio = bool(validos)

    if not validos:
        usou_resgate = True
        validos, _ = avaliar_candidatos_para_slot(
            pool, slot, estado, mapa_limites_locais, requisito_tema,
            ignorar_vizinhanca_e_descanso=True,
            excluse_header=excluse_header, excluse_rows=excluse_rows,
            mapa_limites_mensais=mapa_limites_mensais,
            decisoes_por_row=decisoes_por_row, vizinhos_de_data=vizinhos_de_data,
            aniversarios=aniversarios, compromissos_cruzados=compromissos_cruzados,
        )

    if not validos:
        return None, [], usou_resgate, usou_quebra_rodizio

    ctx = ContextoDesempate(
        slot=slot,
        uso_mes_anterior=estado.uso_no_mes,
        ja_usou_no_mes_atual={
            nome: uso_meses.get(slot.mes_key, 0) > 0
            for nome, uso_meses in estado.uso_por_mes.items()
        },
        historico_total=estado.historico_total,
        zumbis_prioritarios=estado.zumbis_prioritarios,
        ultima_data_usada=estado.ultima_data_usada,
        funcao_tem_restricao_ceia=funcao_tem_restricao_ceia,
        slot_e_ceia=slot.row_index in slots_ceia,
        contagem_tema_atual=(
            estado.historico_vencedores_por_tema.get(slot.tema.strip().upper(), {})
            if "QUARTA" in slot.dia_da_semana.upper() and slot.tema
            else {}
        ),
    )
    ordenados = ordenar_candidatos(validos, ctx)
    return ordenados[0], [c.nome for c in ordenados], usou_resgate, usou_quebra_rodizio


def _registrar_vencedor(
    estado: EstadoExecucaoGrupo, vencedor: CandidatoRuntime, slot: SlotAgenda
) -> None:
    nome = vencedor.nome
    estado.uso_no_mes[nome] = estado.uso_no_mes.get(nome, 0) + 1
    estado.uso_por_mes.setdefault(nome, {})[slot.mes_key] = (
        estado.uso_por_mes.setdefault(nome, {}).get(slot.mes_key, 0) + 1
    )
    estado.ultima_data_usada[nome] = slot.data
    estado.historico_total[nome] = estado.historico_total.get(nome, 0) + 1
    estado.nomes_usados_por_linha_vizinha.setdefault(slot.row_index, set()).add(nome)
    estado.zumbis_prioritarios.discard(nome)
    if slot.semana_do_mes == 1:
        estado.historico_vencedores_ceia.append(nome)
    if "QUARTA" in slot.dia_da_semana.upper():
        # Rodizio por NIVEL (2026-09-08): registra sob o nivel de
        # senioridade REAL do vencedor (nao o nivel exigido pelo slot) --
        # no caminho normal os dois coincidem (`is_tema_compativel` exige
        # correspondencia exata); no resgate podem divergir, e ainda assim
        # o registro fica correto para o rodizio futuro dentro do proprio
        # nivel do vencedor.
        # Quem e "fixo" (ver `eh_fixo_sem_rodizio_de_nivel`) fica de fora
        # deste historico -- sua vitoria nunca deve ocupar uma posicao em
        # nenhuma janela. Os demais registram sob a MESMA chave usada para
        # bloquea-los (`chave_rodizio_nivel`) -- janela geral do nivel para
        # flexiveis, sub-janela isolada por semana para quem tem semana
        # preferencial mas nao e isento.
        nivel = nivel_senioridade(vencedor.regra.temas)
        chave = chave_rodizio_nivel(vencedor.regra, nivel)
        if chave is not None:
            estado.historico_vencedores_por_nivel.setdefault(chave, []).append(nome)
        # Rodizio por TEMA (2026-09-10): registra sob o texto exato do tema
        # do slot, independente do nivel/chave acima -- ver docstring do
        # campo em `EstadoExecucaoGrupo`.
        if slot.tema:
            tema_norm = slot.tema.strip().upper()
            contagem = estado.historico_vencedores_por_tema.setdefault(tema_norm, {})
            contagem[nome] = contagem.get(nome, 0) + 1


def _desregistrar_vencedor(estado: EstadoExecucaoGrupo, nome: str, slot: SlotAgenda) -> None:
    """Desfaz o efeito de `_registrar_vencedor` para `nome` na data de
    `slot`. Usado exclusivamente por `_tentar_reorganizar_lacuna`, que
    reatribui a OUTRO colaborador da mesma hierarquia uma decisao ja
    tomada pela Fase 4, para liberar `nome` para outra data da rotacao."""
    if nome in estado.uso_no_mes:
        estado.uso_no_mes[nome] = max(0, estado.uso_no_mes[nome] - 1)
    uso_meses = estado.uso_por_mes.get(nome)
    if uso_meses is not None and slot.mes_key in uso_meses:
        uso_meses[slot.mes_key] = max(0, uso_meses[slot.mes_key] - 1)
    if estado.historico_total.get(nome):
        estado.historico_total[nome] -= 1
    estado.nomes_usados_por_linha_vizinha.get(slot.row_index, set()).discard(nome)
    # So remove `ultima_data_usada` se ainda apontar para ESTA data -- se
    # `nome` ja tiver sido registrado de novo em outra data mais recente
    # entre o momento do registro original e agora, nao mexe nisso.
    if estado.ultima_data_usada.get(nome) == slot.data:
        del estado.ultima_data_usada[nome]
    if estado.historico_vencedores_lacuna and estado.historico_vencedores_lacuna[-1] == nome:
        estado.historico_vencedores_lacuna.pop()
    for lista_nivel in estado.historico_vencedores_por_nivel.values():
        if lista_nivel and lista_nivel[-1] == nome:
            lista_nivel.pop()
            break
    if slot.tema:
        contagem = estado.historico_vencedores_por_tema.get(slot.tema.strip().upper())
        if contagem and contagem.get(nome):
            contagem[nome] -= 1
            if contagem[nome] == 0:
                del contagem[nome]


def _tentar_reorganizar_lacuna(
    hierarquia_gap_fill: list[RegraColaborador],
    slot_atual: SlotAgenda,
    estado: EstadoExecucaoGrupo,
    limites_sem_teto: dict[str, int],
    requisito_tema: str | None,
    excluse_header: dict[str, int] | None,
    excluse_rows: list[list[str]] | None,
    decisoes_por_row: dict[int, DecisaoAlocacao],
    vizinhos_de_data_por_row: dict[int, tuple[int | None, int | None]],
    vizinhos_do_slot_atual: tuple[int | None, int | None],
    requisitos_tema_por_slot: dict[int, str],
    aniversarios: dict[str, date] | None = None,
) -> tuple[RegraColaborador | None, SlotAgenda | None, RegraColaborador | None]:
    """Reorganizacao (2026-09-07, correcao verbatim do Clayton apos eu ter
    ampliado erradamente para o GRUPO INTEIRO: "era so preciso reorganizar
    os mesmos colaboradores que tinhas na linha... reordenar os dias
    daquela rotacao"): quando NINGUEM da hierarquia de PREENCHIMENTO DE
    LACUNA consegue fechar `slot_atual` sem violar a vizinhanca de datas,
    procura um colaborador da MESMA hierarquia que so esteja bloqueado por
    causa da vizinhanca (ou seja, elegivel em tudo o mais) e tenta REATRIBUIR
    a data vizinha ja decidida (nesta mesma Fase 4) que causa esse bloqueio
    a OUTRO membro da hierarquia -- nunca a alguem de fora dela. Devolve
    (regra_para_slot_atual, slot_vizinho_a_reatribuir, regra_substituta) ou
    (None, None, None) se nenhum swap resolve (nesse caso e genuinamente
    impossivel, e SEM ALOCACAO e o resultado correto)."""
    for candidato in hierarquia_gap_fill:
        elegivel_sem_vizinhanca, _ = avaliar_candidatos_para_slot(
            [candidato], slot_atual, estado, limites_sem_teto, requisito_tema,
            ignorar_vizinhanca_e_descanso=False,
            excluse_header=excluse_header, excluse_rows=excluse_rows,
            mapa_limites_mensais=None,
            aniversarios=aniversarios,
        )
        if not elegivel_sem_vizinhanca:
            continue  # bloqueado por outro motivo (Excluse, aniversario, descanso...); nao ha o que reorganizar aqui.
        elegivel_com_vizinhanca, _ = avaliar_candidatos_para_slot(
            [candidato], slot_atual, estado, limites_sem_teto, requisito_tema,
            ignorar_vizinhanca_e_descanso=False,
            excluse_header=excluse_header, excluse_rows=excluse_rows,
            mapa_limites_mensais=None,
            decisoes_por_row=decisoes_por_row, vizinhos_de_data=vizinhos_do_slot_atual,
            aniversarios=aniversarios,
        )
        if elegivel_com_vizinhanca:
            continue  # ja teria vencido normalmente; nao deveria chegar aqui.

        for row_vizinho in vizinhos_do_slot_atual:
            if row_vizinho is None:
                continue
            decisao_vizinha = decisoes_por_row.get(row_vizinho)
            if decisao_vizinha is None or decisao_vizinha.vencedor != candidato.nome:
                continue
            # So reorganiza decisoes ja tomadas pela propria Fase 4 -- nao
            # mexe em vitorias da CEIA ou da Fase 3.
            if decisao_vizinha.motivo not in ("PREENCHIMENTO DE LACUNA", "REORGANIZAÇÃO"):
                continue

            slot_vizinho = decisao_vizinha.slot
            vizinhos_do_vizinho = vizinhos_de_data_por_row.get(row_vizinho, (None, None))
            requisito_tema_vizinho = requisitos_tema_por_slot.get(row_vizinho)
            decisoes_sem_o_vizinho = dict(decisoes_por_row)
            del decisoes_sem_o_vizinho[row_vizinho]

            for substituto in hierarquia_gap_fill:
                if substituto.nome == candidato.nome:
                    continue
                elegivel_substituto, _ = avaliar_candidatos_para_slot(
                    [substituto], slot_vizinho, estado, limites_sem_teto, requisito_tema_vizinho,
                    ignorar_vizinhanca_e_descanso=False,
                    excluse_header=excluse_header, excluse_rows=excluse_rows,
                    mapa_limites_mensais=None,
                    decisoes_por_row=decisoes_sem_o_vizinho, vizinhos_de_data=vizinhos_do_vizinho,
                    aniversarios=aniversarios,
                )
                if not elegivel_substituto:
                    continue
                return candidato, slot_vizinho, substituto

    return None, None, None


def _motivo_normal(
    vencedor: CandidatoRuntime, usou_resgate: bool, usou_quebra_rodizio: bool = False
) -> str:
    if vencedor.is_sinc_forced or vencedor.is_sinc_natural:
        return "SINCRONIZAÇÃO"
    if usou_resgate:
        return "RESGATE"
    if usou_quebra_rodizio:
        return "ALOCAÇÃO NORMAL (RODÍZIO QUEBRADO P/ FECHAR LACUNA)"
    return "ALOCAÇÃO NORMAL"


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
    mapa_limites_mensais: dict[str, int] | None = None,
    aniversarios: dict[str, date] | None = None,
    compromissos_cruzados: dict[str, list[date]] | None = None,
) -> list[DecisaoAlocacao]:
    requisitos_tema_por_slot = requisitos_tema_por_slot or {}
    slots_ceia = slots_ceia or set()
    slots_ordenados = sorted(slots_grupo, key=lambda s: s.data)

    eh_grupo_domingo = bool(slots_ordenados) and "DOMINGO" in slots_ordenados[0].dia_da_semana.upper()
    usa_ceia_alternada = any(r.ceia_alternada for r in regras_grupo)
    if eh_grupo_domingo and usa_ceia_alternada:
        # Grupo de DOMINGO com CEIA ALTERNADA: usa o algoritmo em fases (ver
        # CONCEITO_CEIA_ALTERNADA.md, secao "Algoritmo em fases").
        return _alocar_grupo_domingo_ceia_alternada(
            regras_grupo, slots_ordenados, estado, mapa_limites_locais,
            requisitos_tema_por_slot, funcao_tem_restricao_ceia, slots_ceia,
            excluse_header, excluse_rows, mapa_limites_mensais, aniversarios,
            compromissos_cruzados,
        )

    vizinhos_de_data_por_row = montar_vizinhos_de_data_por_row(slots_ordenados)
    decisoes_por_row: dict[int, DecisaoAlocacao] = {}
    decisoes: list[DecisaoAlocacao] = []
    for slot in slots_ordenados:
        requisito_tema = requisitos_tema_por_slot.get(slot.row_index)
        vencedor, ordenados_nomes, usou_resgate, usou_quebra_rodizio = _avaliar_e_escolher(
            regras_grupo, slot, estado, mapa_limites_locais, requisito_tema,
            funcao_tem_restricao_ceia, slots_ceia, excluse_header, excluse_rows,
            mapa_limites_mensais,
            decisoes_por_row=decisoes_por_row,
            vizinhos_de_data=vizinhos_de_data_por_row.get(slot.row_index, (None, None)),
            aniversarios=aniversarios, compromissos_cruzados=compromissos_cruzados,
        )

        if vencedor is None:
            decisao = DecisaoAlocacao(slot=slot, vencedor=None, motivo="SEM ALOCAÇÃO", sem_alocacao=True)
            decisoes_por_row[slot.row_index] = decisao
            decisoes.append(decisao)
            continue

        motivo = _motivo_normal(vencedor, usou_resgate, usou_quebra_rodizio)
        _registrar_vencedor(estado, vencedor, slot)
        decisao = DecisaoAlocacao(
            slot=slot,
            vencedor=vencedor.nome,
            motivo=motivo,
            candidatos_avaliados=ordenados_nomes,
            runner_up=ordenados_nomes[1] if len(ordenados_nomes) > 1 else None,
        )
        decisoes_por_row[slot.row_index] = decisao
        decisoes.append(decisao)

    return decisoes


def _alocar_grupo_domingo_ceia_alternada(
    regras_grupo: list[RegraColaborador],
    slots_ordenados: list[SlotAgenda],
    estado: EstadoExecucaoGrupo,
    mapa_limites_locais: dict[str, int],
    requisitos_tema_por_slot: dict[int, str],
    funcao_tem_restricao_ceia: bool,
    slots_ceia: set[int],
    excluse_header: dict[str, int] | None,
    excluse_rows: list[list[str]] | None,
    mapa_limites_mensais: dict[str, int] | None,
    aniversarios: dict[str, date] | None = None,
    compromissos_cruzados: dict[str, list[date]] | None = None,
) -> list[DecisaoAlocacao]:
    """Algoritmo em fases para grupos de DOMINGO que usam CEIA ALTERNADA
    (definido com o Clayton em 2026-09-06, ver CONCEITO_CEIA_ALTERNADA.md):

      Fase 1 - preenche todos os slots do 1o domingo do mes (CEIA) do ciclo
        completo primeiro, em ordem cronologica, antes de qualquer slot
        normal.
      Fase 2 - remove do pool das datas restantes quem venceu a CEIA nesta
        passada, exceto quem tem ALOCAR TODOS OS MESES=true (esse continua
        disponivel, ainda preso a cota mensal).
      Fase 3 - uma unica passada pelas datas restantes (ordem cronologica):
        escolhe por prioridade dentro do pool remanescente, respeitando a
        cota mensal; quem NAO tem ALOCAR TODOS OS MESES sai do pool assim
        que e escalado (nao repete nesta fase); quem tem, continua
        disponivel para os proximos meses.
      Fase 4 - datas que sobrarem sem fechar na fase 3 sao preenchidas pela
        hierarquia de ALOCAR TODOS OS MESES=false (por prioridade),
        ignorando a cota mensal.
    """
    slots_ceia_1o_domingo = [s for s in slots_ordenados if s.semana_do_mes == 1]
    slots_normais = [s for s in slots_ordenados if s.semana_do_mes != 1]

    decisoes_por_row: dict[int, DecisaoAlocacao] = {}
    # Vizinhos DE DATA (data anterior/seguinte na propria sequencia semanal
    # do grupo), para o filtro obrigatorio de "vizinhanca de datas" -- ver
    # `viola_vizinhanca_de_datas`. Calculado sobre a sequencia CRONOLOGICA
    # completa do grupo (CEIA + normais juntos), nao so o subconjunto de
    # cada fase, ja que datas de fases diferentes tambem podem ser vizinhas
    # (ex.: o ultimo domingo normal de um mes e a CEIA do mes seguinte).
    vizinhos_de_data_por_row = montar_vizinhos_de_data_por_row(slots_ordenados)

    # Fase 1: CEIA em todo o ciclo primeiro.
    vencedores_ceia_sem_atm: set[str] = set()
    for slot in slots_ceia_1o_domingo:
        requisito_tema = requisitos_tema_por_slot.get(slot.row_index)
        vencedor, ordenados_nomes, usou_resgate, _usou_quebra_rodizio = _avaliar_e_escolher(
            regras_grupo, slot, estado, mapa_limites_locais, requisito_tema,
            funcao_tem_restricao_ceia, slots_ceia, excluse_header, excluse_rows,
            mapa_limites_mensais,
            decisoes_por_row=decisoes_por_row,
            vizinhos_de_data=vizinhos_de_data_por_row.get(slot.row_index, (None, None)),
            aniversarios=aniversarios,
            compromissos_cruzados=compromissos_cruzados,
        )
        if vencedor is None:
            decisoes_por_row[slot.row_index] = DecisaoAlocacao(
                slot=slot, vencedor=None, motivo="SEM ALOCAÇÃO", sem_alocacao=True
            )
            continue
        _registrar_vencedor(estado, vencedor, slot)
        if not vencedor.regra.alocar_todos_os_meses:
            vencedores_ceia_sem_atm.add(vencedor.nome)
        motivo = "RESGATE" if usou_resgate else "CEIA ALTERNADA"
        decisoes_por_row[slot.row_index] = DecisaoAlocacao(
            slot=slot,
            vencedor=vencedor.nome,
            motivo=motivo,
            candidatos_avaliados=ordenados_nomes,
            runner_up=ordenados_nomes[1] if len(ordenados_nomes) > 1 else None,
        )

    # Fase 2: remove da fila das datas normais quem venceu a CEIA (exceto
    # ALOCAR TODOS OS MESES=true).
    pool_fase3 = [r for r in regras_grupo if r.nome not in vencedores_ceia_sem_atm]
    nomes_disponiveis_fase3 = {r.nome for r in pool_fase3}

    # Fase 3: unica passada pelas datas normais, respeitando a cota mensal.
    slots_sem_fechar: list[SlotAgenda] = []
    for slot in slots_normais:
        requisito_tema = requisitos_tema_por_slot.get(slot.row_index)
        candidatos_disponiveis = [r for r in pool_fase3 if r.nome in nomes_disponiveis_fase3]
        vencedor, ordenados_nomes, usou_resgate, _usou_quebra_rodizio = _avaliar_e_escolher(
            candidatos_disponiveis, slot, estado, mapa_limites_locais, requisito_tema,
            funcao_tem_restricao_ceia, slots_ceia, excluse_header, excluse_rows,
            mapa_limites_mensais,
            decisoes_por_row=decisoes_por_row,
            vizinhos_de_data=vizinhos_de_data_por_row.get(slot.row_index, (None, None)),
            aniversarios=aniversarios,
            compromissos_cruzados=compromissos_cruzados,
        )
        if vencedor is None:
            slots_sem_fechar.append(slot)
            continue
        _registrar_vencedor(estado, vencedor, slot)
        if not vencedor.regra.alocar_todos_os_meses:
            nomes_disponiveis_fase3.discard(vencedor.nome)
        motivo = _motivo_normal(vencedor, usou_resgate)
        decisoes_por_row[slot.row_index] = DecisaoAlocacao(
            slot=slot,
            vencedor=vencedor.nome,
            motivo=motivo,
            candidatos_avaliados=ordenados_nomes,
            runner_up=ordenados_nomes[1] if len(ordenados_nomes) > 1 else None,
        )

    # Fase 4: preenchimento de lacunas pela hierarquia de quem tem
    # ALOCAR TODOS OS MESES=false E ALOCAÇÃO EXTRA (2026-09-07, pedido do
    # Clayton: so quem esta explicitamente marcado como disponivel para
    # cota extra pode ser puxado alem da cota mensal normal -- nao vale
    # pegar qualquer um so pela prioridade), ignorando a cota mensal e a
    # cota total do periodo.
    hierarquia_gap_fill = [
        r for r in regras_grupo if not r.alocar_todos_os_meses and r.alocacao_extra
    ]
    limites_sem_teto = {r.nome: 10**9 for r in hierarquia_gap_fill}
    tamanho_hierarquia_lacuna = len({r.nome for r in hierarquia_gap_fill})
    for slot in slots_sem_fechar:
        requisito_tema = requisitos_tema_por_slot.get(slot.row_index)
        # Rodizio completo (2026-09-07, pedido do Clayton): assim como a
        # CEIA, ninguem da hierarquia de PREENCHIMENTO DE LACUNA pode
        # repetir ate que todos os outros elegiveis ja tenham sido usados
        # desde a ultima volta -- persistente ATRAVES de Rondas (nao so
        # dentro do mesmo ciclo), por isso usa o historico do `estado` em
        # vez de um set local que reiniciaria a cada execucao/Ronda.
        janela_lacuna = max(0, tamanho_hierarquia_lacuna - 1)
        recentes_lacuna_bloqueados = (
            set(estado.historico_vencedores_lacuna[-janela_lacuna:]) if janela_lacuna > 0 else set()
        )
        pool_ainda_nao_usado = [
            r for r in hierarquia_gap_fill if r.nome not in recentes_lacuna_bloqueados
        ]
        vizinhos_do_slot = vizinhos_de_data_por_row.get(slot.row_index, (None, None))
        vencedor, ordenados_nomes, usou_resgate, _usou_quebra_rodizio = _avaliar_e_escolher(
            pool_ainda_nao_usado, slot, estado, limites_sem_teto, requisito_tema,
            funcao_tem_restricao_ceia, slots_ceia, excluse_header, excluse_rows,
            mapa_limites_mensais=None,
            decisoes_por_row=decisoes_por_row, vizinhos_de_data=vizinhos_do_slot,
            aniversarios=aniversarios,
            compromissos_cruzados=compromissos_cruzados,
        )
        if vencedor is None:
            vencedor, ordenados_nomes, usou_resgate, _usou_quebra_rodizio = _avaliar_e_escolher(
                hierarquia_gap_fill, slot, estado, limites_sem_teto, requisito_tema,
                funcao_tem_restricao_ceia, slots_ceia, excluse_header, excluse_rows,
                mapa_limites_mensais=None,
                decisoes_por_row=decisoes_por_row, vizinhos_de_data=vizinhos_do_slot,
                aniversarios=aniversarios,
                compromissos_cruzados=compromissos_cruzados,
            )
        motivo = "PREENCHIMENTO DE LACUNA"
        if vencedor is None:
            # Reorganizacao (2026-09-07, correcao verbatim do Clayton apos eu
            # ter ampliado erradamente para o GRUPO INTEIRO: "era so preciso
            # reorganizar os mesmos colaboradores que tinhas na linha...
            # reordenar os dias daquela rotacao"): a hierarquia de lacuna
            # pode ser pequena demais para respeitar Excluse + vizinhanca de
            # datas ao mesmo tempo com a escolha gulosa por prioridade (ex.:
            # so 2 pessoas na hierarquia, a escolha gulosa colocou a mesma
            # nas duas datas vizinhas). Antes de desistir, tenta um SWAP
            # entre os MESMOS colaboradores da hierarquia (ver
            # `_tentar_reorganizar_lacuna`) -- nunca introduz alguem de fora
            # dela.
            regra_para_atual, slot_vizinho, regra_substituta = _tentar_reorganizar_lacuna(
                hierarquia_gap_fill, slot, estado, limites_sem_teto, requisito_tema,
                excluse_header, excluse_rows,
                decisoes_por_row, vizinhos_de_data_por_row, vizinhos_do_slot,
                requisitos_tema_por_slot,
                aniversarios=aniversarios,
            )
            if regra_para_atual is not None:
                _desregistrar_vencedor(estado, regra_para_atual.nome, slot_vizinho)
                cand_substituto = CandidatoRuntime(regra=regra_substituta)
                _registrar_vencedor(estado, cand_substituto, slot_vizinho)
                estado.historico_vencedores_lacuna.append(regra_substituta.nome)
                decisoes_por_row[slot_vizinho.row_index] = DecisaoAlocacao(
                    slot=slot_vizinho, vencedor=regra_substituta.nome, motivo="REORGANIZAÇÃO",
                )
                vencedor = CandidatoRuntime(regra=regra_para_atual)
                ordenados_nomes = [regra_para_atual.nome]
                motivo = "REORGANIZAÇÃO"
        if vencedor is None:
            decisoes_por_row[slot.row_index] = DecisaoAlocacao(
                slot=slot, vencedor=None, motivo="SEM ALOCAÇÃO", sem_alocacao=True
            )
            continue
        _registrar_vencedor(estado, vencedor, slot)
        estado.historico_vencedores_lacuna.append(vencedor.nome)
        decisoes_por_row[slot.row_index] = DecisaoAlocacao(
            slot=slot,
            vencedor=vencedor.nome,
            motivo=motivo,
            candidatos_avaliados=ordenados_nomes,
            runner_up=ordenados_nomes[1] if len(ordenados_nomes) > 1 else None,
        )

    return [decisoes_por_row[s.row_index] for s in slots_ordenados]
