"""Factory functions wiring each OS use case to concrete infrastructure.

This module is the **composition root** for the OS bounded context:
it is the ONLY file under ``src/ordem_servico/interfaces/`` allowed
to import from ``src/ordem_servico/infraestrutura/``. Every factory
takes a request-scoped SQLAlchemy ``Session`` and returns a freshly
constructed use case instance with its repository, UnitOfWork, and
cross-context adapters wired in. The router injects these factories
via ``Depends(...)`` in each endpoint handler.

Infrastructure classes (``OrdemDeServicoSQLAlchemyRepository``,
``SQLAlchemyUnitOfWork``, the three ``*SQLAlchemyAdapter`` classes)
are imported at module level — this is the composition root and is
allowed to know about infra. Use-case imports (``from
src.ordem_servico.aplicacao.use_cases import X``) stay LOCAL inside
each factory body because they would create a load-time import cycle
if hoisted (``use_cases`` imports ``dtos``/``ports``, and those
transitively could be re-entered). Keeping the use-case imports lazy
keeps this module cheap to load during FastAPI startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
from src.ordem_servico.aplicacao.notificacoes import (
    NotificarMudancaDeStatus,  # noqa: F401  # removido na Task 11
)
from src.ordem_servico.infraestrutura.adapters import (
    CatalogoSQLAlchemyAdapter,
    ClienteSQLAlchemyAdapter,
    EstoqueSQLAlchemyAdapter,
)
from src.ordem_servico.infraestrutura.email_adapter import SmtpEmailAdapter
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.ordem_servico.aplicacao.ports import EmailPort
    from src.ordem_servico.aplicacao.queries import EnriquecerOrdemDeServico
    from src.ordem_servico.aplicacao.use_cases import (
        AdicionarItem,
        AprovarOrcamento,
        AprovarOrcamentoComplementar,
        CancelarOrdem,
        ConsultarAcompanhamento,
        CriarOrdem,
        DecidirOrcamento,
        FinalizarServico,
        GerarOrcamento,
        GerarOrcamentoComplementar,
        IniciarDiagnostico,
        ListarOrdens,
        ObterMetricas,
        ObterOrdem,
        RegistrarEntrega,
        RejeitarOrcamentoComplementar,
        RemoverItem,
    )


def _repo(session: Session) -> OrdemDeServicoSQLAlchemyRepository:
    """Constroi o repositorio concreto atrelado a session request-escopada."""
    return OrdemDeServicoSQLAlchemyRepository(session=session)


def _uow(session: Session) -> SQLAlchemyUnitOfWork:
    """Constroi a UoW compartilhando a mesma session do repositorio.

    ``session_factory=lambda: session`` garante que o UoW, o repo e os
    adapters escrevam e commitem na MESMA session — essencial para o
    escopo transacional dos casos de uso como ``AprovarOrcamento``.
    """
    return SQLAlchemyUnitOfWork(session_factory=lambda: session)


def obter_email_port() -> EmailPort:
    """Factory do adapter de e-mail (RF-024 / ADR-018).

    Seam unico de substituicao: os use cases do contexto OS sao
    construidos por estas factories (nao por FastAPI ``Depends``), entao
    testes E2E trocam o SMTP por um fake com
    ``monkeypatch.setattr(dependencies, "obter_email_port", ...)`` em vez
    de ``app.dependency_overrides``. Sem SMTP no ar (dev/test), a falha
    de conexao e engolida e logada pelo handler — nunca bloqueia a
    transicao.
    """
    return SmtpEmailAdapter()


def _dispatcher(session: Session) -> EventDispatcher:
    """Monta o dispatcher sincrono dos DOMAIN EVENTS PUROS do contexto OS.

    O handler de e-mail (RF-024) migrou para a Transactional Outbox
    (RF-018 / TD-008): a ``UnitOfWork`` enfileira os ``IntegrationEvent``
    na ``outbox`` no commit e o relay (``python -m relay``) os entrega de
    forma duravel. Manter o e-mail tambem aqui causaria entrega dupla.

    Hoje nenhum domain event puro tem consumidor sincrono, entao o
    dispatcher fica sem handlers; permanece no fluxo (e o
    ``_despachar_pos_commit`` dos use cases continua entregando os domain
    events puros preservados pela UoW) para que novos consumidores
    sincronos entrem aqui sem tocar os use cases.
    """
    return EventDispatcher(handlers=())


def obter_criar_ordem(session: Session) -> CriarOrdem:
    """Wires ``CriarOrdem`` com os adapters de Cliente, Catalogo e Estoque.

    Catalogo e Estoque entraram com o RF-020: a criacao pode receber
    servicos/pecas e usa os ports para validar e precificar cada linha
    na mesma transacao da OS.
    """
    from src.ordem_servico.aplicacao.use_cases import CriarOrdem

    return CriarOrdem(
        repo=_repo(session),
        uow=_uow(session),
        cliente_port=ClienteSQLAlchemyAdapter(session=session),
        catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
    )


def obter_adicionar_item(session: Session) -> AdicionarItem:
    """Wires ``AdicionarItem`` com ``CatalogoSQLAlchemyAdapter`` e
    ``EstoqueSQLAlchemyAdapter``.

    O adapter de estoque e necessario porque, quando a linha tem
    ``item_estoque_id``, o ``preco_unitario`` precisa vir do estoque em
    vez do servico (linha de peca consumida vs mao de obra).
    """
    from src.ordem_servico.aplicacao.use_cases import AdicionarItem

    return AdicionarItem(
        repo=_repo(session),
        uow=_uow(session),
        catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
    )


def obter_remover_item(session: Session) -> RemoverItem:
    """Wires ``RemoverItem`` (no cross-context port needed)."""
    from src.ordem_servico.aplicacao.use_cases import RemoverItem

    return RemoverItem(repo=_repo(session), uow=_uow(session))


def obter_iniciar_diagnostico(session: Session) -> IniciarDiagnostico:
    """Wires ``IniciarDiagnostico`` (pure domain transition)."""
    from src.ordem_servico.aplicacao.use_cases import IniciarDiagnostico

    return IniciarDiagnostico(
        repo=_repo(session),
        uow=_uow(session),
        dispatcher=_dispatcher(session),
    )


def obter_gerar_orcamento(session: Session) -> GerarOrcamento:
    """Wires ``GerarOrcamento`` (pure domain transition)."""
    from src.ordem_servico.aplicacao.use_cases import GerarOrcamento

    return GerarOrcamento(
        repo=_repo(session),
        uow=_uow(session),
        dispatcher=_dispatcher(session),
    )


def obter_aprovar_orcamento(session: Session) -> AprovarOrcamento:
    """Wires ``AprovarOrcamento`` with ``EstoqueSQLAlchemyAdapter`` for reserva."""
    from src.ordem_servico.aplicacao.use_cases import AprovarOrcamento

    return AprovarOrcamento(
        repo=_repo(session),
        uow=_uow(session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
        dispatcher=_dispatcher(session),
    )


def obter_finalizar_servico(session: Session) -> FinalizarServico:
    """Wires ``FinalizarServico`` (pure domain transition)."""
    from src.ordem_servico.aplicacao.use_cases import FinalizarServico

    return FinalizarServico(
        repo=_repo(session),
        uow=_uow(session),
        dispatcher=_dispatcher(session),
    )


def obter_registrar_entrega(session: Session) -> RegistrarEntrega:
    """Wires ``RegistrarEntrega`` (pure domain transition)."""
    from src.ordem_servico.aplicacao.use_cases import RegistrarEntrega

    return RegistrarEntrega(
        repo=_repo(session),
        uow=_uow(session),
        dispatcher=_dispatcher(session),
    )


def obter_cancelar_ordem(session: Session) -> CancelarOrdem:
    """Wires ``CancelarOrdem`` with ``EstoqueSQLAlchemyAdapter`` for liberacao."""
    from src.ordem_servico.aplicacao.use_cases import CancelarOrdem

    return CancelarOrdem(
        repo=_repo(session),
        uow=_uow(session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
        dispatcher=_dispatcher(session),
    )


def obter_gerar_complementar(session: Session) -> GerarOrcamentoComplementar:
    """Wires ``GerarOrcamentoComplementar`` (pure domain transition)."""
    from src.ordem_servico.aplicacao.use_cases import (
        GerarOrcamentoComplementar,
    )

    return GerarOrcamentoComplementar(
        repo=_repo(session),
        uow=_uow(session),
        dispatcher=_dispatcher(session),
    )


def obter_aprovar_complementar(session: Session) -> AprovarOrcamentoComplementar:
    """Wires ``AprovarOrcamentoComplementar`` (pure domain transition)."""
    from src.ordem_servico.aplicacao.use_cases import (
        AprovarOrcamentoComplementar,
    )

    return AprovarOrcamentoComplementar(
        repo=_repo(session),
        uow=_uow(session),
        dispatcher=_dispatcher(session),
    )


def obter_rejeitar_complementar(session: Session) -> RejeitarOrcamentoComplementar:
    """Wires ``RejeitarOrcamentoComplementar`` (pure domain transition)."""
    from src.ordem_servico.aplicacao.use_cases import (
        RejeitarOrcamentoComplementar,
    )

    return RejeitarOrcamentoComplementar(
        repo=_repo(session),
        uow=_uow(session),
        dispatcher=_dispatcher(session),
    )


def obter_decidir_orcamento(session: Session) -> DecidirOrcamento:
    """Wires ``DecidirOrcamento`` compondo os tres caminhos delegados (RF-022).

    Consumido pelo router publico (canal externo autenticado por token
    dedicado, ADR-021) via import lazy — mesmo trilho da consulta de
    acompanhamento. Reusa as factories dos casos de uso existentes para
    que a reserva/liberacao de estoque continue com o wiring canonico.
    """
    from src.ordem_servico.aplicacao.use_cases import DecidirOrcamento

    return DecidirOrcamento(
        repo=_repo(session),
        aprovar_orcamento=obter_aprovar_orcamento(session),
        aprovar_complementar=obter_aprovar_complementar(session),
        cancelar_ordem=obter_cancelar_ordem(session),
    )


def obter_listar_ordens(session: Session) -> ListarOrdens:
    """Wires ``ListarOrdens`` (query-only, no UoW)."""
    from src.ordem_servico.aplicacao.use_cases import ListarOrdens

    return ListarOrdens(repo=_repo(session))


def obter_obter_ordem(session: Session) -> ObterOrdem:
    """Wires ``ObterOrdem`` (query-only, no UoW)."""
    from src.ordem_servico.aplicacao.use_cases import ObterOrdem

    return ObterOrdem(repo=_repo(session))


def obter_metricas(session: Session) -> ObterMetricas:
    """Wires ``ObterMetricas`` (query-only, no UoW)."""
    from src.ordem_servico.aplicacao.use_cases import ObterMetricas

    return ObterMetricas(repo=_repo(session))


def obter_consultar_acompanhamento(session: Session) -> ConsultarAcompanhamento:
    """Wires ``ConsultarAcompanhamento`` (query-only, consumido pelo router publico)."""
    from src.ordem_servico.aplicacao.use_cases import ConsultarAcompanhamento

    return ConsultarAcompanhamento(repo=_repo(session))


def obter_enriquecer_ordem(session: Session) -> EnriquecerOrdemDeServico:
    """Wires ``EnriquecerOrdemDeServico`` com Catalogo + Estoque + Cliente adapters.

    Query handler chamado pelo router para resolver ``servico_nome``,
    ``item_estoque_nome``, ``cliente_nome`` e ``veiculo_placa``
    server-side antes de mapear o DTO pra Pydantic. Mantem o router
    fora do contato direto com agregados de contextos vizinhos
    (issue #87).
    """
    from src.ordem_servico.aplicacao.queries import EnriquecerOrdemDeServico

    return EnriquecerOrdemDeServico(
        catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
        cliente_port=ClienteSQLAlchemyAdapter(session=session),
    )
