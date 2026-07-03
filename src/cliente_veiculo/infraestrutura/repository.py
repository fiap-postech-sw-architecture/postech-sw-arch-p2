from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.consentimento import ConsentimentoCliente
from src.cliente_veiculo.infraestrutura.mapping import (
    clientes_table,
    consentimentos_table,
    veiculos_table,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from src.cliente_veiculo.dominio.documento import Documento
    from src.cliente_veiculo.dominio.placa import Placa


class ClienteSQLAlchemyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obter_por_id(self, cliente_id: UUID) -> Cliente | None:
        return self._session.get(Cliente, cliente_id)

    def bloquear_veiculo_para_remocao(self, veiculo_id: UUID) -> bool:
        """Adquire ``FOR UPDATE`` na linha do veiculo para serializar com INSERTs em
        ``ordens_de_servico``: a validacao de FK em INSERT pega ``FOR KEY SHARE``
        no veiculo referenciado, que conflita com ``FOR UPDATE``.

        Retorna ``True`` se a linha foi travada e ``False`` se ela ja nao existe
        (caso de duplo-DELETE concorrente: a Tx perdedora deve mapear esse
        retorno para ``VeiculoNaoEncontradoException`` em vez de prosseguir e
        deixar o ``flush`` levantar ``StaleDataError``).
        """
        stmt = (
            select(veiculos_table.c.id)
            .where(veiculos_table.c.id == veiculo_id)
            .with_for_update()
        )
        return self._session.execute(stmt).first() is not None

    def salvar(self, cliente: Cliente) -> None:
        self._session.add(cliente)
        self._session.flush()

    def listar(self, offset: int = 0, limit: int = 20) -> list[Cliente]:
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

    def anonimizar_dados(self, cliente_id: UUID) -> None:
        from sqlalchemy import select, update

        # Bypass SQLAlchemy ORM event listeners via raw UPDATE.
        # The before_update listener recalculates _documento_numero and
        # _documento_hash from _documento on every flush, so any ORM-level
        # write to those columns is silently overwritten with the original
        # PII. A direct UPDATE avoids this and guarantees erasure.
        # Use per-client tombstone on documento_hash to preserve the
        # unique constraint (multiple clients can be anonymized).
        # Column name is ``documento`` in the table schema; the ORM attribute
        # ``_documento_numero`` maps to it (see mapping.py:92). Raw UPDATE
        # bypasses the ORM, so we must use the table column name here.
        stmt = (
            update(clientes_table)
            .where(clientes_table.c.id == cliente_id)
            .values(
                nome="ANONIMIZADO",
                contato="anonimizado@anonimizado.local",
                documento="ANONIMIZADO",
                documento_hash=f"ANONIMIZADO:{cliente_id}",
                ativo=False,
            )
        )
        self._session.execute(stmt)

        # #72: cascateia para os veiculos do cliente na MESMA transacao. A placa
        # e PII; o tombstone ``ANONIMIZADO:{veiculo_id}`` a neutraliza preservando
        # o UNIQUE (varios veiculos anonimizados). marca/modelo viram ANONIMIZADO.
        # O ``cliente_id`` e mantido -- aponta para o cliente ja anonimizado, nao
        # re-identifica -- e a FK ``ordens_de_servico.veiculo_id`` fica intacta,
        # preservando o historico de OS. Tombstone por-id via SELECT + UPDATE
        # (f-string, como no cliente) para nao depender de concat SQL (sqlite).
        veiculo_ids = (
            self._session.execute(
                select(veiculos_table.c.id).where(
                    veiculos_table.c.cliente_id == cliente_id
                )
            )
            .scalars()
            .all()
        )
        for veiculo_id in veiculo_ids:
            self._session.execute(
                update(veiculos_table)
                .where(veiculos_table.c.id == veiculo_id)
                .values(
                    placa=f"ANONIMIZADO:{veiculo_id}",
                    marca="ANONIMIZADO",
                    modelo="ANONIMIZADO",
                )
            )

        # Expire cached ORM state so subsequent reads reflect the change.
        cliente = self._session.get(Cliente, cliente_id)
        if cliente is not None:
            self._session.expire(cliente)

    def salvar_consentimento(self, consentimento: ConsentimentoCliente) -> None:
        self._session.add(consentimento)
        self._session.flush()

    def obter_consentimento(
        self, cliente_id: UUID, tipo: str
    ) -> ConsentimentoCliente | None:
        stmt = (
            select(ConsentimentoCliente)
            .where(consentimentos_table.c.cliente_id == cliente_id)
            .where(consentimentos_table.c.tipo == tipo)
            .order_by(consentimentos_table.c.concedido_em.desc())
        )
        return self._session.scalars(stmt).first()
