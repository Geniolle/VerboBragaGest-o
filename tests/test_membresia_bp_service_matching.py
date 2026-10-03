"""Testes para a sincronização Membresia -> BP SERVICE com nova regra de matching.

Nova regra (2026-10-03):
Match automático requer NOME + EMAIL + TELEFONE coincidentes.
Email ou telefone isolados nunca geram match automático.
"""

import pytest
from scripts.Colaborador.marcar_membresia_bp_service_existentes import (
    PessoaBp,
    IdentidadeMembresia,
    Match,
    Ambiguidade,
    normalize_text,
    normalize_email,
    normalize_phone,
    normalize_date,
    encontrar_match,
)


def test_chave_identidade_tripla_completa():
    """Chave tripla com todos os campos preenchidos."""
    pessoa = PessoaBp(
        linha=2,
        id_user="1",
        nome="JOAO SILVA",
        email="joao@email.pt",
        telefone="351912345678",
        number_whatsapp="",
        nascimento="1980-01-15",
    )
    assert pessoa.chave_identidade_tripla == ("JOAO SILVA", "joao@email.pt", "351912345678")


def test_chave_identidade_tripla_nome_vazio():
    """Chave tripla retorna None quando nome está vazio."""
    pessoa = PessoaBp(
        linha=2,
        id_user="1",
        nome="",  # vazio
        email="joao@email.pt",
        telefone="351912345678",
        number_whatsapp="",
        nascimento="1980-01-15",
    )
    assert pessoa.chave_identidade_tripla is None


def test_chave_identidade_tripla_email_vazio():
    """Chave tripla retorna None quando email está vazio."""
    pessoa = PessoaBp(
        linha=2,
        id_user="1",
        nome="JOAO SILVA",
        email="",  # vazio
        telefone="351912345678",
        number_whatsapp="",
        nascimento="1980-01-15",
    )
    assert pessoa.chave_identidade_tripla is None


def test_chave_identidade_tripla_telefone_vazio():
    """Chave tripla retorna None quando telefone está vazio."""
    pessoa = PessoaBp(
        linha=2,
        id_user="1",
        nome="JOAO SILVA",
        email="joao@email.pt",
        telefone="",  # vazio
        number_whatsapp="",
        nascimento="1980-01-15",
    )
    assert pessoa.chave_identidade_tripla is None


def test_match_nome_email_telefone_iguais():
    """Caso A: Nome + Email + Telefone iguais → MATCH (novo critério)."""
    por_tripla = {
        ("JOAO SILVA", "joao@email.pt", "351912345678"): PessoaBp(
            linha=2,
            id_user="17",
            nome="JOAO SILVA",
            email="joao@email.pt",
            telefone="351912345678",
            number_whatsapp="",
            nascimento="1980-01-15",
        )
    }
    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="João Silva",
        nome="JOAO SILVA",
        email="joao@email.pt",
        telefone="351912345678",
        number_whatsapp="",
        nascimento="1980-01-15",
    )

    resultado = encontrar_match(identidade, por_tripla, {}, {}, {})

    assert isinstance(resultado, Match)
    assert resultado.id_user == "17"
    assert resultado.metodo == "NOME+EMAIL+TELEFONE"


def test_ambiguidade_email_telefone_iguais_nome_diferente():
    """Caso C: Email + Telefone iguais, mas Nome diferente → AMBIGUIDADE."""
    # Este é o case "Teste Servidor" que deve ser detectado como ambíguo
    por_tripla = {
        ("CLAYTON LOPES", "consultorsapclaytonlopes@gmail.com", "351913873024"): PessoaBp(
            linha=2,
            id_user="17",
            nome="CLAYTON LOPES",
            email="consultorsapclaytonlopes@gmail.com",
            telefone="351913873024",
            number_whatsapp="",
            nascimento="",
        )
    }
    por_email = {
        "consultorsapclaytonlopes@gmail.com": [
            PessoaBp(
                linha=2,
                id_user="17",
                nome="CLAYTON LOPES",
                email="consultorsapclaytonlopes@gmail.com",
                telefone="351913873024",
                number_whatsapp="",
                nascimento="",
            )
        ]
    }
    por_telefone = {
        "351913873024": [
            PessoaBp(
                linha=2,
                id_user="17",
                nome="CLAYTON LOPES",
                email="consultorsapclaytonlopes@gmail.com",
                telefone="351913873024",
                number_whatsapp="",
                nascimento="",
            )
        ]
    }

    identidade = IdentidadeMembresia(
        linha=37,
        nome_original="Teste Servidor",
        nome="TESTE SERVIDOR",  # DIFERENTE
        email="consultorsapclaytonlopes@gmail.com",  # IGUAL
        telefone="351913873024",  # IGUAL
        number_whatsapp="",
        nascimento="1974-08-01",
    )

    resultado = encontrar_match(identidade, por_tripla, por_email, por_telefone, {})

    assert isinstance(resultado, Ambiguidade)
    assert "17" in resultado.ids_possiveis
    assert "nome é diferente" in resultado.motivo.lower()


