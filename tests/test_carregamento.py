# -*- coding: utf-8 -*-
"""Regressao para a corrupcao de cabecalho encontrada em 2026-09-11 (ver
CHANGELOG/comentario em carregamento.py): se uma coluna obrigatoria de
BP ALGORITIMO desaparecer do cabecalho (renomeada/deslocada sem atualizar o
texto), `carregar_regras_colaboradores` deve falhar alto, nunca voltar a
carregar tudo em silencio com prioridade=999 (ou outro default) para todo
mundo."""
from datetime import date

import pytest

from pastoreio_orquestrador.carregamento import (
    build_header_index, carregar_emails, carregar_regras_colaboradores,
    contar_ocorrencias_mensais_por_colaborador,
    validar_cabecalho_bp_algoritimo,
)

CABECALHO_OK = [
    "ID_TABLE", "NOME", "DEPARTAMENTO", "FUNÇÃO", "DIA DA SEMANA",
    "PRIORIDADE NA ALOCAÇÃO", "REPETIÇÃO MENSAL", "ALOCAR TODOS OS MESES",
    "SEMANA PREFERENCIAL", "CEIA ALTERNADA", "SEMANA ALTERNADA",
    "ALOCAÇÃO EXTRA", "ATRIBUIR AOS RECADOS", "SINC_COLABORADOR",
    "SINC_SEM_ALOCAÇÃO", "TEMA", "TIPO ALOCAÇÃO", "INTERVALO MESES",
    "DATA INÍCIO RECORRÊNCIA", "ATIVO",
]

LINHA_ANA = [
    "1", "Ana", "D. MINISTROS", "MINISTRO", "QUARTA-FEIRA",
    "1", "1", "FALSE", "0", "FALSE", "FALSE", "0", "", "", "", "",
    "", "", "", "TRUE",
]


def test_cabecalho_valido_carrega_normalmente():
    valores = [CABECALHO_OK, LINHA_ANA]
    regras = carregar_regras_colaboradores(valores)
    assert len(regras) == 1
    assert regras[0].prioridade == 1
    assert regras[0].tipo_alocacao is None


def test_cabecalho_sem_prioridade_levanta_erro_alto():
    """Caso real (2026-09-11): a coluna G de CLAUDE_BP ALGORITIMO ficou com o
    cabecalho em branco em vez de 'PRIORIDADE NA ALOCAÇÃO'. Antes desta
    checagem, isso resultava em prioridade=999 para todo mundo, sem
    nenhum aviso."""
    cabecalho_quebrado = list(CABECALHO_OK)
    idx_prioridade = cabecalho_quebrado.index("PRIORIDADE NA ALOCAÇÃO")
    cabecalho_quebrado[idx_prioridade] = ""

    with pytest.raises(ValueError, match="PRIORIDADE NA ALOCAÇÃO"):
        carregar_regras_colaboradores([cabecalho_quebrado, LINHA_ANA])


def test_validar_cabecalho_lista_todas_as_colunas_faltando():
    idx = build_header_index(["ID_TABLE", "NOME"])
    faltando = validar_cabecalho_bp_algoritimo(idx)
    assert "PRIORIDADE NA ALOCAÇÃO" in faltando
    assert "ATIVO" in faltando
    assert "NOME" not in faltando


# ---------------------------------------------------------------------------
# carregar_emails (pedido do Clayton, 2026-09-11: escrever automaticamente
# o email do colaborador alocado na coluna "EMAIL <FUNÇÃO>")
# ---------------------------------------------------------------------------

CABECALHO_BP_SERVICE = ["ID_USER", "NOME", "TELEFONE", "WHATSAPP", "NUMBER_WHATSAPP", "EMAIL"]


def test_carregar_emails_casa_por_nome_em_maiusculas():
    valores = [
        CABECALHO_BP_SERVICE,
        ["1", "André Luiz", "", "", "", "andre@example.com"],
    ]
    emails = carregar_emails(valores)
    assert emails["ANDRÉ LUIZ"] == "andre@example.com"


