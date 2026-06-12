"""Unitarios do handler ``NotificarMudancaDeStatus`` (RF-024 / ADR-018).

Cobrem o contrato do aceite do RF-024:

- transicao de status -> e-mail ao cliente com assunto/corpo/destinatario
  corretos;
- contato sem e-mail valido -> skip + log warning, sem chamar a porta;
- excecao do envio -> logada e engolida (falha de envio nunca bloqueia);
- evento que nao e de transicao -> ignorado pelo handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import structlog
from structlog.testing import capture_logs

import src.ordem_servico.aplicacao.notificacoes as notificacoes_modulo
from src.ordem_servico.aplicacao.notificacoes import (
    _STATUS_POR_EVENTO,
    NotificarMudancaDeStatus,
)
from src.ordem_servico.aplicacao.ports import ClienteContatoDTO
from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    OrdemCriadaEvent,
    ServicoFinalizadoEvent,
)
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico

if TYPE_CHECKING:
    from uuid import UUID


@pytest.fixture(autouse=True)
def _logger_fresco(monkeypatch: pytest.MonkeyPatch) -> None:
    # capture_logs nao intercepta loggers ja "bound" e cacheados: se algum
    # teste anterior bootou o app (configurar_logging usa
    # cache_logger_on_first_use=True) e exercitou o handler, o proxy
    # module-level `_log` fica preso aos processors de producao. Um proxy
    # novo por teste devolve o capture deterministico em qualquer ordem.
    monkeypatch.setattr(
        notificacoes_modulo, "_log", structlog.get_logger("test_notificacoes")
    )


class StubRepo:
    def __init__(self, ordem: OrdemDeServico | None) -> None:
        self._ordem = ordem
        self.consultas = 0

    def obter_por_id(self, ordem_id: UUID) -> OrdemDeServico | None:
        self.consultas += 1
        if self._ordem is not None and self._ordem.id == ordem_id:
            return self._ordem
        return None


class StubClienteContatoPort:
    def __init__(self, dto: ClienteContatoDTO | None) -> None:
        self._dto = dto

    def obter_contato(self, cliente_id: UUID) -> ClienteContatoDTO | None:
        return self._dto


class FakeEmailPort:
    def __init__(self, erro: Exception | None = None) -> None:
        self.enviados: list[tuple[str, str, str]] = []
        self._erro = erro

    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        if self._erro is not None:
            raise self._erro
        self.enviados.append((destinatario, assunto, corpo))


def _cenario(
    *,
    contato: str = "maria@cliente.com",
    erro_envio: Exception | None = None,
) -> tuple[OrdemDeServico, NotificarMudancaDeStatus, FakeEmailPort]:
    ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
    email_port = FakeEmailPort(erro=erro_envio)
    handler = NotificarMudancaDeStatus(
        repo=StubRepo(ordem),
        cliente_port=StubClienteContatoPort(
            ClienteContatoDTO(id=ordem.cliente_id, nome="Maria Silva", contato=contato)
        ),
        email_port=email_port,
    )
    return ordem, handler, email_port


class TestNotificarMudancaDeStatus:
    def test_transicao_envia_email_com_assunto_corpo_e_destinatario(self) -> None:
        ordem, handler, email_port = _cenario(
            contato="Maria - maria@cliente.com / (11) 99999-0000"
        )

        handler(ServicoFinalizadoEvent(agregado_id=ordem.id))

        assert len(email_port.enviados) == 1
        destinatario, assunto, corpo = email_port.enviados[0]
        id_curto = str(ordem.id)[:8]
        assert destinatario == "maria@cliente.com"
        assert assunto == f"PytStop — Ordem de Servico {id_curto}: Finalizada"
        assert "Maria Silva" in corpo
        assert "Finalizada" in corpo
        assert id_curto in corpo

    def test_rotulo_da_situacao_usa_vocabulario_do_challenge(self) -> None:
        ordem, handler, email_port = _cenario()

        handler(DiagnosticoIniciadoEvent(agregado_id=ordem.id))

        assert len(email_port.enviados) == 1
        _, assunto, corpo = email_port.enviados[0]
        assert "Em diagnóstico" in assunto
        assert "Em diagnóstico" in corpo

    def test_contato_sem_email_valido_pula_envio_com_warning(self) -> None:
        ordem, handler, email_port = _cenario(contato="(11) 99999-0000")

        with capture_logs() as logs:
            handler(ServicoFinalizadoEvent(agregado_id=ordem.id))

        assert email_port.enviados == []
        warnings = [log for log in logs if log.get("log_level") == "warning"]
        assert any("e-mail" in str(log.get("event", "")) for log in warnings)

    def test_excecao_do_envio_e_logada_e_engolida(self) -> None:
        ordem, handler, email_port = _cenario(
            erro_envio=ConnectionRefusedError("smtp fora do ar")
        )

        with capture_logs() as logs:
            handler(ServicoFinalizadoEvent(agregado_id=ordem.id))

        assert email_port.enviados == []
        assert any(log.get("exc_info") for log in logs)

    def test_evento_que_nao_e_transicao_e_ignorado_sem_consultar_repo(self) -> None:
        ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        repo = StubRepo(ordem)
        email_port = FakeEmailPort()
        handler = NotificarMudancaDeStatus(
            repo=repo,
            cliente_port=StubClienteContatoPort(None),
            email_port=email_port,
        )

        handler(
            OrdemCriadaEvent(
                agregado_id=ordem.id,
                cliente_id=ordem.cliente_id,
                veiculo_id=ordem.veiculo_id,
            )
        )

        assert email_port.enviados == []
        assert repo.consultas == 0

    def test_ordem_inexistente_pula_com_warning(self) -> None:
        email_port = FakeEmailPort()
        handler = NotificarMudancaDeStatus(
            repo=StubRepo(None),
            cliente_port=StubClienteContatoPort(None),
            email_port=email_port,
        )

        with capture_logs() as logs:
            handler(ServicoFinalizadoEvent(agregado_id=uuid4()))

        assert email_port.enviados == []
        assert any(log.get("log_level") == "warning" for log in logs)

    def test_cliente_sem_cadastro_pula_com_warning(self) -> None:
        ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        email_port = FakeEmailPort()
        handler = NotificarMudancaDeStatus(
            repo=StubRepo(ordem),
            cliente_port=StubClienteContatoPort(None),
            email_port=email_port,
        )

        with capture_logs() as logs:
            handler(ServicoFinalizadoEvent(agregado_id=ordem.id))

        assert email_port.enviados == []
        assert any(log.get("log_level") == "warning" for log in logs)


class TestMapaDeEventosDeTransicao:
    def test_todo_evento_de_transicao_tem_status_mapeado(self) -> None:
        """Guard de exaustividade: novo evento de transicao em
        ``dominio/events.py`` sem entrada no mapa significa transicao
        silenciosamente sem notificacao — este teste obriga a decisao
        explicita. ``OrdemCriadaEvent`` fica de fora por desenho: criacao
        nao e mudanca de status (RF-024 notifica atualizacoes).
        """
        import inspect

        from src.compartilhado.dominio.events import DomainEvent
        from src.ordem_servico.dominio import events as eventos_modulo

        eventos_de_transicao = {
            obj
            for _, obj in inspect.getmembers(eventos_modulo, inspect.isclass)
            if issubclass(obj, DomainEvent)
            and obj is not DomainEvent
            and obj is not OrdemCriadaEvent
        }

        assert eventos_de_transicao == set(_STATUS_POR_EVENTO)
