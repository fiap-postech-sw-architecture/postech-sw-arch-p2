"""Queries de leitura da aplicacao Ordem de Servico.

Os casos de uso de escrita (``use_cases.py``) so conhecem o agregado
``OrdemDeServico`` e os IDs cross-context que ele guarda. Para que a
camada HTTP consiga renderizar nomes de servicos e itens de estoque
sem expor essa leitura ao router (que importaria agregados de
contextos vizinhos), este modulo concentra queries que orquestram as
portas ``CatalogoPort`` / ``EstoquePort`` em batch.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from src.ordem_servico.aplicacao.dtos import (
        ItemDaOrdemDTO,
        OrdemDeServicoDTO,
    )
    from src.ordem_servico.aplicacao.ports import (
        CatalogoPort,
        EstoquePort,
        ItemEstoqueDTO,
        ServicoOferecidoDTO,
    )


class EnriquecerOrdemDeServico:
    """Query que enriquece uma ``OrdemDeServicoDTO`` com nomes resolvidos.

    Carrega, em duas consultas batch (servicos + estoque), os nomes do
    catalogo e do estoque correspondentes aos IDs presentes nos itens
    da ordem. Devolve um novo DTO imutavel com ``servico_nome`` e
    ``item_estoque_nome`` preenchidos onde existirem; itens nao
    encontrados ficam com ``None`` para a UI escolher placeholder.

    Evita N+1 deduplicando IDs antes do lookup. Ordens sem itens, ou
    sem itens com ``item_estoque_id``, suprimem a query correspondente.
    """

    def __init__(self, catalogo_port: CatalogoPort, estoque_port: EstoquePort) -> None:
        self._catalogo_port = catalogo_port
        self._estoque_port = estoque_port

    def executar(self, ordem: OrdemDeServicoDTO) -> OrdemDeServicoDTO:
        """Retorna um novo DTO com os nomes resolvidos via portas.

        ``ordem`` permanece imutavel (frozen dataclass). Se a ordem nao
        tem itens, o objeto original e devolvido sem novo lookup.
        """
        if not ordem.itens:
            return ordem

        servico_ids = {item.servico_catalogo_id for item in ordem.itens}
        estoque_ids = {
            item.item_estoque_id
            for item in ordem.itens
            if item.item_estoque_id is not None
        }

        servicos_por_id = self._catalogo_port.obter_servicos_em_lote(servico_ids)
        itens_estoque_por_id = self._estoque_port.obter_itens_em_lote(estoque_ids)

        itens_enriquecidos = [
            self._enriquecer_item(item, servicos_por_id, itens_estoque_por_id)
            for item in ordem.itens
        ]
        return replace(ordem, itens=itens_enriquecidos)

    @staticmethod
    def _enriquecer_item(
        item: ItemDaOrdemDTO,
        servicos_por_id: dict[UUID, ServicoOferecidoDTO],
        itens_estoque_por_id: dict[UUID, ItemEstoqueDTO],
    ) -> ItemDaOrdemDTO:
        servico = servicos_por_id.get(item.servico_catalogo_id)
        item_estoque = (
            itens_estoque_por_id.get(item.item_estoque_id)
            if item.item_estoque_id is not None
            else None
        )
        return replace(
            item,
            servico_nome=servico.nome if servico is not None else None,
            item_estoque_nome=(item_estoque.nome if item_estoque is not None else None),
        )
