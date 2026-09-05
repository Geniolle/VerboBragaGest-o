"""Proposta D: alerta automatico quando o motor deixa vagas "SEM ALOCAÇÃO".

Este modulo so MONTA o conteudo do alerta (destinatario via EMAIL LIDER,
assunto, corpo com as datas sem alocacao). O envio de e-mail de fato e uma
acao com efeito fora do orquestrador e este projeto nao tem nenhum servico
de e-mail configurado -- ligar o envio real exige aprovacao explicita antes
de qualquer implementacao de SMTP/API de envio.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pastoreio_orquestrador.models import DecisaoAlocacao


@dataclass
class AlertaSemAlocacao:
    email_lider: str
    grupo_label: str
    datas_sem_alocacao: list[str] = field(default_factory=list)

    @property
    def assunto(self) -> str:
        return (
            f"[Pastoreio] {len(self.datas_sem_alocacao)} vaga(s) sem alocação em {self.grupo_label}"
        )

    @property
    def corpo(self) -> str:
        linhas = "\n".join(f"  - {d}" for d in self.datas_sem_alocacao)
        return (
            f"O motor de alocação não encontrou candidato disponível para "
            f"{len(self.datas_sem_alocacao)} vaga(s) do grupo {self.grupo_label}:\n"
            f"{linhas}\n\n"
            f"Revise a escala manualmente ou ajuste as regras em BP ALGORITIMO."
        )


def montar_alerta_sem_alocacao(
    decisoes: list[DecisaoAlocacao],
    grupo_label: str,
    email_lider: str,
) -> AlertaSemAlocacao | None:
    """Devolve o alerta a ser enviado, ou None se o grupo nao teve nenhuma
    decisao 'SEM ALOCAÇÃO'. Nunca envia nada."""
    datas = [d.slot.data.isoformat() for d in decisoes if d.sem_alocacao]
    if not datas:
        return None
    return AlertaSemAlocacao(email_lider=email_lider, grupo_label=grupo_label, datas_sem_alocacao=datas)
