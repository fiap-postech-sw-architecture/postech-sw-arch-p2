from __future__ import annotations

import pytest

from src.compartilhado.dominio.exceptions import (
    DomainException,
    EntidadeDuplicadaException,
    EntidadeNaoEncontradaException,
    EstoqueInsuficienteException,
    FalhaAutenticacaoException,
    TransicaoStatusInvalidaException,
    ViolacaoRegraDeNegocioException,
)


class TestDomainException:
    def test_codigo_e_mensagem(self) -> None:
        exc = DomainException(codigo="TESTE", mensagem="mensagem teste")
        assert exc.codigo == "TESTE"
        assert exc.mensagem == "mensagem teste"
        assert str(exc) == "mensagem teste"

    def test_herda_de_exception(self) -> None:
        exc = DomainException(codigo="TESTE", mensagem="teste")
        assert isinstance(exc, Exception)


class TestExceptionsEspecificas:
    @pytest.mark.parametrize(
        ("classe", "codigo_esperado", "mensagem_padrao"),
        [
            (
                EntidadeNaoEncontradaException,
                "ENTIDADE_NAO_ENCONTRADA",
                "Entidade nao encontrada",
            ),
            (
                ViolacaoRegraDeNegocioException,
                "VIOLACAO_REGRA_NEGOCIO",
                "Violacao de regra de negocio",
            ),
            (
                TransicaoStatusInvalidaException,
                "TRANSICAO_STATUS_INVALIDA",
                "Transicao de status invalida",
            ),
            (
                EstoqueInsuficienteException,
                "ESTOQUE_INSUFICIENTE",
                "Estoque insuficiente",
            ),
            (
                EntidadeDuplicadaException,
                "ENTIDADE_DUPLICADA",
                "Entidade duplicada",
            ),
            (
                FalhaAutenticacaoException,
                "FALHA_AUTENTICACAO",
                "Falha na autenticacao",
            ),
        ],
    )
    def test_excecao_com_padrao(
        self,
        classe: type[DomainException],
        codigo_esperado: str,
        mensagem_padrao: str,
    ) -> None:
        exc = classe()
        assert exc.codigo == codigo_esperado
        assert exc.mensagem == mensagem_padrao
        assert isinstance(exc, DomainException)

    @pytest.mark.parametrize(
        "classe",
        [
            EntidadeNaoEncontradaException,
            ViolacaoRegraDeNegocioException,
            TransicaoStatusInvalidaException,
            EstoqueInsuficienteException,
            EntidadeDuplicadaException,
            FalhaAutenticacaoException,
        ],
    )
    def test_excecao_com_mensagem_customizada(
        self,
        classe: type[DomainException],
    ) -> None:
        exc = classe(mensagem="mensagem customizada")
        assert exc.mensagem == "mensagem customizada"

    @pytest.mark.parametrize(
        "classe",
        [
            EntidadeNaoEncontradaException,
            ViolacaoRegraDeNegocioException,
            TransicaoStatusInvalidaException,
            EstoqueInsuficienteException,
            EntidadeDuplicadaException,
            FalhaAutenticacaoException,
        ],
    )
    def test_excecao_pode_ser_levantada(
        self,
        classe: type[DomainException],
    ) -> None:
        with pytest.raises(classe):
            raise classe()
