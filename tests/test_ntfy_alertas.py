from pathlib import Path
from unittest.mock import patch

from pastoreio_orquestrador.ntfy_alertas import notificar_transicao


STATE_FILE = Path("runtime/teste_ntfy_estado.json")


class SenderFake:
    def __init__(self, falhar: bool = False):
        self.requests = []
        self.falhar = falhar

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if self.falhar:
            raise OSError("offline")


def notificar(sender: SenderFake, exit_code: int, **kwargs) -> str:
    return notificar_transicao(
        exit_code=exit_code,
        state_file=STATE_FILE,
        timestamp="2026-10-07T10:00:00+01:00",
        url="https://ntfy.sh/topico-teste",
        hostname="servidor-teste",
        sender=sender,
        **kwargs,
    )


@patch("pastoreio_orquestrador.ntfy_alertas._gravar_estado")
@patch("pastoreio_orquestrador.ntfy_alertas._estado_anterior", return_value=None)
def test_primeiro_sucesso_nao_notifica(estado_mock, gravar_mock):
    sender = SenderFake()
    assert notificar(sender, 0) == "estado inicial saudavel"
    assert sender.requests == []
    gravar_mock.assert_called_once_with(STATE_FILE, "success")


@patch("pastoreio_orquestrador.ntfy_alertas._gravar_estado")
@patch("pastoreio_orquestrador.ntfy_alertas._estado_anterior", side_effect=[None, "failure"])
def test_primeira_falha_notifica_uma_vez(estado_mock, gravar_mock):
    sender = SenderFake()
    assert notificar(sender, 1) == "falha notificada"
    assert notificar(sender, 1) == "sem mudanca"
    assert len(sender.requests) == 1
    request, timeout = sender.requests[0]
    assert request.full_url == "https://ntfy.sh/topico-teste"
    assert request.headers["Priority"] == "urgent"
    assert b"Exit code: 1" in request.data
    assert timeout == 10.0
    gravar_mock.assert_called_once_with(STATE_FILE, "failure")


@patch("pastoreio_orquestrador.ntfy_alertas._gravar_estado")
@patch("pastoreio_orquestrador.ntfy_alertas._estado_anterior", return_value="failure")
def test_recuperacao_notifica_depois_de_falha(estado_mock, gravar_mock):
    sender = SenderFake()
    assert notificar(sender, 0) == "recuperacao notificada"
    assert sender.requests[-1][0].headers["Priority"] == "default"
    gravar_mock.assert_called_once_with(STATE_FILE, "success")


@patch("pastoreio_orquestrador.ntfy_alertas._gravar_estado")
@patch("pastoreio_orquestrador.ntfy_alertas._estado_anterior", return_value=None)
def test_token_vai_no_header_authorization(estado_mock, gravar_mock):
    sender = SenderFake()
    notificar(sender, 1, token="segredo")
    assert sender.requests[0][0].headers["Authorization"] == "Bearer segredo"


@patch("pastoreio_orquestrador.ntfy_alertas._gravar_estado")
@patch("pastoreio_orquestrador.ntfy_alertas._estado_anterior", return_value=None)
def test_falha_de_rede_nao_grava_estado_para_permitir_retry(estado_mock, gravar_mock):
    sender = SenderFake(falhar=True)
    resultado = notificar(sender, 1)
    assert resultado.startswith("erro ao enviar")
    gravar_mock.assert_not_called()


def test_sem_url_fica_desativado():
    sender = SenderFake()
    resultado = notificar_transicao(
        exit_code=1,
        state_file=STATE_FILE,
        timestamp="agora",
        url="",
        sender=sender,
    )
    assert resultado == "desativado"
    assert sender.requests == []
