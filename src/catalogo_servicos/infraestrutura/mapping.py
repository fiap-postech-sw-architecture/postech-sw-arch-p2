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
    _mapeamento_iniciado = True  # codeql[py/unused-global-variable] -- lida na guarda

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
    @event.listens_for(ServicoOferecido, "refresh")
    def _reconstruir_preco(target: ServicoOferecido, *_args: object) -> None:
        # Decorators empilhados load+refresh (``*_args`` absorve o ``attrs`` que
        # o refresh passa a mais). O catalogo nao usa populate_existing hoje,
        # mas registrar ``refresh`` espelha estoque/cliente_veiculo e previne VO
        # stale caso um populate_existing/session.refresh surja no futuro — sem
        # o listener, o Dinheiro reidratado ficaria defasado apos a releitura.
        valor = target._preco_valor  # type: ignore[attr-defined]
        moeda = target._preco_moeda  # type: ignore[attr-defined]
        object.__setattr__(target, "_preco", Dinheiro(valor=valor, moeda=moeda))
        # __init__ nao roda no load (reconstituicao via __new__), entao o campo
        # init=False _eventos_pendentes nao existe na instancia. Semeia vazio
        # para paridade com cliente_veiculo/mapping.py e para a infraestrutura
        # que varre eventos pendentes (UoW/outbox) nao estourar AttributeError.
        # Hoje so a factory `criar` emite evento; mutacoes nao emitem.
        object.__setattr__(target, "_eventos_pendentes", [])

    @event.listens_for(ServicoOferecido, "before_insert")
    @event.listens_for(ServicoOferecido, "before_update")
    def _decompor_preco(
        _mapper: object, _connection: object, target: ServicoOferecido
    ) -> None:
        preco = target.preco
        target._preco_valor = preco.valor
        target._preco_moeda = preco.moeda
