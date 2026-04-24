"""Seeder do catalogo de servicos via API. Requer ADMIN autenticado."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from full_test.client.errors import ConflitoError

if TYPE_CHECKING:
    from full_test.client import models
    from full_test.client.system_client import SystemClient


@dataclass(frozen=True, slots=True)
class ServicoSeed:
    nome: str
    descricao: str
    preco: Decimal


_PADRAO: tuple[ServicoSeed, ...] = (
    ServicoSeed(
        nome="Troca de oleo",
        descricao="Troca completa de oleo e filtro",
        preco=Decimal("149.90"),
    ),
    ServicoSeed(
        nome="Alinhamento",
        descricao="Alinhamento e balanceamento",
        preco=Decimal("89.90"),
    ),
    ServicoSeed(
        nome="Revisao basica",
        descricao="Revisao basica de 10 itens",
        preco=Decimal("299.00"),
    ),
    ServicoSeed(
        nome="Troca de pastilhas",
        descricao="Troca de pastilhas dianteiras",
        preco=Decimal("250.00"),
    ),
)


def servicos_padrao() -> tuple[ServicoSeed, ...]:
    return _PADRAO


def semear(client: SystemClient) -> list[models.ServicoResponse]:
    """Cria os servicos padrao; servicos com mesmo nome ja criados sao reutilizados.

    Observacao: nao ha endpoint de busca por nome, logo checamos via listagem.
    Idempotente: re-execucoes nao duplicam.
    """
    existentes = client.listar_servicos(limit=100).items
    por_nome = {s.nome: s for s in existentes}
    resultado: list[models.ServicoResponse] = []
    for seed in _PADRAO:
        if seed.nome in por_nome:
            resultado.append(por_nome[seed.nome])
            continue
        try:
            criado = client.criar_servico(
                nome=seed.nome, descricao=seed.descricao, preco=seed.preco
            )
            resultado.append(criado)
        except ConflitoError:
            atualizados = client.listar_servicos(limit=100).items
            match = next((s for s in atualizados if s.nome == seed.nome), None)
            if match is None:
                raise
            resultado.append(match)
    return resultado
