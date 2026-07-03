from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.compartilhado.dominio.dinheiro import Dinheiro


class TestServicoOferecido:
    def test_criacao_valida(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )
        assert s.nome == "Troca de oleo"
        assert s.descricao == "Troca completa"
        assert s.preco == preco
        assert s.ativo is True

    def test_nome_vazio_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        with pytest.raises(ValueError, match="Nome do servico"):
            ServicoOferecido(_nome="", _descricao="Desc", _preco=preco)

    def test_descricao_vazia_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        with pytest.raises(ValueError, match="Descricao do servico"):
            ServicoOferecido(_nome="Servico", _descricao="", _preco=preco)

    def test_atualizar(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )
        novo_preco = Dinheiro(valor=Decimal("150.00"))
        s.atualizar(nome="Revisao", descricao="Revisao geral", preco=novo_preco)
        assert s.nome == "Revisao"
        assert s.descricao == "Revisao geral"
        assert s.preco == novo_preco

    def test_desativar(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )
        s.desativar()
        assert s.ativo is False

    def test_identidade_por_id(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        id_fixo = uuid4()
        a = ServicoOferecido(id=id_fixo, _nome="A", _descricao="A", _preco=preco)
        b = ServicoOferecido(id=id_fixo, _nome="B", _descricao="B", _preco=preco)
        assert a == b

    def test_preco_dinheiro(self) -> None:
        preco = Dinheiro(valor=Decimal("99.99"))
        s = ServicoOferecido(
            _nome="Pintura", _descricao="Pintura completa", _preco=preco
        )
        assert s.preco.valor == Decimal("99.99")
        assert s.preco.moeda == "BRL"

    def test_preco_nao_pode_ser_nulo(self) -> None:
        s = ServicoOferecido(
            _nome="Pintura",
            _descricao="Pintura completa",
            _preco=Dinheiro(valor=Decimal("99.99")),
        )
        object.__setattr__(s, "_preco", None)

        with pytest.raises(ValueError, match="Preco do servico nao pode ser nulo"):
            _ = s.preco

    def test_atualizar_nome_vazio_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )
        novo_preco = Dinheiro(valor=Decimal("150.00"))
        with pytest.raises(ValueError, match="Nome do servico nao pode ser vazio"):
            s.atualizar(nome="", descricao="Nova descricao", preco=novo_preco)

    def test_atualizar_descricao_vazia_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )
        novo_preco = Dinheiro(valor=Decimal("150.00"))
        with pytest.raises(ValueError, match="Descricao do servico nao pode ser vazia"):
            s.atualizar(nome="Revisao", descricao="", preco=novo_preco)

    def test_preco_none_invalido(self) -> None:
        with pytest.raises(ValueError, match="Preco do servico e obrigatorio"):
            ServicoOferecido(
                _nome="Troca de oleo",
                _descricao="Troca completa",
                _preco=None,  # type: ignore[arg-type]
            )

    def test_atualizar_preco_none_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )
        with pytest.raises(ValueError, match="Preco do servico e obrigatorio"):
            s.atualizar(
                nome="Revisao",
                descricao="Revisao geral",
                preco=None,  # type: ignore[arg-type]
            )

    def test_identidade_distinta_para_ids_diferentes(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        a = ServicoOferecido(_nome="A", _descricao="A", _preco=preco)
        b = ServicoOferecido(_nome="A", _descricao="A", _preco=preco)
        assert a != b

    def test_desativar_idempotente(self) -> None:
        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )
        s.desativar()
        s.desativar()
        assert s.ativo is False

    def test_criar_emite_servico_cadastrado_event(self) -> None:
        from src.catalogo_servicos.dominio.events import ServicoCadastradoEvent

        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido.criar(
            nome="Troca de oleo", descricao="Troca completa", preco=preco
        )

        assert s.nome == "Troca de oleo"
        assert s.descricao == "Troca completa"
        assert s.preco == preco
        assert s.ativo is True
        eventos = s.coletar_eventos()
        assert [type(e) for e in eventos] == [ServicoCadastradoEvent]
        assert eventos[0].agregado_id == s.id

    def test_construtor_nao_emite_servico_cadastrado_event(self) -> None:
        # A emissao vive em `criar`, fora do construtor/__post_init__.
        # Construcao crua nao deve emitir ServicoCadastrado (a reconstituicao
        # via __new__ nem passa pelo construtor) — so o cadastro real, pela
        # factory.
        from src.catalogo_servicos.dominio.events import ServicoCadastradoEvent

        preco = Dinheiro(valor=Decimal("100.00"))
        s = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Troca completa", _preco=preco
        )

        tipos = [type(e) for e in s.coletar_eventos()]
        assert ServicoCadastradoEvent not in tipos
