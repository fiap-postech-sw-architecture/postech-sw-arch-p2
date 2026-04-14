from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.cliente_veiculo.dominio.cliente import Cliente
    from src.cliente_veiculo.dominio.documento import Documento
    from src.cliente_veiculo.dominio.placa import Placa


class ClienteRepository(Protocol):
    """Contrato de persistencia para o agregado Cliente.

    Define as operacoes que qualquer implementacao (SQLAlchemy, in-memory, fake)
    precisa oferecer.
    """

    def obter_por_id(self, cliente_id: UUID) -> Cliente | None:
        """Retorna o Cliente pela chave primaria ou None se nao existir."""
        ...

    def salvar(self, cliente: Cliente) -> None:
        """Persiste insercoes e atualizacoes do agregado Cliente."""
        ...

    def listar(self, offset: int = 0, limit: int = 20) -> list[Cliente]:
        """Lista clientes paginados (padrao: 20 por pagina)."""
        ...

    def contar(self) -> int:
        """Retorna o total de clientes cadastrados."""
        ...

    def obter_por_documento(self, documento: Documento) -> Cliente | None:
        """Busca por documento (CPF ou CNPJ) para verificacao de duplicacao."""
        ...

    def placa_existe(
        self, placa: Placa, excluir_cliente_id: UUID | None = None
    ) -> bool:
        """Indica se a placa ja esta cadastrada em outro cliente.

        `excluir_cliente_id` permite ignorar o proprio cliente durante updates.
        """
        ...
