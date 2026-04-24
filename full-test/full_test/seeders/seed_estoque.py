"""Seeder de itens de estoque via API. Requer ADMIN autenticado.

Quantidades iniciais sao deliberadamente altas (>= 100) para que o orchestrator
possa rodar muitas ordens em paralelo sem esgotar o estoque base, mas
pequenas o suficiente para que o teste de concorrencia de ajustes (step 8)
ainda exercite caminhos de borda. A journey de step 8 que testa depleção cria
seus proprios itens com quantidade baixa.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from full_test.client import models
    from full_test.client.system_client import SystemClient


@dataclass(frozen=True, slots=True)
class ItemEstoqueSeed:
    nome: str
    descricao: str
    quantidade: int
    preco_unitario: Decimal


_PADRAO: tuple[ItemEstoqueSeed, ...] = (
    ItemEstoqueSeed(
        nome="Oleo 10W40 1L",
        descricao="Oleo mineral 1L",
        quantidade=200,
        preco_unitario=Decimal("35.00"),
    ),
    ItemEstoqueSeed(
        nome="Filtro de oleo",
        descricao="Filtro padrao",
        quantidade=150,
        preco_unitario=Decimal("45.00"),
    ),
    ItemEstoqueSeed(
        nome="Pastilha de freio dianteira",
        descricao="Par",
        quantidade=80,
        preco_unitario=Decimal("180.00"),
    ),
    ItemEstoqueSeed(
        nome="Vela de ignicao",
        descricao="Un",
        quantidade=300,
        preco_unitario=Decimal("28.00"),
    ),
)


def itens_padrao() -> tuple[ItemEstoqueSeed, ...]:
    return _PADRAO


def semear(client: SystemClient) -> list[models.ItemEstoqueResponse]:
    existentes = client.listar_itens_estoque(limit=100).items
    por_nome = {i.nome: i for i in existentes}
    resultado: list[models.ItemEstoqueResponse] = []
    for seed in _PADRAO:
        if seed.nome in por_nome:
            item = por_nome[seed.nome]
            if item.quantidade < seed.quantidade:
                item = client.ajustar_quantidade_estoque(
                    item.id, nova_quantidade=seed.quantidade
                )
            resultado.append(item)
            continue
        criado = client.criar_item_estoque(
            nome=seed.nome,
            descricao=seed.descricao,
            quantidade=seed.quantidade,
            preco_unitario=seed.preco_unitario,
        )
        resultado.append(criado)
    return resultado
