from unittest.mock import patch

from scripts.Colaborador.cockpit_colaborador import Etapa, run_etapa


@patch("scripts.Colaborador.cockpit_colaborador.subprocess.run")
def test_etapa_sem_suporte_nao_recebe_use_cache(run_mock):
    etapa = Etapa("Atualizar BP AUTORITY", "atualizar_bp_autority.py", aplica=True)

    run_etapa(etapa, aplicar=True, no_cache=False)

    cmd = run_mock.call_args.args[0]
    assert "--aplicar" in cmd
    assert "--use-cache" not in cmd


@patch("scripts.Colaborador.cockpit_colaborador.subprocess.run")
def test_limpeza_destrutiva_nao_recebe_use_cache(run_mock):
    etapa = Etapa("Limpar BP ALGORITIMO", "limpar_bp_algoritimo.py", aplica=True)

    run_etapa(etapa, aplicar=True, no_cache=False)

    cmd = run_mock.call_args.args[0]
    assert "--aplicar" in cmd
    assert "--use-cache" not in cmd


@patch("scripts.Colaborador.cockpit_colaborador.subprocess.run")
def test_no_cache_remove_opcao_mesmo_quando_etapa_suporta(run_mock):
    etapa = Etapa("Limpar BP ALGORITIMO", "limpar_bp_algoritimo.py", usa_cache=True)

    run_etapa(etapa, aplicar=False, no_cache=True)

    cmd = run_mock.call_args.args[0]
    assert "--use-cache" not in cmd
