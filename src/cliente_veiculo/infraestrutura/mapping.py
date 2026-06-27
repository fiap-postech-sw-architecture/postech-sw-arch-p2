from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Uuid,
    event,
)
from sqlalchemy.orm import registry, relationship

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.consentimento import ConsentimentoCliente
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.documento_anonimizado import DocumentoAnonimizado
from src.cliente_veiculo.dominio.placa import Placa
from src.cliente_veiculo.dominio.veiculo import Veiculo
from src.compartilhado.infraestrutura.database import metadata
from src.compartilhado.infraestrutura.encryption import EncryptionService

clientes_table = Table(
    "clientes",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("nome", String(255), nullable=False),
    Column("documento", String(255), nullable=False),
    Column("documento_hash", String(64), nullable=False, unique=True),
    Column("tipo_documento", String(4), nullable=False),
    Column("contato", String(255), nullable=False),
    Column("ativo", Boolean, nullable=False, default=True),
)

veiculos_table = Table(
    "veiculos",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("placa", String(7), nullable=False, unique=True),
    Column("marca", String(100), nullable=False),
    Column("modelo", String(100), nullable=False),
    Column("ano", Integer, nullable=False),
    Column("cliente_id", Uuid, ForeignKey("clientes.id"), nullable=False),
)

consentimentos_table = Table(
    "consentimentos",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "cliente_id",
        Uuid,
        ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("tipo", String(50), nullable=False),
    Column("concedido_em", DateTime(timezone=True), nullable=False),
    Column("revogado_em", DateTime(timezone=True), nullable=True),
)

_mapeamento_iniciado = False


def iniciar_mapeamentos() -> None:  # noqa: C901  # mapeamento declarativo coeso
    global _mapeamento_iniciado  # noqa: PLW0603  # init-once flag
    if _mapeamento_iniciado:
        return
    _mapeamento_iniciado = True  # codeql[py/unused-global-variable] -- lida na guarda

    mapper_registry = registry()

    mapper_registry.map_imperatively(
        Veiculo,
        veiculos_table,
        properties={
            "id": veiculos_table.c.id,
            "_placa_valor": veiculos_table.c.placa,
            "_marca": veiculos_table.c.marca,
            "_modelo": veiculos_table.c.modelo,
            "_ano": veiculos_table.c.ano,
        },
    )

    mapper_registry.map_imperatively(
        Cliente,
        clientes_table,
        properties={
            "id": clientes_table.c.id,
            "_nome": clientes_table.c.nome,
            "_documento_numero": clientes_table.c.documento,
            "_documento_hash": clientes_table.c.documento_hash,
            "_tipo_documento": clientes_table.c.tipo_documento,
            "_contato": clientes_table.c.contato,
            "_ativo": clientes_table.c.ativo,
            "_veiculos": relationship(
                Veiculo,
                lazy="selectin",
                cascade="all, delete-orphan",
            ),
        },
    )

    mapper_registry.map_imperatively(
        ConsentimentoCliente,
        consentimentos_table,
        properties={
            "id": consentimentos_table.c.id,
            "_cliente_id": consentimentos_table.c.cliente_id,
            "_tipo": consentimentos_table.c.tipo,
            "_concedido_em": consentimentos_table.c.concedido_em,
            "_revogado_em": consentimentos_table.c.revogado_em,
        },
    )

    @event.listens_for(Veiculo, "load")
    def _reconstruir_placa(target: Veiculo, _context: object) -> None:
        # object.__setattr__ for slots-safety and consistency with other listeners.
        object.__setattr__(target, "_placa", Placa(valor=target._placa_valor))  # type: ignore[attr-defined]
        object.__setattr__(target, "_id_atribuido", True)

    @event.listens_for(ConsentimentoCliente, "load")
    def _reconstruir_consentimento(
        target: ConsentimentoCliente, _context: object
    ) -> None:
        object.__setattr__(target, "_id_atribuido", True)

    def _reidratar_documento(target: Cliente) -> None:
        numero: str = target._documento_numero  # type: ignore[attr-defined]
        enc = EncryptionService.instance()
        if numero and numero.startswith("gAAAAA"):
            numero = enc.decrypt(numero)
        tipo: str = target._tipo_documento  # type: ignore[attr-defined]
        doc: CPF | CNPJ | DocumentoAnonimizado
        if numero == "ANONIMIZADO":
            # Tombstone escrito por ``ClienteRepository.anonimizar_dados``
            # (raw UPDATE bypassing event listeners). Reidrata como VO de
            # primeira classe — ``isinstance(doc, CPF/CNPJ)`` passa a ser
            # naturalmente False e nao precisamos burlar a validacao do CPF.
            doc = DocumentoAnonimizado(cliente_id=target.id)
        elif tipo == "cpf":
            doc = CPF(numero=numero)
        elif tipo == "cnpj":
            doc = CNPJ(numero=numero)
        else:
            msg = f"tipo_documento invalido ao reidratar Cliente: {tipo!r}"
            raise ValueError(msg)
        object.__setattr__(target, "_documento", doc)
        object.__setattr__(target, "_id_atribuido", True)
        object.__setattr__(target, "_eventos_pendentes", [])

    @event.listens_for(Cliente, "load")
    def _reconstruir_documento_on_load(target: Cliente, _context: object) -> None:
        _reidratar_documento(target)

    @event.listens_for(Cliente, "refresh")
    def _reconstruir_documento_on_refresh(
        target: Cliente, _context: object, _attrs: object
    ) -> None:
        # Necessario quando o mesmo session expira o cliente apos
        # ``anonimizar_dados`` (raw UPDATE) e re-le na mesma sessao —
        # o evento ``load`` so dispara no primeiro carregamento, entao
        # sem este listener o ``_documento`` em memoria fica defasado.
        _reidratar_documento(target)

    @event.listens_for(Veiculo, "before_insert")
    @event.listens_for(Veiculo, "before_update")
    def _decompor_placa(_mapper: object, _connection: object, target: Veiculo) -> None:
        target._placa_valor = target.placa.valor

    @event.listens_for(Cliente, "before_insert")
    @event.listens_for(Cliente, "before_update")
    def _decompor_documento(
        _mapper: object, _connection: object, target: Cliente
    ) -> None:
        doc = target.documento
        # Cliente anonimizado: as colunas ``documento`` e ``documento_hash``
        # ja foram preenchidas com tombstones unicos pelo raw UPDATE em
        # ``ClienteRepository.anonimizar_dados``. Recalcular aqui (encrypt +
        # hash_deterministic do sentinela) geraria o MESMO hash para todos
        # os clientes anonimizados e violaria o ``unique=True``. Sem-op
        # preserva o estado escrito pelo repository.
        if isinstance(doc, DocumentoAnonimizado):
            return
        enc = EncryptionService.instance()
        target._documento_numero = enc.encrypt(doc.numero)
        target._documento_hash = enc.hash_deterministic(doc.numero)
        if isinstance(doc, CPF):
            target._tipo_documento = "cpf"
        elif isinstance(doc, CNPJ):
            target._tipo_documento = "cnpj"
        else:
            msg = f"Tipo de documento nao suportado: {type(doc).__name__}"
            raise TypeError(msg)
