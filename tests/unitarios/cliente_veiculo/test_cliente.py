from __future__ import annotations

from uuid import uuid4

import pytest

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.exceptions import (
    PlacaDuplicadaException,
    VeiculoNaoEncontradoException,
)
from src.cliente_veiculo.dominio.placa import Placa

CPF_VALIDO = "21249722519"
CNPJ_VALIDO = "11222333000181"


class TestCliente:
    def test_criacao_com_cpf(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        assert cliente.nome == "Joao"
        assert cliente.documento == cpf
        assert cliente.contato == "11999999999"
        assert cliente.ativo is True
        assert cliente.veiculos == []

    def test_criacao_sem_cpf(self) -> None:
        with pytest.raises(ValueError, match="Documento do cliente e obrigatorio"):
            Cliente(_nome="Joao", _contato="11999999999")

    def test_documento_nao_pode_ser_nulo(self) -> None:
        cliente = Cliente.__new__(Cliente)
        object.__setattr__(cliente, "_documento", None)

        with pytest.raises(ValueError, match="Documento do cliente nao pode ser nulo"):
            _ = cliente.documento

    def test_criacao_com_cnpj(self) -> None:
        cnpj = CNPJ(numero=CNPJ_VALIDO)
        cliente = Cliente(_nome="Oficina X", _documento=cnpj, _contato="1133334444")
        assert cliente.documento == cnpj

    def test_adicionar_veiculo(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        placa = Placa(valor="ABC1234")
        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        assert veiculo.placa == placa
        assert len(cliente.veiculos) == 1

    def test_adicionar_veiculo_placa_duplicada(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        with pytest.raises(PlacaDuplicadaException):
            cliente.adicionar_veiculo(placa, "VW", "Gol", 2021)

    def test_remover_veiculo(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        placa = Placa(valor="ABC1234")
        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        cliente.remover_veiculo(veiculo.id)
        assert len(cliente.veiculos) == 0

    def test_remover_veiculo_inexistente(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        with pytest.raises(VeiculoNaoEncontradoException):
            cliente.remover_veiculo(uuid4())

    def test_desativar(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        cliente.desativar()
        assert cliente.ativo is False

    def test_desativar_idempotente(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        cliente.desativar()
        eventos_apos_primeira = len(cliente.coletar_eventos())
        cliente.desativar()
        # Second call must be a no-op: no extra event is recorded.
        assert cliente.ativo is False
        assert len(cliente.coletar_eventos()) == eventos_apos_primeira

    def test_atualizar(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        cliente.atualizar(nome="Joao Silva", contato="11888888888")
        assert cliente.nome == "Joao Silva"
        assert cliente.contato == "11888888888"

    def test_veiculos_retorna_copia(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        veiculos = cliente.veiculos
        veiculos.clear()
        assert len(cliente.veiculos) == 1

    def test_identidade_por_id(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        id_fixo = uuid4()
        a = Cliente(id=id_fixo, _nome="Joao", _documento=cpf, _contato="11999999999")
        b = Cliente(id=id_fixo, _nome="Maria", _documento=cpf, _contato="11888888888")
        assert a == b

    def test_criacao_nome_vazio_invalido(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        with pytest.raises(ValueError, match="Nome do cliente nao pode ser vazio"):
            Cliente(_nome="", _documento=cpf, _contato="11999999999")

    def test_criacao_documento_none_invalido(self) -> None:
        with pytest.raises(ValueError, match="Documento do cliente e obrigatorio"):
            Cliente(_nome="Joao", _documento=None, _contato="11999999999")

    def test_atualizar_nome_vazio_invalido(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        with pytest.raises(ValueError, match="Nome do cliente nao pode ser vazio"):
            cliente.atualizar(nome="", contato="11888888888")

    def test_eventos_emitidos_nas_transicoes_de_estado(self) -> None:
        from src.cliente_veiculo.dominio.events import (
            ClienteAtualizadoEvent,
            ClienteDesativadoEvent,
            VeiculoAdicionadoEvent,
            VeiculoRemovidoEvent,
        )

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        placa = Placa(valor="ABC1234")

        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        cliente.atualizar(nome="Joao Silva", contato="11888888888")
        cliente.remover_veiculo(veiculo.id)
        cliente.desativar()

        eventos = cliente.coletar_eventos()
        tipos = [type(e) for e in eventos]
        assert VeiculoAdicionadoEvent in tipos
        assert ClienteAtualizadoEvent in tipos
        assert VeiculoRemovidoEvent in tipos
        assert ClienteDesativadoEvent in tipos

    def test_veiculo_adicionado_event_payload_obrigatorio(self) -> None:
        from src.cliente_veiculo.dominio.events import VeiculoAdicionadoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)

        evento = next(
            e
            for e in cliente.coletar_eventos()
            if isinstance(e, VeiculoAdicionadoEvent)
        )
        assert evento.placa_valor == "ABC1234"
        assert evento.marca == "Fiat"
        assert evento.modelo == "Uno"
        assert evento.ano == 2020

    def test_cliente_atualizado_event_nao_carrega_pii(self) -> None:
        from src.cliente_veiculo.dominio.events import ClienteAtualizadoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999999999")
        cliente.atualizar(nome="Joao Silva", contato="11888888888")

        evento = next(
            e
            for e in cliente.coletar_eventos()
            if isinstance(e, ClienteAtualizadoEvent)
        )
        # O evento deve conter apenas agregado_id/ocorrido_em (herdados),
        # nenhum campo de PII como nome ou contato.
        assert not hasattr(evento, "nome")
        assert not hasattr(evento, "contato")

    def test_repr_nao_vaza_nome_nem_contato(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao Silva",
            _documento=cpf,
            _contato="11999999999",
        )
        representacao = repr(cliente)
        assert "Joao" not in representacao
        assert "11999999999" not in representacao
