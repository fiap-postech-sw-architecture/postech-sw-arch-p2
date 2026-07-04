"""Factory functions wiring each OS use case to concrete infrastructure.

This module is the **composition root** for the OS bounded context:
it is the ONLY file under ``src/ordem_servico/interfaces/`` allowed
to import from ``src/ordem_servico/infraestrutura/``. Every factory
takes a request-scoped SQLAlchemy ``Session`` and returns a freshly
constructed use case instance with its repository, UnitOfWork, and
cross-context adapters wired in. The router injects these factories
via ``Depends(...)`` in each endpoint handler.

Infrastructure classes and the use cases are imported at module level:
there is no import cycle here (``use_cases`` never imports back into
``interfaces``), and the router already loads this module during FastAPI
startup, so hoisting the imports costs nothing extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
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
from src.ordem_servico.infraestrutura.adapters import (
    CatalogoSQLAlchemyAdapter,
    ClienteSQLAlchemyAdapter,
    EstoqueSQLAlchemyAdapter,
)
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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


def obter_criar_ordem(session: Session) -> CriarOrdem:
    """Wires ``CriarOrdem`` com os adapters de Cliente, Catalogo e Estoque.

    Catalogo e Estoque entraram com o RF-020: a criacao pode receber
    servicos/pecas e usa os ports para validar e precificar cada linha
    na mesma transacao da OS.
    """
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
    return AdicionarItem(
        repo=_repo(session),
        uow=_uow(session),
        catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
    )


def obter_remover_item(session: Session) -> RemoverItem:
    """Wires ``RemoverItem`` (no cross-context port needed)."""
    return RemoverItem(repo=_repo(session), uow=_uow(session))


def obter_iniciar_diagnostico(session: Session) -> IniciarDiagnostico:
    """Wires ``IniciarDiagnostico`` (pure domain transition)."""
    return IniciarDiagnostico(repo=_repo(session), uow=_uow(session))


def obter_gerar_orcamento(session: Session) -> GerarOrcamento:
    """Wires ``GerarOrcamento`` (pure domain transition)."""
    return GerarOrcamento(repo=_repo(session), uow=_uow(session))


def obter_aprovar_orcamento(session: Session) -> AprovarOrcamento:
    """Wires ``AprovarOrcamento`` with ``EstoqueSQLAlchemyAdapter`` for reserva."""
    return AprovarOrcamento(
        repo=_repo(session),
        uow=_uow(session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
    )


def obter_finalizar_servico(session: Session) -> FinalizarServico:
    """Wires ``FinalizarServico`` (pure domain transition)."""
    return FinalizarServico(repo=_repo(session), uow=_uow(session))


def obter_registrar_entrega(session: Session) -> RegistrarEntrega:
    """Wires ``RegistrarEntrega`` (pure domain transition)."""
    return RegistrarEntrega(repo=_repo(session), uow=_uow(session))


def obter_cancelar_ordem(session: Session) -> CancelarOrdem:
    """Wires ``CancelarOrdem`` with ``EstoqueSQLAlchemyAdapter`` for liberacao."""
    return CancelarOrdem(
        repo=_repo(session),
        uow=_uow(session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
    )


def obter_gerar_complementar(session: Session) -> GerarOrcamentoComplementar:
    """Wires ``GerarOrcamentoComplementar`` (pure domain transition)."""
    return GerarOrcamentoComplementar(repo=_repo(session), uow=_uow(session))


def obter_aprovar_complementar(session: Session) -> AprovarOrcamentoComplementar:
    """Wires ``AprovarOrcamentoComplementar`` (pure domain transition)."""
    return AprovarOrcamentoComplementar(repo=_repo(session), uow=_uow(session))


def obter_rejeitar_complementar(session: Session) -> RejeitarOrcamentoComplementar:
    """Wires ``RejeitarOrcamentoComplementar`` (reverte escopo + libera reservas)."""
    return RejeitarOrcamentoComplementar(
        repo=_repo(session),
        uow=_uow(session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
    )


def obter_decidir_orcamento(session: Session) -> DecidirOrcamento:
    """Wires ``DecidirOrcamento`` compondo os tres caminhos delegados (RF-022).

    Consumido pelo router publico (canal externo autenticado por token
    dedicado, ADR-021) — mesmo trilho da consulta de acompanhamento.
    Reusa as factories dos casos de uso existentes para que a
    reserva/liberacao de estoque continue com o wiring canonico.
    """
    return DecidirOrcamento(
        repo=_repo(session),
        aprovar_orcamento=obter_aprovar_orcamento(session),
        aprovar_complementar=obter_aprovar_complementar(session),
        cancelar_ordem=obter_cancelar_ordem(session),
    )


def obter_listar_ordens(session: Session) -> ListarOrdens:
    """Wires ``ListarOrdens`` (query-only, no UoW)."""
    return ListarOrdens(repo=_repo(session))


def obter_obter_ordem(session: Session) -> ObterOrdem:
    """Wires ``ObterOrdem`` (query-only, no UoW)."""
    return ObterOrdem(repo=_repo(session))


def obter_metricas(session: Session) -> ObterMetricas:
    """Wires ``ObterMetricas`` (query-only, no UoW)."""
    return ObterMetricas(repo=_repo(session))


def obter_consultar_acompanhamento(session: Session) -> ConsultarAcompanhamento:
    """Wires ``ConsultarAcompanhamento`` (query-only, consumido pelo router publico)."""
    return ConsultarAcompanhamento(repo=_repo(session))


def obter_enriquecer_ordem(session: Session) -> EnriquecerOrdemDeServico:
    """Wires ``EnriquecerOrdemDeServico`` com Catalogo + Estoque + Cliente adapters.

    Query handler chamado pelo router para resolver ``servico_nome``,
    ``item_estoque_nome``, ``cliente_nome`` e ``veiculo_placa``
    server-side antes de mapear o DTO pra Pydantic. Mantem o router
    fora do contato direto com agregados de contextos vizinhos
    (issue #87).
    """
    return EnriquecerOrdemDeServico(
        catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
        cliente_port=ClienteSQLAlchemyAdapter(session=session),
    )
