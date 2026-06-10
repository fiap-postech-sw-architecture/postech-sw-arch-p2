from __future__ import annotations

from src.cliente_veiculo.dominio.exceptions import (
    ClienteNaoEncontradoException,
    DocumentoDuplicadoException,
    PlacaDuplicadaException,
    VeiculoNaoEncontradoException,
)
from src.compartilhado.dominio.exceptions import (
    EntidadeDuplicadaException,
    EntidadeNaoEncontradaException,
)


class TestClienteVeiculoExceptions:
    def test_cliente_nao_encontrado_default(self) -> None:
        exc = ClienteNaoEncontradoException()
        assert isinstance(exc, EntidadeNaoEncontradaException)
        assert "Cliente" in exc.mensagem

    def test_cliente_nao_encontrado_mensagem_custom(self) -> None:
        exc = ClienteNaoEncontradoException(mensagem="id=x")
        assert exc.mensagem == "id=x"

    def test_veiculo_nao_encontrado_default(self) -> None:
        exc = VeiculoNaoEncontradoException()
        assert isinstance(exc, EntidadeNaoEncontradaException)
        assert "Veiculo" in exc.mensagem

    def test_placa_duplicada_default(self) -> None:
        exc = PlacaDuplicadaException()
        assert isinstance(exc, EntidadeDuplicadaException)
        assert "Placa" in exc.mensagem

    def test_documento_duplicado_default(self) -> None:
        exc = DocumentoDuplicadoException()
        assert isinstance(exc, EntidadeDuplicadaException)
        assert "Documento" in exc.mensagem
