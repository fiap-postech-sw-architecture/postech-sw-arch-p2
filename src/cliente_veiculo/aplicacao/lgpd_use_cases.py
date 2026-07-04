from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.cliente_veiculo.aplicacao.dtos import (
    ConsentimentoDTO,
    DadosPessoaisDTO,
)
from src.cliente_veiculo.aplicacao.use_cases import (
    obter_cliente_ou_falhar,
    tipo_documento,
    veiculo_dto,
)
from src.cliente_veiculo.dominio.consentimento import ConsentimentoCliente
from src.cliente_veiculo.dominio.exceptions import (
    ConsentimentoNaoEncontradoException,
)
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException

if TYPE_CHECKING:
    from uuid import UUID

    from src.cliente_veiculo.aplicacao.dtos import RegistrarConsentimentoDTO
    from src.cliente_veiculo.aplicacao.ports import OrdemDeServicoPort
    from src.cliente_veiculo.dominio.repository import ClienteRepository
    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork


class ExportarDadosPessoais:
    def __init__(self, repo: ClienteRepository) -> None:
        self._repo = repo

    def executar(self, cliente_id: UUID) -> DadosPessoaisDTO:
        cliente = obter_cliente_ou_falhar(self._repo, cliente_id)
        return DadosPessoaisDTO(
            id=cliente.id,
            nome=cliente.nome,
            documento_formatado=cliente.documento.formatado(),
            tipo_documento=tipo_documento(cliente),
            contato=cliente.contato.valor,
            veiculos=[veiculo_dto(v) for v in cliente.veiculos],
            ativo=cliente.ativo,
        )


class ExcluirDadosPessoais:
    """Anonimiza (erasure LGPD) os dados de um cliente sem OS ativa.

    Espelha o guard de `DesativarCliente`: consulta
    `OrdemDeServicoPort.existe_os_ativa_para_cliente` antes de apagar e, se
    houver OS ativa, levanta `ViolacaoRegraDeNegocioException` (409). A LGPD
    (Art. 16) permite reter dados pessoais para a execucao de um contrato, e
    uma OS ativa e justamente esse contrato em andamento — apagar agora
    quebraria a prestacao do servico.
    """

    def __init__(
        self,
        repo: ClienteRepository,
        uow: UnitOfWork,
        os_port: OrdemDeServicoPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._os_port = os_port

    def executar(self, cliente_id: UUID) -> None:
        obter_cliente_ou_falhar(self._repo, cliente_id)
        if self._os_port.existe_os_ativa_para_cliente(cliente_id):
            raise ViolacaoRegraDeNegocioException(
                mensagem="Cliente possui ordem de servico ativa"
            )
        with self._uow:
            self._repo.anonimizar_dados(cliente_id)
            self._uow.commit()


class RegistrarConsentimento:
    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(
        self, cliente_id: UUID, dto: RegistrarConsentimentoDTO
    ) -> ConsentimentoDTO:
        obter_cliente_ou_falhar(self._repo, cliente_id)
        existente = self._repo.obter_consentimento(cliente_id, dto.tipo)
        if existente is not None and existente.ativo:
            # Grant-grant do mesmo tipo: ja existe consentimento ativo para o
            # par cliente+tipo. Levanta violacao de regra (409 no mapeamento
            # de erros existente) em vez de criar registro ativo duplicado.
            raise ViolacaoRegraDeNegocioException(
                mensagem="Consentimento ativo ja existe para este tipo"
            )
        agora = datetime.now(tz=UTC)
        consentimento = ConsentimentoCliente.criar(
            cliente_id=cliente_id,
            tipo=dto.tipo,
            concedido_em=agora,
        )
        with self._uow:
            self._repo.salvar_consentimento(consentimento)
            self._uow.commit()
        return ConsentimentoDTO(
            id=consentimento.id,
            cliente_id=consentimento.cliente_id,
            tipo=consentimento.tipo,
            concedido_em=consentimento.concedido_em,
            revogado_em=consentimento.revogado_em,
            ativo=consentimento.ativo,
        )


class RevogarConsentimento:
    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, cliente_id: UUID, tipo: str) -> None:
        consentimento = self._repo.obter_consentimento(cliente_id, tipo)
        if consentimento is None:
            raise ConsentimentoNaoEncontradoException()
        agora = datetime.now(tz=UTC)
        consentimento.revogar(agora)
        with self._uow:
            self._repo.salvar_consentimento(consentimento)
            self._uow.commit()
