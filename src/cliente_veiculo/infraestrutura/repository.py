from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.infraestrutura.mapping import (
    clientes_table,
    veiculos_table,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from src.cliente_veiculo.dominio.documento import Documento
    from src.cliente_veiculo.dominio.placa import Placa


class ClienteSQLAlchemyRepository:
    """Implementacao SQLAlchemy do contrato `ClienteRepository`.

    Encapsula a sessao e expoe as operacoes de persistencia definidas pelo
    protocolo do dominio. A busca por documento usa o hash deterministico
    para preservar sigilo sem perder indexacao.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def obter_por_id(self, cliente_id: UUID) -> Cliente | None:
        return self._session.get(Cliente, cliente_id)

    def salvar(self, cliente: Cliente) -> None:
        self._session.add(cliente)
        self._session.flush()

    def listar(self, offset: int = 0, limit: int = 20) -> list[Cliente]:
        # order_by explicito garante paginacao deterministica — sem ele, SQL
        # nao assegura a ordem entre paginas e o cliente pode ver itens
        # duplicados ou pulados ao navegar offset/limit.
        stmt = select(Cliente).order_by(clientes_table.c.id).offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def contar(self) -> int:
        stmt = select(func.count()).select_from(clientes_table)
        result = self._session.scalar(stmt)
        return result if result is not None else 0

    def obter_por_documento(self, documento: Documento) -> Cliente | None:
        from src.compartilhado.infraestrutura.encryption import EncryptionService

        enc = EncryptionService.instance()
        doc_hash = enc.hash_deterministic(documento.numero)
        stmt = select(Cliente).where(
            clientes_table.c.documento_hash == doc_hash,
        )
        return self._session.scalars(stmt).first()

    def placa_existe(
        self, placa: Placa, excluir_cliente_id: UUID | None = None
    ) -> bool:
        stmt = (
            select(func.count())
            .select_from(veiculos_table)
            .where(
                veiculos_table.c.placa == placa.valor,
            )
        )
        if excluir_cliente_id is not None:
            stmt = stmt.where(
                veiculos_table.c.cliente_id != excluir_cliente_id,
            )
        result = self._session.scalar(stmt)
        return (result or 0) > 0
