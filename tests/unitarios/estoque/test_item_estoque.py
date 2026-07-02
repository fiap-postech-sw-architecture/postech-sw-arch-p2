from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import (
    EstoqueInsuficienteException,
    ViolacaoRegraDeNegocioException,
)
from src.estoque.dominio.events import (
    EstoqueLiberadoEvent,
    EstoqueReservadoEvent,
)
from src.estoque.dominio.item_estoque import ItemEstoque


def _criar_item(quantidade: int = 10) -> ItemEstoque:
    preco = Dinheiro(valor=Decimal("50.00"))
    return ItemEstoque(
        _nome="Filtro de oleo",
        _descricao="Filtro para motor",
        _quantidade=quantidade,
        _preco_unitario=preco,
    )


class TestItemEstoque:
    def test_criacao_valida(self) -> None:
        item = _criar_item()
        assert item.nome == "Filtro de oleo"
        assert item.descricao == "Filtro para motor"
        assert item.quantidade == 10
        assert item.preco_unitario.valor == Decimal("50.00")
        assert item.ativo is True

    def test_nome_vazio_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Nome do item"):
            ItemEstoque(
                _nome="", _descricao="Desc", _quantidade=10, _preco_unitario=preco
            )

    def test_quantidade_negativa_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Quantidade nao pode ser negativa"):
            ItemEstoque(
                _nome="Item", _descricao="Desc", _quantidade=-1, _preco_unitario=preco
            )

    def test_reservar_sucesso(self) -> None:
        item = _criar_item(quantidade=10)
        item.reservar(3)
        assert item.quantidade == 7

    def test_reservar_evento_registrado(self) -> None:
        item = _criar_item(quantidade=10)
        item.reservar(3)
        eventos = item.coletar_eventos()
        assert len(eventos) == 1
        evento = eventos[0]
        assert isinstance(evento, EstoqueReservadoEvent)
        assert evento.quantidade_reservada == 3
        assert evento.quantidade_restante == 7
        assert evento.agregado_id == item.id

    def test_reservar_estoque_insuficiente(self) -> None:
        item = _criar_item(quantidade=5)
        with pytest.raises(
            EstoqueInsuficienteException, match=r"disponivel=5.*solicitado=10"
        ):
            item.reservar(10)
        assert item.quantidade == 5

    def test_reservar_um_acima_do_disponivel(self) -> None:
        item = _criar_item(quantidade=5)
        with pytest.raises(EstoqueInsuficienteException):
            item.reservar(6)

    def test_reservar_quantidade_exata(self) -> None:
        item = _criar_item(quantidade=5)
        item.reservar(5)
        assert item.quantidade == 0

    def test_reservar_zero_invalido(self) -> None:
        item = _criar_item()
        with pytest.raises(ValueError, match="Quantidade para reserva"):
            item.reservar(0)

    def test_reservar_item_inativo_rejeitado(self) -> None:
        # Issue #120: defesa em profundidade — item desativado nunca reserva,
        # mesmo que a validacao de aplicacao (_montar_item) seja contornada.
        item = ItemEstoque(
            _nome="Filtro",
            _descricao="Descontinuado",
            _quantidade=10,
            _preco_unitario=Dinheiro(valor=Decimal("50.00")),
            _ativo=False,
        )
        with pytest.raises(ViolacaoRegraDeNegocioException, match="inativo"):
            item.reservar(3)
        assert item.quantidade == 10  # saldo intacto

    def test_liberar_sucesso(self) -> None:
        item = _criar_item(quantidade=5)
        item.liberar(3)
        assert item.quantidade == 8

    def test_liberar_evento_registrado(self) -> None:
        item = _criar_item(quantidade=5)
        item.liberar(3)
        eventos = item.coletar_eventos()
        assert len(eventos) == 1
        evento = eventos[0]
        assert isinstance(evento, EstoqueLiberadoEvent)
        assert evento.quantidade_liberada == 3
        assert evento.quantidade_atual == 8
        assert evento.agregado_id == item.id

    def test_liberar_zero_invalido(self) -> None:
        item = _criar_item()
        with pytest.raises(ValueError, match="Quantidade para liberacao"):
            item.liberar(0)

    def test_atualizar(self) -> None:
        item = _criar_item()
        novo_preco = Dinheiro(valor=Decimal("75.00"))
        item.atualizar(
            nome="Filtro premium", descricao="Filtro premium", preco_unitario=novo_preco
        )
        assert item.nome == "Filtro premium"
        assert item.preco_unitario == novo_preco

    def test_preco_unitario_nao_pode_ser_nulo(self) -> None:
        item = _criar_item()
        object.__setattr__(item, "_preco_unitario", None)

        with pytest.raises(
            ValueError, match="Preco unitario do item nao pode ser nulo"
        ):
            _ = item.preco_unitario

    def test_ajustar_quantidade(self) -> None:
        item = _criar_item(quantidade=10)
        item.ajustar_quantidade(20)
        assert item.quantidade == 20

    def test_ajustar_quantidade_zero_permitido(self) -> None:
        item = _criar_item(quantidade=10)
        item.ajustar_quantidade(0)
        assert item.quantidade == 0

    def test_ajustar_quantidade_negativa_invalida(self) -> None:
        item = _criar_item()
        with pytest.raises(ValueError, match="Quantidade nao pode ser negativa"):
            item.ajustar_quantidade(-1)

    def test_desativar(self) -> None:
        item = _criar_item()
        item.desativar()
        assert item.ativo is False

    def test_limpar_eventos(self) -> None:
        item = _criar_item()
        item.reservar(1)
        item.limpar_eventos()
        assert item.coletar_eventos() == []

    def test_identidade_por_id(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        id_fixo = uuid4()
        a = ItemEstoque(
            id=id_fixo, _nome="A", _descricao="A", _quantidade=1, _preco_unitario=preco
        )
        b = ItemEstoque(
            id=id_fixo, _nome="B", _descricao="B", _quantidade=2, _preco_unitario=preco
        )
        assert a == b

    def test_atualizar_nome_vazio_invalido(self) -> None:
        item = _criar_item()
        novo_preco = Dinheiro(valor=Decimal("75.00"))
        with pytest.raises(ValueError, match="Nome do item nao pode ser vazio"):
            item.atualizar(nome="", descricao="Desc", preco_unitario=novo_preco)

    def test_construcao_sem_preco_invalida(self) -> None:
        with pytest.raises(ValueError, match="Preco unitario do item e obrigatorio"):
            ItemEstoque(
                _nome="Item",
                _descricao="Desc",
                _quantidade=1,
                _preco_unitario=None,  # type: ignore[arg-type]
            )

    def test_atualizar_preco_none_invalido(self) -> None:
        item = _criar_item()
        with pytest.raises(ValueError, match="Preco unitario do item e obrigatorio"):
            item.atualizar(
                nome="Novo",
                descricao="Nova desc",
                preco_unitario=None,  # type: ignore[arg-type]
            )

    def test_reservar_negativo_invalido(self) -> None:
        item = _criar_item()
        with pytest.raises(ValueError, match="Quantidade para reserva"):
            item.reservar(-1)

    def test_liberar_negativo_invalido(self) -> None:
        item = _criar_item()
        with pytest.raises(ValueError, match="Quantidade para liberacao"):
            item.liberar(-1)

    def test_ativar(self) -> None:
        item = _criar_item()
        item.desativar()
        item.ativar()
        assert item.ativo is True

    def test_desativar_idempotente(self) -> None:
        item = _criar_item()
        item.desativar()
        item.desativar()
        assert item.ativo is False

    def test_ativar_idempotente(self) -> None:
        item = _criar_item()
        item.ativar()
        item.ativar()
        assert item.ativo is True

    def test_identidade_distinta_para_ids_diferentes(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        a = ItemEstoque(_nome="A", _descricao="A", _quantidade=1, _preco_unitario=preco)
        b = ItemEstoque(_nome="A", _descricao="A", _quantidade=1, _preco_unitario=preco)
        assert a != b
