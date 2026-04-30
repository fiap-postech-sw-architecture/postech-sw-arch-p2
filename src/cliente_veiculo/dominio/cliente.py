from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.cliente_veiculo.dominio.events import (
    ClienteAtualizadoEvent,
    ClienteDesativadoEvent,
    VeiculoAdicionadoEvent,
    VeiculoRemovidoEvent,
)
from src.cliente_veiculo.dominio.exceptions import (
    PlacaDuplicadaException,
    VeiculoNaoEncontradoException,
)
from src.compartilhado.dominio.aggregate_root import AggregateRoot

if TYPE_CHECKING:
    from uuid import UUID

    from src.cliente_veiculo.dominio.documento import Documento
    from src.cliente_veiculo.dominio.placa import Placa
    from src.cliente_veiculo.dominio.veiculo import Veiculo


@dataclass(eq=False)
class Cliente(AggregateRoot):
    """Agregado Cliente (raiz do contexto Cliente+Veiculo).

    Encapsula dados de cadastro (nome, documento, contato), a colecao de
    veiculos e o flag `_ativo`. Invariantes:
    - `nome` nunca vazio.
    - `documento` obrigatorio (CPF ou CNPJ valido).
    - placa unica por cliente (duplicacao levanta `PlacaDuplicadaException`).
    - remocao de veiculo inexistente levanta `VeiculoNaoEncontradoException`.

    Cada metodo de transicao de estado registra um `DomainEvent` no aggregate
    via `_registrar_evento`; os eventos ficam armazenados ate serem coletados
    e publicados pelo UoW apos o commit.
    """

    # Sentinels para permitir `Cliente(_nome=..., _documento=...)` como kwargs:
    # o runtime guard em __post_init__ rejeita vazios/None antes que o objeto
    # escape da construcao. `_nome` e `_contato` usam `repr=False` para nao
    # vazar PII pelo `__repr__` gerado automaticamente pelo dataclass.
    _nome: str = field(default="", repr=False)
    _documento: Documento | None = None  # validated in __post_init__
    _contato: str = field(default="", repr=False)
    _veiculos: list[Veiculo] = field(default_factory=list, repr=False)
    _ativo: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self._nome:
            msg = "Nome do cliente nao pode ser vazio"
            raise ValueError(msg)
        if self._documento is None:
            msg = "Documento do cliente e obrigatorio"
            raise ValueError(msg)

    @property
    def nome(self) -> str:
        return self._nome

    @property
    def documento(self) -> Documento:
        if self._documento is None:
            msg = "Documento do cliente nao pode ser nulo"
            raise ValueError(msg)
        return self._documento

    @property
    def contato(self) -> str:
        return self._contato

    @property
    def veiculos(self) -> list[Veiculo]:
        """Retorna uma copia defensiva da lista de veiculos do cliente."""
        return list(self._veiculos)

    @property
    def ativo(self) -> bool:
        return self._ativo

    def adicionar_veiculo(
        self, placa: Placa, marca: str, modelo: str, ano: int
    ) -> Veiculo:
        """Cria e adiciona um Veiculo ao cliente, rejeitando placas duplicadas."""
        from src.cliente_veiculo.dominio.veiculo import Veiculo as _Veiculo

        if any(v.placa == placa for v in self._veiculos):
            raise PlacaDuplicadaException()
        veiculo = _Veiculo(_placa=placa, _marca=marca, _modelo=modelo, _ano=ano)
        self._veiculos.append(veiculo)
        self._registrar_evento(
            VeiculoAdicionadoEvent(
                agregado_id=self.id,
                placa_valor=placa.valor,
                marca=marca,
                modelo=modelo,
                ano=ano,
            )
        )
        return veiculo

    def remover_veiculo(self, veiculo_id: UUID) -> None:
        """Remove o veiculo identificado por `veiculo_id`; levanta se nao existir."""
        for i, v in enumerate(self._veiculos):
            if v.id == veiculo_id:
                placa_removida = v.placa.valor
                self._veiculos.pop(i)
                self._registrar_evento(
                    VeiculoRemovidoEvent(
                        agregado_id=self.id,
                        placa_valor=placa_removida,
                    )
                )
                return
        raise VeiculoNaoEncontradoException()

    def desativar(self) -> None:
        """Soft-delete: marca o cliente como inativo e emite evento."""
        if not self._ativo:
            return
        self._ativo = False
        self._registrar_evento(ClienteDesativadoEvent(agregado_id=self.id))

    def atualizar(self, nome: str, contato: str) -> None:
        """Atualiza nome e contato do cliente. Nome vazio e rejeitado."""
        if not nome:
            msg = "Nome do cliente nao pode ser vazio"
            raise ValueError(msg)
        self._nome = nome
        self._contato = contato
        self._registrar_evento(ClienteAtualizadoEvent(agregado_id=self.id))
