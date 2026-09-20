"""Nomes de coluna reais das abas do Google Sheets (confirmados via leitura
ao vivo da spreadsheet AppPastoreioGestao em 2026-09-05)."""

from __future__ import annotations


class ColBpAlgoritimo:
    ID_TABLE = "ID_TABLE"
    NOME = "NOME"
    DEPARTAMENTO = "DEPARTAMENTO"
    FUNCAO = "FUNÇÃO"
    DIA_DA_SEMANA = "DIA DA SEMANA"
    PRIORIDADE = "PRIORIDADE NA ALOCAÇÃO"
    REPETICAO_MENSAL = "REPETIÇÃO MENSAL"
    ALOCAR_TODOS_OS_MESES = "ALOCAR TODOS OS MESES"
    SEMANA_PREFERENCIAL = "SEMANA PREFERENCIAL"
    CEIA_ALTERNADA = "CEIA ALTERNADA"
    SEMANA_ALTERNADA = "SEMANA ALTERNADA"
    ALOCACAO_EXTRA = "ALOCAÇÃO EXTRA"
    ATRIBUIR_AOS_RECADOS = "ATRIBUIR AOS RECADOS"
    PERFIL_AUTORIZACAO = "PERFIL DE AUTORIZAÇÃO"
    SINC_COLABORADOR = "SINC_COLABORADOR"
    SINC_SEM_ALOCACAO = "SINC_SEM_ALOCAÇÃO"
    TEMA = "TEMA"
    TIPO_ALOCACAO = "TIPO ALOCAÇÃO"
    INTERVALO_MESES = "INTERVALO MESES"
    DATA_INICIO_RECORRENCIA = "DATA INÍCIO RECORRÊNCIA"
    ATIVO = "ATIVO"
    ELIMINAR_DA_ESCALA = "ELIMINAR DA ESCALA"
    COLABORADOR_SUBSTITUTO = "COLABORADOR SUBSTITUTO"
    STATUS_ELIMINACAO = "STATUS ELIMINAÇÃO"
    EMAIL_LIDER = "EMAIL LIDER"
    USEREMAIL = "USEREMAIL"
    TIMESTAMP = "TIMESTAMP"
    TYPE = "TYPE"


class ColBpService:
    ID_USER = "ID_USER"
    NOME = "NOME"
    EMAIL = "EMAIL"
    DEPARTAMENTOS = "DEPARTAMENTOS"
    INATIVO = "INATIVO"
    TYPE = "TYPE"
    DEPARTAMENTO_PREFIXO = "D. "
    # Excluida da deteccao de colunas de departamento -- mesma excecao do
    # script original (ProcessarBPService_BPAlgoritimo_v12).
    DEPARTAMENTO_EXCLUIDO = "D. CENTRO DE CURA"


class ColIdDepartamentos:
    DEPARTAMENTOS = "DEPARTAMENTOS"
    EMAIL = "EMAIL"


class ColAppAnualGlobal:
    PERIODO = "PERÍODO"
    MES = "MÊS"
    DIA_DA_SEMANA = "DIA DA SEMANA"
    DATA = "DATA"
    TEMA = "TEMA"
    NUM_COLUNAS_ASSIDUIDADE = 30

    @classmethod
    def colunas_assiduidade(cls) -> list[str]:
        """As 30 colunas genericas ASSIDUIDADE1..30 de AppAnualGlobal, cujo
        significado (a qual departamento/funcao pertencem) e definido pela
        aba Excluse (ver ColExcluse.id_col)."""
        return [f"ASSIDUIDADE{i}" for i in range(1, cls.NUM_COLUNAS_ASSIDUIDADE + 1)]


class ColExcluse:
    COLUNAS = "COLUNAS"

    @staticmethod
    def id_col(departamento: str) -> str:
        """Ex.: 'D. MINISTROS' -> 'ID_MINISTROS' (prefixo 'D. ' removido)."""
        nome = departamento.strip()
        if nome.upper().startswith("D. "):
            nome = nome[3:]
        return f"ID_{nome.strip().upper()}"


class ColConfAlgoritimo:
    PROCESSO = "PROCESSO"
    VALOR = "VALOR"


class ColLivros:
    DIA_DA_SEMANA = "DIA DA SEMANA"
    TEMA = "TEMA"
    LINK = "LINK"
    CLASSIFICACAO = "CLASSIFICAÇÃO"


class ColBpLog:
    DEPARTAMENTO = "DEPARTAMENTO"
    PROCESSO = "PROCESSO"
    NOME = "NOME"
    MES_NAO_ALOCADOS = "MÊS DE NÃO ALOCADOS"
    DISPONIBILIDADE = "DISPONIBILIDADE"
    TIMESTAMP_UTILIZACAO = "TIMESTEMP DA UTILIZAÇÃO"


class ColLogAlgoritimo:
    LOG_ID = "Log ID"
    DATA_EXECUCAO = "Data de Execução"
    ALOCACOES_JSON = "Alocações (JSON)"
    STATUS = "Status"
    NOTAS = "Notas do Usuário"
    DEPARTAMENTO = "Departamento"
    FUNCAO = "Função"
