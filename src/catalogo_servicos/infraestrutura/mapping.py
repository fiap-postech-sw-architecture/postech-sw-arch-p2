from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Numeric,
    String,
    Table,
    Text,
    Uuid,
    event,
)
from sqlalchemy.orm import registry

from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.infraestrutura.database import metadata

servicos_oferecidos_table = Table(
    "servicos_oferecidos",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("nome", String(255), nullable=False),
    Column("descricao", Text, nullable=False),
    Column("preco_valor", Numeric(10, 2), nullable=False),
    Column("preco_moeda", String(3), nullable=False, default="BRL"),
    Column("ativo", Boolean, nullable=False, default=True),
)

_mapeamento_iniciado = False


def iniciar_mapeamentos() -> None:
    global _mapeamento_iniciado  # noqa: PLW0603  # init-once flag
    if _mapeamento_iniciado:
        return
    _mapeamento_iniciado = True

    mapper_registry = registry()

    mapper_registry.map_imperatively(
        ServicoOferecido,
        servicos_oferecidos_table,
        properties={
            "id": servicos_oferecidos_table.c.id,
            "_nome": servicos_oferecidos_table.c.nome,
            "_descricao": servicos_oferecidos_table.c.descricao,
            "_preco_valor": servicos_oferecidos_table.c.preco_valor,
            "_preco_moeda": servicos_oferecidos_table.c.preco_moeda,
            "_ativo": servicos_oferecidos_table.c.ativo,
        },
    )

    @event.listens_for(ServicoOferecido, "load")
    def _reconstruir_preco(target: ServicoOferecido, _context: object) -> None:
        valor = target._preco_valor  # type: ignore[attr-defined]
        moeda = target._preco_moeda  # type: ignore[attr-defined]
        object.__setattr__(target, "_preco", Dinheiro(valor=valor, moeda=moeda))
        # Preserva o guard de imutabilidade de id em instancias carregadas
        # (SQLAlchemy nao invoca __post_init__).
        object.__setattr__(target, "_id_atribuido", True)

    @event.listens_for(ServicoOferecido, "before_insert")
    @event.listens_for(ServicoOferecido, "before_update")
    def _decompor_preco(
        _mapper: object, _connection: object, target: ServicoOferecido
    ) -> None:
        preco = target.preco
        target._preco_valor = preco.valor
        target._preco_moeda = preco.moeda
