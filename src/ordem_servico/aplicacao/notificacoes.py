"""Notificacao de mudanca de status da OS por e-mail (RF-024 / ADR-018).

Handler invocado pelo relay da outbox (RF-018 / TD-008): a cada evento de
TRANSICAO de status entregue, resolve o cliente via ``ClientePort``
(cross-context, sem tocar o dominio vizinho), extrai o e-mail do campo
livre ``contato`` e envia a notificacao pela ``EmailPort``.

Politica de falha: o relay e o unico caller, entao o contrato de erro
distingue dois casos:

- "nada a entregar" (ordem/cliente/e-mail ausentes): NAO-FATAL — log
  warning e skip; retentar nao resolveria, entao o relay finaliza a linha
  (``entregue``);
- falha de TRANSPORTE no envio (``FalhaEnvioEmailException``, levantada
  pelo adapter): PROPAGA — o relay traduz em retry -> backoff -> DLQ.
  Engolir aqui marcaria a linha ``entregue`` e perderia o e-mail sem
  nenhuma retentativa.

Validacao de e-mail: regex simples (RFC-relaxada), por decisao. O campo
``contato`` e texto livre ("Maria - maria@x.com / (11) 9..."), entao o
handler EXTRAI o primeiro token com forma de e-mail em vez de validar o
campo inteiro; pydantic/EmailStr validaria o campo completo (e poria
dependencia de framework na aplicacao) sem resolver a extracao. Mesmo
padrao do scrubber de PII em ``compartilhado/infraestrutura/logging.py``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

import structlog

from src.ordem_servico.aplicacao.ports import FalhaEnvioEmailException
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

# Evento de transicao -> status NOVO da ordem. FALLBACK para linhas antigas da
# outbox (gravadas antes de ``TransicaoStatusEvent.status_novo`` existir): o
# handler prefere ``evento.status_novo`` do payload quando presente e so cai
# neste mapa quando o campo vem ``None``. ``OrdemCriadaEvent`` fica de fora por
# desenho: criacao nao e atualizacao de status. O guard de exaustividade em
# ``tests/unitarios/ordem_servico/test_notificacoes.py`` obriga decisao
# explicita para cada novo evento do dominio.
_STATUS_POR_EVENTO: Final[dict[type[DomainEvent], StatusOrdem]] = {
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
# livre do contato (que pode misturar nome e telefone). O dominio e casado
# label a label (`.` fora da classe, so como separador) para eliminar o
# backtracking polinomial (hotspot S5852 do SonarQube); o input ja chega
# limitado a 255 chars pelo VO Contato.
_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)


def _extrair_email(contato: str) -> str | None:
    """Extrai o primeiro e-mail do campo livre de contato, ou ``None``."""
    match = _EMAIL_RE.search(contato)
    return None if match is None else match.group()


class NotificarMudancaDeStatus:
    """Handler de eventos de transicao: envia e-mail de situacao ao cliente.

    Eventos de transicao carregam apenas ``agregado_id`` (ver docstring de
    ``dominio/events.py``: handlers re-buscam o agregado); o relay abre uma
    session propria por entrega (``relay/handlers.py``) e o handler
    re-busca a ordem nela.
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
        """Notifica a transicao por e-mail.

        "Nada a entregar" (ordem/cliente/e-mail ausentes) vira log warning e
        skip — nao-fatal. Falha de transporte do envio PROPAGA para o relay
        dirigir retry/backoff/DLQ (TD-008).

        Raises:
            FalhaEnvioEmailException: falha de transporte no envio,
                traduzida pelo adapter da ``EmailPort``.
        """
        # Prefere o status auto-suficiente do payload (TransicaoStatusEvent);
        # cai no mapa apenas para linhas antigas da outbox sem o campo.
        status_novo = getattr(evento, "status_novo", None) or _STATUS_POR_EVENTO.get(
            type(evento)
        )
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
        except FalhaEnvioEmailException:
            # Falha de TRANSPORTE (SMTP fora, timeout, recusa — traduzida
            # pelo adapter na excecao da porta): PROPAGA. O relay (unico
            # caller) traduz a excecao em retry -> backoff -> DLQ. Engolir
            # aqui marcaria a linha `entregue` e perderia o e-mail sem retry.
            # Os skips acima (ordem/cliente/e-mail ausentes) seguem
            # nao-fatais por desenho: retentar nao resolve "nada a enviar",
            # entao a linha e corretamente finalizada.
            _log.exception(
                "falha ao enviar e-mail de mudanca de status",
                ordem_id=str(ordem.id),
                situacao=situacao,
            )
            raise
