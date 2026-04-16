from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.cliente_veiculo.dominio.consentimento import ConsentimentoCliente
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.exceptions import (
    ClienteNaoEncontradoException,
    ConsentimentoNaoEncontradoException,
)

if TYPE_CHECKING:
    from uuid import UUID

    from src.cliente_veiculo.aplicacao.dtos import (
        ConsentimentoDTO,
        DadosPessoaisDTO,
        RegistrarConsentimentoDTO,
    )
    from src.cliente_veiculo.dominio.repository import ClienteRepository
    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork


class ExportarDadosPessoais:
    def __init__(self, repo: ClienteRepository) -> None:
        self._repo = repo

    def executar(self, cliente_id: UUID) -> DadosPessoaisDTO:
        from src.cliente_veiculo.aplicacao.dtos import DadosPessoaisDTO

        cliente = self._repo.obter_por_id(cliente_id)
        if cliente is None:
            raise ClienteNaoEncontradoException()
        return DadosPessoaisDTO(
            id=cliente.id,
            nome=cliente.nome,
            documento_formatado=cliente.documento.formatado(),
            tipo_documento=("cpf" if isinstance(cliente.documento, CPF) else "cnpj"),
            contato=cliente.contato,
            veiculos=[
                {
                    "id": str(v.id),
                    "placa": v.placa.valor,
                    "marca": v.marca,
                    "modelo": v.modelo,
                    "ano": v.ano,
                }
                for v in cliente.veiculos
            ],
            ativo=cliente.ativo,
        )


class ExcluirDadosPessoais:
    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, cliente_id: UUID) -> None:
        cliente = self._repo.obter_por_id(cliente_id)
        if cliente is None:
            raise ClienteNaoEncontradoException()
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
        from src.cliente_veiculo.aplicacao.dtos import ConsentimentoDTO

        cliente = self._repo.obter_por_id(cliente_id)
        if cliente is None:
            raise ClienteNaoEncontradoException()
        agora = datetime.now(tz=UTC)
        consentimento = ConsentimentoCliente(
            _cliente_id=cliente_id,
            _tipo=dto.tipo,
            _concedido_em=agora,
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