def test_ambiguidade_email_nome_iguais_telefone_diferente():
    """Caso B: Email + Nome iguais, mas Telefone diferente → AMBIGUIDADE."""
    por_tripla = {}
    por_email = {
        "joao@email.pt": [
            PessoaBp(
                linha=2,
                id_user="10",
                nome="JOAO SILVA",
                email="joao@email.pt",
                telefone="351912345678",
                number_whatsapp="",
                nascimento="1980-01-15",
            )
        ]
    }

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="João Silva",
        nome="JOAO SILVA",  # IGUAL
        email="joao@email.pt",  # IGUAL
        telefone="351987654321",  # DIFERENTE
        number_whatsapp="",
        nascimento="1980-01-15",
    )

    resultado = encontrar_match(identidade, por_tripla, por_email, {}, {})

    assert isinstance(resultado, Ambiguidade)
    assert "10" in resultado.ids_possiveis
    assert "telefone é diferente" in resultado.motivo.lower()


def test_ambiguidade_nome_telefone_iguais_email_diferente():
    """Caso A.2: Nome + Telefone iguais, mas Email diferente → AMBIGUIDADE."""
    por_tripla = {}
    por_telefone = {
        "351912345678": [
            PessoaBp(
                linha=2,
                id_user="10",
                nome="JOAO SILVA",
                email="joao.silva@email.pt",
                telefone="351912345678",
                number_whatsapp="",
                nascimento="1980-01-15",
            )
        ]
    }

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="João Silva",
        nome="JOAO SILVA",  # IGUAL
        email="joao.novo@email.pt",  # DIFERENTE
        telefone="351912345678",  # IGUAL
        number_whatsapp="",
        nascimento="1980-01-15",
    )

    resultado = encontrar_match(identidade, por_tripla, {}, por_telefone, {})

    assert isinstance(resultado, Ambiguidade)
    assert "10" in resultado.ids_possiveis
    assert "email é diferente" in resultado.motivo.lower()


def test_sem_match_email_isolado():
    """Email isolado (sem nome+telefone iguais) → NÃO MATCH automático."""
    por_tripla = {}
    por_email = {
        "joao@email.pt": [
            PessoaBp(
                linha=2,
                id_user="10",
                nome="JOAO SILVA",
                email="joao@email.pt",
                telefone="351912345678",
                number_whatsapp="",
                nascimento="1980-01-15",
            )
        ]
    }

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="Pedro Santos",
        nome="PEDRO SANTOS",  # DIFERENTE
        email="joao@email.pt",  # IGUAL (isolado)
        telefone="351987654321",  # DIFERENTE
        number_whatsapp="",
        nascimento="1970-05-10",
    )

    resultado = encontrar_match(identidade, por_tripla, por_email, {}, {})

    # Não deve ser match automático nem ambiguidade neste contexto
    assert resultado is None


def test_sem_match_telefone_isolado():
    """Telefone isolado (sem nome+email iguais) → NÃO MATCH automático."""
    por_tripla = {}
    por_telefone = {
        "351912345678": [
            PessoaBp(
                linha=2,
                id_user="10",
                nome="JOAO SILVA",
                email="joao@email.pt",
                telefone="351912345678",
                number_whatsapp="",
                nascimento="1980-01-15",
            )
        ]
    }

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="Pedro Santos",
        nome="PEDRO SANTOS",  # DIFERENTE
        email="pedro@email.pt",  # DIFERENTE
        telefone="351912345678",  # IGUAL (isolado)
        number_whatsapp="",
        nascimento="1970-05-10",
    )

    resultado = encontrar_match(identidade, por_tripla, {}, por_telefone, {})

    # Não deve ser match automático nem ambiguidade neste contexto
    assert resultado is None


def test_sem_match_nome_isolado():
    """Nome isolado (sem email+telefone iguais) → NÃO MATCH automático."""
    por_tripla = {}
    por_nome_nascimento = {
        "JOAO SILVA|1980-01-15": [
            PessoaBp(
                linha=2,
                id_user="10",
                nome="JOAO SILVA",
                email="joao@email.pt",
                telefone="351912345678",
                number_whatsapp="",
                nascimento="1980-01-15",
            )
        ]
    }

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="João Silva",
        nome="JOAO SILVA",  # IGUAL (isolado)
        email="joao.novo@email.pt",  # DIFERENTE
        telefone="351987654321",  # DIFERENTE
        number_whatsapp="",
        nascimento="1980-01-15",
    )

    resultado = encontrar_match(identidade, por_tripla, {}, {}, por_nome_nascimento)

    # Não deve ser match automático
    # (Nome+Data de Nascimento já não é critério de match automático)
    assert resultado is None


