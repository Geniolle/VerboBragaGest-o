from pastoreio_orquestrador.models import RegraColaborador
from pastoreio_orquestrador.protocolo_validacao import avaliar_grupos, parse_grupos_validados


def _regra(nome: str, **overrides) -> RegraColaborador:
    base = dict(
        id_table="1",
        nome=nome,
        departamento="D. MINISTROS",
        funcao="MINISTRO",
        dia_da_semana="QUARTA-FEIRA",
        prioridade=10,
        repeticao_mensal=1,
        alocar_todos_os_meses=False,
        semana_preferencial=0,
        ceia_alternada=False,
        semana_alternada=False,
        alocacao_extra=0,
        atribuir_aos_recados=False,
        perfil_autorizacao=False,
        sinc_colaborador=None,
        sinc_sem_alocacao=False,
        temas=[],
        ativo=True,
        row_index_bp=1,
    )
    base.update(overrides)
    return RegraColaborador(**base)


def test_parse_grupos_validados_ignora_comentarios_e_titulos():
    md = """# titulo
## Validados

D. MINISTROS###MINISTRO###QUARTA-FEIRA
# comentario
D. DIACONATO###AUXILIAR###DOMINGO
"""
    grupos = parse_grupos_validados(md)
    assert grupos == {
        "D. MINISTROS###MINISTRO###QUARTA-FEIRA",
        "D. DIACONATO###AUXILIAR###DOMINGO",
    }


def test_avaliar_grupos_separa_validados_de_pendentes():
    regras = [
        _regra("Ana", departamento="D. MINISTROS", funcao="MINISTRO", dia_da_semana="QUARTA-FEIRA"),
        _regra("Caio", departamento="D. DIACONATO", funcao="AUXILIAR", dia_da_semana="DOMINGO"),
    ]
    validados = {"D. MINISTROS###MINISTRO###QUARTA-FEIRA"}

    relatorio = avaliar_grupos(regras, validados)

    assert relatorio.validados == ["D. MINISTROS###MINISTRO###QUARTA-FEIRA"]
    assert relatorio.pendentes == ["D. DIACONATO###AUXILIAR###DOMINGO"]
