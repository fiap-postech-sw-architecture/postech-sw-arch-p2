"""Queries de leitura da aplicacao Ordem de Servico.

Os casos de uso de escrita (``use_cases.py``) so conhecem o agregado
``OrdemDeServico`` e os IDs cross-context que ele guarda. Para que a
camada HTTP consiga renderizar nomes de servicos, itens de estoque,
clientes e placas de veiculos sem expor essa leitura ao router (que
importaria agregados de contextos vizinhos), este modulo concentra
queries que orquestram as portas ``CatalogoPort`` / ``EstoquePort`` /
``ClientePort`` em batch.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from src.ordem_servico.aplicacao.dtos import (
        ItemDaOrdemDTO,
        OrdemDeServicoDTO,
        OrdemResumoDTO,
    )
    from src.ordem_servico.aplicacao.ports import (
        CatalogoPort,
        ClientePort,
        ClienteResumoDTO,
        EstoquePort,
        ItemEstoqueDTO,
        ServicoOferecidoDTO,
        VeiculoResumoDTO,
    )


class EnriquecerOrdemDeServico:
    """Query que enriquece projecoes de ordem com nomes resolvidos.

    Carrega, em consultas batch (servicos + estoque + clientes +
    veiculos), os campos cross-context que a UI precisa exibir mas
    que o agregado so guarda como IDs:

    - ``servico_nome`` / ``item_estoque_nome`` em cada item da ordem
      (so na variante completa ``executar``);
    - ``cliente_nome`` / ``veiculo_placa`` no header da ordem (em
      ambas as variantes single e lote).

    Devolve novos DTOs imutaveis com os campos preenchidos onde
    existirem; entidades nao encontradas (ex.: cliente removido)
    ficam com ``None`` para a UI escolher placeholder.

    Evita N+1 deduplicando IDs antes de cada lookup. Ordens sem
    itens ou listagens vazias suprimem a query correspondente.
    """

    def __init__(
        self,
        catalogo_port: CatalogoPort,
        estoque_port: EstoquePort,
        cliente_port: ClientePort,
    ) -> None:
        self._catalogo_port = catalogo_port
        self._estoque_port = estoque_port
        self._cliente_port = cliente_port

    def executar(self, ordem: OrdemDeServicoDTO) -> OrdemDeServicoDTO:
        """Retorna um novo DTO com nomes de servicos/itens/cliente/veiculo resolvidos.

        ``ordem`` permanece imutavel (frozen dataclass).
        """
        clientes_por_id = self._cliente_port.obter_clientes_em_lote({ordem.cliente_id})
        veiculos_por_id = self._cliente_port.obter_veiculos_em_lote({ordem.veiculo_id})

        if not ordem.itens:
            return replace(
                ordem,
                cliente_nome=_nome_cliente(clientes_por_id, ordem.cliente_id),
                veiculo_placa=_placa_veiculo(veiculos_por_id, ordem.veiculo_id),
            )

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
        return replace(
            ordem,
            itens=itens_enriquecidos,
            cliente_nome=_nome_cliente(clientes_por_id, ordem.cliente_id),
            veiculo_placa=_placa_veiculo(veiculos_por_id, ordem.veiculo_id),
        )

    def executar_lote(self, ordens: list[OrdemResumoDTO]) -> list[OrdemResumoDTO]:
        """Enriquece uma lista de resumos em batch (cliente + veiculo).

        Coleta todos os ``cliente_id`` e ``veiculo_id`` distintos e faz
        duas consultas (uma por porta) — independente de quantas ordens
        a pagina contenha. Lista vazia retorna nova lista vazia (nao
        repassa a referencia do input pra evitar mutacao acidental).
        """
        if not ordens:
            return []

        cliente_ids = {ordem.cliente_id for ordem in ordens}
        veiculo_ids = {ordem.veiculo_id for ordem in ordens}

        clientes_por_id = self._cliente_port.obter_clientes_em_lote(cliente_ids)
        veiculos_por_id = self._cliente_port.obter_veiculos_em_lote(veiculo_ids)

        return [
            replace(
                ordem,
                cliente_nome=_nome_cliente(clientes_por_id, ordem.cliente_id),
                veiculo_placa=_placa_veiculo(veiculos_por_id, ordem.veiculo_id),
            )
            for ordem in ordens
        ]

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


def _nome_cliente(
    clientes_por_id: dict[UUID, ClienteResumoDTO], cliente_id: UUID
) -> str | None:
    cliente = clientes_por_id.get(cliente_id)
    return cliente.nome if cliente is not None else None


def _placa_veiculo(
    veiculos_por_id: dict[UUID, VeiculoResumoDTO], veiculo_id: UUID
) -> str | None:
    veiculo = veiculos_por_id.get(veiculo_id)
    return veiculo.placa if veiculo is not None else None