def test_novo_utilizador_quando_nenhum_candidato():
    """Nenhum candidato plausível → Novo utilizador (retorna None)."""
    por_tripla = {}

    identidade = IdentidadeMembresia(
        linha=50,
        nome_original="Maria Santos",
        nome="MARIA SANTOS",
        email="maria@email.pt",
        telefone="351955555555",
        number_whatsapp="",
        nascimento="1990-03-20",
    )

    resultado = encontrar_match(identidade, por_tripla, {}, {}, {})

    assert resultado is None


def test_normalizacao_nome_com_acentos():
    """Nome com acentos normaliza corretamente."""
    assert normalize_text("João") == "JOAO"
    assert normalize_text("Lopes") == "LOPES"
    assert normalize_text("Café") == "CAFE"
    assert normalize_text("   José   ") == "JOSE"


def test_normalizacao_email():
    """Email normaliza para lowercase."""
    assert normalize_email("JOAO@EMAIL.PT") == "joao@email.pt"
    assert normalize_email("  joao@email.pt  ") == "joao@email.pt"


def test_normalizacao_telefone():
    """Telefone remove todos os caracteres não-numéricos."""
    assert normalize_phone("+351 912 345 678") == "351912345678"
    assert normalize_phone("351912345678") == "351912345678"
    assert normalize_phone("+351-912-345-678") == "351912345678"
    assert normalize_phone("(+351) 912.345.678") == "351912345678"


def test_dados_insuficientes_sem_nome():
    """Identidade sem nome não gera match automático."""
    por_tripla = {}

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="",
        nome="",  # vazio
        email="joao@email.pt",
        telefone="351912345678",
        number_whatsapp="",
        nascimento="1980-01-15",
    )

    assert identidade.chave_identidade_tripla is None
    resultado = encontrar_match(identidade, por_tripla, {}, {}, {})
    assert resultado is None


def test_dados_insuficientes_sem_email():
    """Identidade sem email não gera match automático."""
    por_tripla = {}

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="João Silva",
        nome="JOAO SILVA",
        email="",  # vazio
        telefone="351912345678",
        number_whatsapp="",
        nascimento="1980-01-15",
    )

    assert identidade.chave_identidade_tripla is None
    resultado = encontrar_match(identidade, por_tripla, {}, {}, {})
    assert resultado is None


def test_dados_insuficientes_sem_telefone():
    """Identidade sem telefone não gera match automático."""
    por_tripla = {}

    identidade = IdentidadeMembresia(
        linha=3,
        nome_original="João Silva",
        nome="JOAO SILVA",
        email="joao@email.pt",
        telefone="",  # vazio
        number_whatsapp="",
        nascimento="1980-01-15",
    )

    assert identidade.chave_identidade_tripla is None
    resultado = encontrar_match(identidade, por_tripla, {}, {}, {})
    assert resultado is None


def test_regressao_teste_servidor():
    """REGRESSÃO: Teste Servidor + Clayton Lopes deve ser AMBIGUIDADE, nunca MATCH."""
    # Dados do caso real
    por_tripla = {
        ("CLAYTON LOPES", "consultorsapclaytonlopes@gmail.com", "351913873024"): PessoaBp(
            linha=2,
            id_user="17",
            nome="CLAYTON LOPES",
            email="consultorsapclaytonlopes@gmail.com",
            telefone="351913873024",
            number_whatsapp="",
            nascimento="",
        )
    }
    por_email = {
        "consultorsapclaytonlopes@gmail.com": [
            PessoaBp(
                linha=2,
                id_user="17",
                nome="CLAYTON LOPES",
                email="consultorsapclaytonlopes@gmail.com",
                telefone="351913873024",
                number_whatsapp="",
                nascimento="",
            )
        ]
    }
    por_telefone = {
        "351913873024": [
            PessoaBp(
                linha=2,
                id_user="17",
                nome="CLAYTON LOPES",
                email="consultorsapclaytonlopes@gmail.com",
                telefone="351913873024",
                number_whatsapp="",
                nascimento="",
            )
        ]
    }

    identidade = IdentidadeMembresia(
        linha=37,
        nome_original="Teste Servidor",
        nome="TESTE SERVIDOR",
        email="consultorsapclaytonlopes@gmail.com",
        telefone="351913873024",
        number_whatsapp="",
        nascimento="1974-08-01",
    )

    resultado = encontrar_match(identidade, por_tripla, por_email, por_telefone, {})

    # NUNCA deve ser Match automático
    assert not isinstance(resultado, Match), "Teste Servidor NÃO deve ser Match automático com Clayton Lopes"

    # DEVE ser Ambiguidade
    assert isinstance(resultado, Ambiguidade), "Teste Servidor deve ser classificado como AMBIGUIDADE"
    assert "17" in resultado.ids_possiveis
    assert "nome" in resultado.motivo.lower()
