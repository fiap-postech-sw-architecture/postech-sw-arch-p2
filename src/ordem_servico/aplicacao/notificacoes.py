"""Notificacao de mudanca de status da OS por e-mail (RF-024 / ADR-018).

Handler registrado no ``EventDispatcher``: a cada evento de TRANSICAO de
status, resolve o cliente via ``ClientePort`` (cross-context, sem tocar o
dominio vizinho), extrai o e-mail do campo livre ``contato`` e envia a
notificacao pela ``EmailPort``.

Politica de falha (aceite do RF-024): nada aqui interrompe a transicao —
contato sem e-mail valido e cliente/ordem ausentes geram log warning e
skip; excecao do envio e logada e engolida.

Validacao de e-mail: regex simples (RFC-relaxada), por decisao. O campo
``contato`` e texto livre ("Maria - maria@x.com / (11) 9..."), entao o
handler EXTRAI o primeiro token com forma de e-mail em vez de validar o
campo inteiro; pydantic/EmailStr validaria o campo completo (e poria
dependencia de framework na aplicacao) sem resolver a extracao. Mesmo
padrao do scrubber de PII em ``compartilhado/infraestrutura/logging.py``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from src.ordem_servico.aplicacao.situacoes import situacao_de
from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    EntregaRegistradaEvent,
    OrcamentoAprovadoEvent,
    OrcamentoComplementarAprovadoEvent,
    OrcamentoComplementarGeradoEvent,
    OrcamentoComplementarRejeitadoEvent,
    OrcamentoGeradoEvent,
    OrdemCanceladaEvent,
    ServicoFinalizadoEvent,
)
from src.ordem_servico.dominio.status import StatusOrdem

if TYPE_CHECKING:
    from src.compartilhado.dominio.events import DomainEvent
    from src.ordem_servico.aplicacao.ports import ClientePort, EmailPort
    from src.ordem_servico.dominio.repository import OrdemDeServicoRepository

_log = structlog.get_logger(__name__)

# Evento de transicao -> status NOVO da ordem. ``OrdemCriadaEvent`` fica
# de fora por desenho: criacao nao e atualizacao de status. O guard de
# exaustividade em ``tests/unitarios/ordem_servico/test_notificacoes.py``
# obriga decisao explicita para cada novo evento do dominio.
_STATUS_POR_EVENTO: dict[type[DomainEvent], StatusOrdem] = {
    DiagnosticoIniciadoEvent: StatusOrdem.EM_DIAGNOSTICO,
    OrcamentoGeradoEvent: StatusOrdem.AGUARDANDO_APROVACAO,
    OrcamentoAprovadoEvent: StatusOrdem.EM_EXECUCAO,
    ServicoFinalizadoEvent: StatusOrdem.FINALIZADA,
    EntregaRegistradaEvent: StatusOrdem.ENTREGUE,
    OrdemCanceladaEvent: StatusOrdem.CANCELADA,
    OrcamentoComplementarGeradoEvent: StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR,
    OrcamentoComplementarAprovadoEvent: StatusOrdem.EM_EXECUCAO,
    OrcamentoComplementarRejeitadoEvent: StatusOrdem.EM_EXECUCAO,
}

# Forma minima local@dominio.tld; extrai o primeiro candidato do texto
# livre do contato (que pode misturar nome e telefone).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _extrair_email(contato: str) -> str | None:
    """Extrai o primeiro e-mail do campo livre de contato, ou ``None``."""
    match = _EMAIL_RE.search(contato)
    return None if match is None else match.group()


class NotificarMudancaDeStatus:
    """Handler de eventos de transicao: envia e-mail de situacao ao cliente.

    Eventos de transicao carregam apenas ``agregado_id`` (ver docstring de
    ``dominio/events.py``: handlers re-buscam o agregado); o handler roda
    pos-commit na mesma session da request, entao a re-busca sai do
    identity map sem custo extra.
    """

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        cliente_port: ClientePort,
        email_port: EmailPort,
    ) -> None:
        self._repo = repo
        self._cliente_port = cliente_port
        self._email_port = email_port

    def __call__(self, evento: DomainEvent) -> None:
        """Notifica a transicao; qualquer impedimento vira log, nunca excecao."""
        status_novo = _STATUS_POR_EVENTO.get(type(evento))
        if status_novo is None:
            return  # evento que nao e de transicao (ex.: OrdemCriadaEvent)

        ordem = self._repo.obter_por_id(evento.agregado_id)
        if ordem is None:
            _log.warning(
                "notificacao pulada: ordem nao encontrada",
                agregado_id=str(evento.agregado_id),
            )
            return

        cliente = self._cliente_port.obter_contato(ordem.cliente_id)
        if cliente is None:
            _log.warning(
                "notificacao pulada: cliente nao encontrado",
                ordem_id=str(ordem.id),
            )
            return

        destinatario = _extrair_email(cliente.contato)
        if destinatario is None:
            _log.warning(
                "notificacao pulada: contato do cliente sem e-mail valido",
                ordem_id=str(ordem.id),
                cliente_id=str(cliente.id),
            )
            return

        id_curto = str(ordem.id)[:8]
        situacao = situacao_de(status_novo)
        assunto = f"PytStop — Ordem de Servico {id_curto}: {situacao}"
        corpo = (
            f"Olá, {cliente.nome}!\n"
            f"\n"
            f"A situação da sua ordem de serviço {id_curto} foi atualizada "
            f"para: {situacao}.\n"
            f"\n"
            f"Em caso de dúvida, fale com a oficina.\n"
            f"\n"
            f"Equipe PytStop\n"
        )
        try:
            self._email_port.enviar(
                destinatario=destinatario, assunto=assunto, corpo=corpo
            )
        except Exception:  # noqa: BLE001 — falha de envio nunca bloqueia a transicao (RF-024)
            _log.exception(
                "falha ao enviar e-mail de mudanca de status",
                ordem_id=str(ordem.id),
                situacao=situacao,
            )
