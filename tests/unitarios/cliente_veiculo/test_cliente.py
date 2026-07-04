from __future__ import annotations

from uuid import uuid4

import pytest

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.exceptions import (
    PlacaDuplicadaException,
    VeiculoNaoEncontradoException,
)
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException

CPF_VALIDO = "21249722519"
CNPJ_VALIDO = "11222333000181"


class TestCliente:
    def test_criacao_com_cpf(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        assert cliente.nome == "Joao"
        assert cliente.documento == cpf
        assert cliente.contato == Contato(valor="11999999999")
        assert cliente.ativo is True
        assert cliente.veiculos == ()

    def test_criacao_sem_cpf(self) -> None:
        with pytest.raises(ValueError, match="Documento do cliente e obrigatorio"):
            Cliente(_nome="Joao", _contato=Contato(valor="11999999999"))

    def test_documento_nao_pode_ser_nulo(self) -> None:
        cliente = Cliente.__new__(Cliente)
        object.__setattr__(cliente, "_documento", None)

        with pytest.raises(ValueError, match="Documento do cliente nao pode ser nulo"):
            _ = cliente.documento

    def test_contato_nao_pode_ser_nulo(self) -> None:
        cliente = Cliente.__new__(Cliente)
        object.__setattr__(cliente, "_contato", None)

        with pytest.raises(ValueError, match="Contato do cliente nao pode ser nulo"):
            _ = cliente.contato

    def test_criacao_com_cnpj(self) -> None:
        cnpj = CNPJ(numero=CNPJ_VALIDO)
        cliente = Cliente(
            _nome="Oficina X", _documento=cnpj, _contato=Contato(valor="1133334444")
        )
        assert cliente.documento == cnpj

    def test_adicionar_veiculo(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        placa = Placa(valor="ABC1234")
        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        assert veiculo.placa == placa
        assert len(cliente.veiculos) == 1

    def test_adicionar_veiculo_placa_duplicada(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        with pytest.raises(PlacaDuplicadaException):
            cliente.adicionar_veiculo(placa, "VW", "Gol", 2021)

    def test_remover_veiculo(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        placa = Placa(valor="ABC1234")
        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        cliente.remover_veiculo(veiculo.id)
        assert len(cliente.veiculos) == 0

    def test_remover_veiculo_inexistente(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        with pytest.raises(VeiculoNaoEncontradoException):
            cliente.remover_veiculo(uuid4())

    def test_desativar(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        cliente.desativar()
        assert cliente.ativo is False

    def test_desativar_idempotente(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        cliente.desativar()
        eventos_apos_primeira = len(cliente.coletar_eventos())
        cliente.desativar()
        # Second call must be a no-op: no extra event is recorded.
        assert cliente.ativo is False
        assert len(cliente.coletar_eventos()) == eventos_apos_primeira

    def test_atualizar(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        cliente.atualizar(nome="Joao Silva", contato=Contato(valor="11888888888"))
        assert cliente.nome == "Joao Silva"
        assert cliente.contato == Contato(valor="11888888888")

    def _cliente_inativo(self) -> Cliente:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        cliente.desativar()
        return cliente

    def test_atualizar_cliente_inativo_rejeitado(self) -> None:
        # O invariante "inativo rejeita mutacao" vive no agregado: e a ultima
        # linha mesmo que a aplicacao pre-cheque para a mensagem 409.
        cliente = self._cliente_inativo()
        with pytest.raises(ViolacaoRegraDeNegocioException, match="cliente inativo"):
            cliente.atualizar(nome="Novo", contato=Contato(valor="11888888888"))

    def test_adicionar_veiculo_cliente_inativo_rejeitado(self) -> None:
        cliente = self._cliente_inativo()
        with pytest.raises(ViolacaoRegraDeNegocioException, match="cliente inativo"):
            cliente.adicionar_veiculo(Placa(valor="ABC1234"), "Fiat", "Uno", 2020)

    def test_remover_veiculo_cliente_inativo_rejeitado(self) -> None:
        # Brecha antiga: RemoverVeiculo nao tinha pre-check na aplicacao, entao
        # so o guard no agregado fecha a mutacao de cliente inativo.
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        veiculo = cliente.adicionar_veiculo(Placa(valor="ABC1234"), "Fiat", "Uno", 2020)
        cliente.desativar()
        with pytest.raises(ViolacaoRegraDeNegocioException, match="cliente inativo"):
            cliente.remover_veiculo(veiculo.id)

    def test_veiculos_retorna_tuple_imutavel(self) -> None:
        # Espelha OrdemDeServico.itens: a colecao exposta e um tuple, entao
        # nao ha copia mutavel que possa divergir do estado interno.
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        veiculos = cliente.veiculos
        assert isinstance(veiculos, tuple)
        assert not hasattr(veiculos, "clear")
        assert len(cliente.veiculos) == 1

    def test_identidade_por_id(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        id_fixo = uuid4()
        a = Cliente(
            id=id_fixo,
            _nome="Joao",
            _documento=cpf,
            _contato=Contato(valor="11999999999"),
        )
        b = Cliente(
            id=id_fixo,
            _nome="Maria",
            _documento=cpf,
            _contato=Contato(valor="11888888888"),
        )
        assert a == b

    def test_criacao_nome_vazio_invalido(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        with pytest.raises(ValueError, match="Nome do cliente nao pode ser vazio"):
            Cliente(_nome="", _documento=cpf, _contato=Contato(valor="11999999999"))

    def test_criacao_nome_whitespace_invalido(self) -> None:
        # Whitespace-only passava antes do strip() em __post_init__ (#168).
        cpf = CPF(numero=CPF_VALIDO)
        with pytest.raises(ValueError, match="Nome do cliente nao pode ser vazio"):
            Cliente(_nome="   ", _documento=cpf, _contato=Contato(valor="11999999999"))

    def test_criacao_nome_e_aparado(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="  Joao  ", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        assert cliente.nome == "Joao"

    def test_criacao_documento_none_invalido(self) -> None:
        with pytest.raises(ValueError, match="Documento do cliente e obrigatorio"):
            Cliente(
                _nome="Joao", _documento=None, _contato=Contato(valor="11999999999")
            )

    def test_atualizar_nome_vazio_invalido(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        with pytest.raises(ValueError, match="Nome do cliente nao pode ser vazio"):
            cliente.atualizar(nome="", contato=Contato(valor="11888888888"))

    def test_atualizar_nome_whitespace_invalido(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        with pytest.raises(ValueError, match="Nome do cliente nao pode ser vazio"):
            cliente.atualizar(nome=" \t ", contato=Contato(valor="11888888888"))

    def test_atualizar_nome_e_aparado(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        cliente.atualizar(nome="  Joao Silva  ", contato=Contato(valor="11888888888"))
        assert cliente.nome == "Joao Silva"

    def test_atualizar_sem_mudanca_nao_emite_evento(self) -> None:
        # Short-circuit: PUT idempotente com os mesmos valores nao gera
        # ClienteAtualizadoEvent (espelha a idempotencia de desativar).
        from src.cliente_veiculo.dominio.events import ClienteAtualizadoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        cliente.atualizar(nome="Joao", contato=Contato(valor="11999999999"))
        tipos = [type(e) for e in cliente.coletar_eventos()]
        assert ClienteAtualizadoEvent not in tipos
        assert cliente.nome == "Joao"

    def test_atualizar_contato_none_invalido(self) -> None:
        # Espelha o guard de __post_init__ (finding DDD-tatico da revisao de
        # entrega): sem o guard o agregado aceitava contato None em memoria e
        # o erro so aparecia no flush.
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        with pytest.raises(ValueError, match="Contato do cliente e obrigatorio"):
            cliente.atualizar(nome="Novo Nome", contato=None)  # type: ignore[arg-type]

    def test_eventos_emitidos_nas_transicoes_de_estado(self) -> None:
        from src.cliente_veiculo.dominio.events import (
            ClienteAtualizadoEvent,
            ClienteDesativadoEvent,
            VeiculoAdicionadoEvent,
            VeiculoRemovidoEvent,
        )

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        placa = Placa(valor="ABC1234")

        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        cliente.atualizar(nome="Joao Silva", contato=Contato(valor="11888888888"))
        cliente.remover_veiculo(veiculo.id)
        cliente.desativar()

        eventos = cliente.coletar_eventos()
        tipos = [type(e) for e in eventos]
        assert VeiculoAdicionadoEvent in tipos
        assert ClienteAtualizadoEvent in tipos
        assert VeiculoRemovidoEvent in tipos
        assert ClienteDesativadoEvent in tipos

    def test_veiculo_adicionado_event_payload_mascara_placa(self) -> None:
        # Placa e PII veicular (mesma politica de Placa.__repr__): o payload
        # do evento carrega o valor mascarado, nunca a placa crua.
        from src.cliente_veiculo.dominio.events import VeiculoAdicionadoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)

        evento = next(
            e
            for e in cliente.coletar_eventos()
            if isinstance(e, VeiculoAdicionadoEvent)
        )
        assert evento.placa_valor == placa.mascarado()
        assert "ABC1234" not in evento.placa_valor
        assert evento.marca == "Fiat"
        assert evento.modelo == "Uno"
        assert evento.ano == 2020

    def test_veiculo_removido_event_payload_mascara_placa(self) -> None:
        from src.cliente_veiculo.dominio.events import VeiculoRemovidoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        placa = Placa(valor="ABC1234")
        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        cliente.remover_veiculo(veiculo.id)

        evento = next(
            e for e in cliente.coletar_eventos() if isinstance(e, VeiculoRemovidoEvent)
        )
        assert evento.placa_valor == placa.mascarado()
        assert "ABC1234" not in evento.placa_valor

    def test_cliente_atualizado_event_nao_carrega_pii(self) -> None:
        from src.cliente_veiculo.dominio.events import ClienteAtualizadoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )
        cliente.atualizar(nome="Joao Silva", contato=Contato(valor="11888888888"))

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
            _contato=Contato(valor="11999999999"),
        )
        representacao = repr(cliente)
        assert "Joao" not in representacao
        assert "11999999999" not in representacao

    def test_criar_emite_cliente_cadastrado_event(self) -> None:
        from src.cliente_veiculo.dominio.events import ClienteCadastradoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente.criar(
            nome="Joao", documento=cpf, contato=Contato(valor="11999999999")
        )

        assert cliente.nome == "Joao"
        assert cliente.documento == cpf
        assert cliente.contato == Contato(valor="11999999999")
        assert cliente.ativo is True
        eventos = cliente.coletar_eventos()
        assert [type(e) for e in eventos] == [ClienteCadastradoEvent]
        assert eventos[0].agregado_id == cliente.id

    def test_construtor_nao_emite_cliente_cadastrado_event(self) -> None:
        # A emissao vive em `criar`, fora do construtor/__post_init__.
        # Construcao crua nao deve emitir ClienteCadastrado (nem a
        # reconstituicao via __new__ do SQLAlchemy, que nem passa pelo
        # construtor) — so o cadastro real, pela factory.
        from src.cliente_veiculo.dominio.events import ClienteCadastradoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(
            _nome="Joao", _documento=cpf, _contato=Contato(valor="11999999999")
        )

        tipos = [type(e) for e in cliente.coletar_eventos()]
        assert ClienteCadastradoEvent not in tipos

    def test_cliente_cadastrado_event_nao_carrega_pii(self) -> None:
        from src.cliente_veiculo.dominio.events import ClienteCadastradoEvent

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente.criar(
            nome="Joao", documento=cpf, contato=Contato(valor="11999999999")
        )

        evento = next(
            e
            for e in cliente.coletar_eventos()
            if isinstance(e, ClienteCadastradoEvent)
        )
        # Evento de criacao carrega so agregado_id/ocorrido_em (herdados),
        # nunca PII como nome ou contato.
        assert not hasattr(evento, "nome")
        assert not hasattr(evento, "contato")
