"""Portas de saida (Protocol) que a aplicacao OrdemDeServico consome.

Cada Protocol e definido aqui (no contexto consumidor) e implementado
em ``infraestrutura/`` do contexto provedor — padrao Anti-Corruption
Layer. PRs futuros (10/11) registrarao adapters concretos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.compartilhado.dominio.dinheiro import Dinheiro


@dataclass(frozen=True, slots=True)
class ServicoOferecidoDTO:
    """DTO imutavel devolvido por ``CatalogoPort.obter_servico``.

    Carrega apenas os campos que a aplicacao OrdemDeServico precisa
    para validar e snapshotar precos no orcamento.
    """

    id: UUID
    nome: str
    preco: Dinheiro
    ativo: bool


@dataclass(frozen=True, slots=True)
class ItemEstoqueDTO:
    """DTO imutavel devolvido por ``EstoquePort.obter_item``.

    Snapshot do preco da peca no momento da consulta — usado por
    ``AdicionarItem`` para registrar o preco da peca consumida (em vez
    do preco do servico, que seria pra mao-de-obra).
    """

    id: UUID
    nome: str
    preco_unitario: Dinheiro


class EstoquePort(Protocol):
    """Porta para reserva, liberacao e consulta de itens no contexto Estoque."""

    def reservar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Reserva ``quantidade`` unidades do item.

        Implementacoes devem levantar ``EstoqueInsuficienteException`` (ou
        equivalente) se a quantidade disponivel for menor que a solicitada.
        Nao e idempotente: chamadas repetidas reservam quantidades adicionais.
        """
        ...

    def liberar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Libera ``quantidade`` unidades previamente reservadas.

        Implementacoes devem rejeitar liberacoes que excedam a reserva
        ativa para o item.
        """
        ...

    def obter_item(self, item_estoque_id: UUID) -> ItemEstoqueDTO | None:
        """Retorna o DTO do item de estoque, ou ``None`` se nao existir.

        Usado por ``AdicionarItem`` quando a linha da OS representa uma peca
        consumida (item_estoque_id presente): o ``preco_unitario`` da
        ItemDaOrdem precisa vir do estoque, nao do servico.
        """
        ...


class CatalogoPort(Protocol):
    """Porta para consulta de servicos oferecidos no contexto Catalogo de Servicos."""

    def obter_servico(self, servico_id: UUID) -> ServicoOferecidoDTO | None:
        """Retorna o DTO do servico pelo id, ou ``None`` se nao existir."""
        ...


class ClientePort(Protocol):
    """Porta para checar existencia de cliente e veiculo no contexto Cliente+Veiculo."""

    def cliente_existe(self, cliente_id: UUID) -> bool:
        """Indica se o cliente existe e esta ativo no contexto Cliente+Veiculo."""
        ...

    def veiculo_existe(self, veiculo_id: UUID) -> bool:
        """Indica se o veiculo existe e esta ativo no contexto Cliente+Veiculo."""
        ...
