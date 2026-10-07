from datetime import datetime, timedelta, timezone

from scripts.Servidor.verificar_saude_colaborador import avaliar_saude


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def test_timer_inativo_e_falha_mesmo_com_snapshot_saudavel():
    ok, detail = avaliar_saude(False, {"state": "HEALTHY", "updated_at": NOW.isoformat()}, NOW, 900)
    assert not ok
    assert "timer inativo" in detail


def test_oneshot_healthy_nao_precisa_estar_ativo():
    ok, _ = avaliar_saude(True, {"state": "HEALTHY", "updated_at": NOW.isoformat()}, NOW, 900)
    assert ok


def test_snapshot_antigo_e_stale():
    old = (NOW - timedelta(seconds=901)).isoformat()
    ok, detail = avaliar_saude(True, {"state": "HEALTHY", "updated_at": old}, NOW, 900)
    assert not ok
    assert "atrasado" in detail


def test_failed_preserva_etapa_no_diagnostico():
    ok, detail = avaliar_saude(
        True,
        {"state": "FAILED", "failed_stage": "7. Sincronizar", "updated_at": NOW.isoformat()},
        NOW,
        900,
    )
    assert not ok
    assert "7. Sincronizar" in detail