def test_carregar_emails_ignora_linha_sem_email():
    """Caso real: 'Culto de Oração' e um placeholder (nao uma pessoa) e nao
    tem linha/email cadastrado em BP SERVICE -- nao deve gerar entrada nem
    erro, so fica de fora do dicionario (o chamador escreve celula vazia)."""
    valores = [
        CABECALHO_BP_SERVICE,
        ["1", "Culto de Oração", "", "", "", ""],
    ]
    emails = carregar_emails(valores)
    assert "CULTO DE ORAÇÃO" not in emails


def test_contar_ocorrencias_mensais_por_colaborador_lendo_ceia_e_ministro():
    valores = [
        ["DATA", "DIA DA SEMANA", "CEIA", "MINISTRO"],
        ["06/12/2026", "DOMINGO", "Pessoa A", ""],
        ["13/12/2026", "DOMINGO", "", "Pessoa A"],
        ["20/12/2026", "DOMINGO", "", "Pessoa B"],
        ["23/12/2026", "QUARTA-FEIRA", "Pessoa A", "Pessoa A"],
    ]

    contagem = contar_ocorrencias_mensais_por_colaborador(
        valores,
        "DOMINGO",
        ("CEIA", "MINISTRO"),
        nomes_validos={"PESSOA A": "Pessoa A", "PESSOA B": "Pessoa B"},
    )

    assert contagem == {
        "Pessoa A": {"2026-12": 2},
        "Pessoa B": {"2026-12": 1},
    }


def test_contar_ocorrencias_mensais_respeita_data_corte_rotacional():
    valores = [
        ["DATA", "DIA DA SEMANA", "MINISTRO"],
        ["27/09/2026", "DOMINGO", "Pessoa A"],
        ["04/10/2026", "DOMINGO", "Pessoa A"],
    ]

    contagem = contar_ocorrencias_mensais_por_colaborador(
        valores,
        "DOMINGO",
        ("MINISTRO",),
        nomes_validos={"PESSOA A": "Pessoa A"},
        data_corte_historico=date(2026, 10, 1),
    )

    assert contagem == {"Pessoa A": {"2026-10": 1}}


def test_carregar_regra_fixo_recorrente():
    linha = list(LINHA_ANA)
    linha[CABECALHO_OK.index("NOME")] = "Centro de Cura"
    linha[CABECALHO_OK.index("SEMANA PREFERENCIAL")] = "3"
    linha[CABECALHO_OK.index("TIPO ALOCAÇÃO")] = "fixo_recorrente"
    linha[CABECALHO_OK.index("INTERVALO MESES")] = "2"
    linha[CABECALHO_OK.index("DATA INÍCIO RECORRÊNCIA")] = "16/09/2026"

    regra = carregar_regras_colaboradores([CABECALHO_OK, linha])[0]

    assert regra.tipo_alocacao == "FIXO_RECORRENTE"
    assert regra.intervalo_meses == 2
    assert regra.data_inicio_recorrencia == date(2026, 9, 16)
    assert regra.semana_preferencial == 3


@pytest.mark.parametrize(
    ("campo", "valor", "erro"),
    [
        ("INTERVALO MESES", "", "INTERVALO MESES"),
        ("INTERVALO MESES", "0", "positivo"),
        ("INTERVALO MESES", "-1", "positivo"),
        ("DATA INÍCIO RECORRÊNCIA", "", "DATA INÍCIO RECORRÊNCIA"),
        ("DATA INÍCIO RECORRÊNCIA", "2026-09-16", "invalida"),
        ("SEMANA PREFERENCIAL", "0", "SEMANA PREFERENCIAL"),
        ("SEMANA PREFERENCIAL", "6", "SEMANA PREFERENCIAL"),
    ],
)
def test_carregar_regra_fixo_recorrente_invalida_falha_alto(campo, valor, erro):
    linha = list(LINHA_ANA)
    linha[CABECALHO_OK.index("NOME")] = "Centro de Cura"
    linha[CABECALHO_OK.index("SEMANA PREFERENCIAL")] = "3"
    linha[CABECALHO_OK.index("TIPO ALOCAÇÃO")] = "FIXO_RECORRENTE"
    linha[CABECALHO_OK.index("INTERVALO MESES")] = "2"
    linha[CABECALHO_OK.index("DATA INÍCIO RECORRÊNCIA")] = "16/09/2026"
    linha[CABECALHO_OK.index(campo)] = valor

    with pytest.raises(ValueError, match=erro):
        carregar_regras_colaboradores([CABECALHO_OK, linha])
