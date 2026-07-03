from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.cliente_veiculo.interfaces.schemas import (
    AdicionarVeiculoRequest,
    AtualizarClienteRequest,
    ClienteResponse,
    ConsentimentoRequest,
    CriarClienteRequest,
    VeiculoResponse,
)


class TestCriarClienteRequest:
    def test_dados_validos(self) -> None:
        req = CriarClienteRequest(
            nome="Joao", documento="21249722519", tipo_documento="cpf", contato="11999"
        )
        assert req.nome == "Joao"

    def test_rejeita_campos_extras(self) -> None:
        with pytest.raises(ValidationError):
            CriarClienteRequest(
                nome="Joao",
                documento="21249722519",
                tipo_documento="cpf",
                contato="11999",
                extra="campo",  # type: ignore[call-arg]
            )

    def test_rejeita_nome_vazio(self) -> None:
        with pytest.raises(ValidationError):
            CriarClienteRequest(
                nome="", documento="21249722519", tipo_documento="cpf", contato="11999"
            )

    def test_rejeita_tipo_documento_invalido(self) -> None:
        with pytest.raises(ValidationError):
            CriarClienteRequest(
                nome="Joao",
                documento="21249722519",
                tipo_documento="rg",
                contato="11999",
            )


class TestAtualizarClienteRequest:
    def test_dados_validos(self) -> None:
        req = AtualizarClienteRequest(nome="Joao Silva", contato="11888")
        assert req.nome == "Joao Silva"

    def test_rejeita_campos_extras(self) -> None:
        with pytest.raises(ValidationError):
            AtualizarClienteRequest(
                nome="Joao",
                contato="11888",
                extra="x",  # type: ignore[call-arg]
            )


class TestAdicionarVeiculoRequest:
    def test_dados_validos(self) -> None:
        req = AdicionarVeiculoRequest(
            placa="ABC1234", marca="Fiat", modelo="Uno", ano=2020
        )
        assert req.placa == "ABC1234"

    def test_rejeita_placa_curta(self) -> None:
        with pytest.raises(ValidationError):
            AdicionarVeiculoRequest(placa="ABC", marca="Fiat", modelo="Uno", ano=2020)

    def test_rejeita_ano_invalido(self) -> None:
        with pytest.raises(ValidationError):
            AdicionarVeiculoRequest(
                placa="ABC1234", marca="Fiat", modelo="Uno", ano=1800
            )

    def test_rejeita_ano_acima_do_limite_do_dominio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.cliente_veiculo.interfaces import schemas as schemas_module

        monkeypatch.setattr(schemas_module, "ano_maximo_permitido", lambda: 2031)
        with pytest.raises(ValidationError, match="ano deve ser menor ou igual a 2031"):
            AdicionarVeiculoRequest(
                placa="ABC1234", marca="Fiat", modelo="Uno", ano=2050
            )


class TestConsentimentoRequest:
    def test_normaliza_tipo_lowercase_e_strip(self) -> None:
        req = ConsentimentoRequest(tipo="  Marketing ")
        assert req.tipo == "marketing"

    def test_rejeita_tipo_whitespace(self) -> None:
        with pytest.raises(ValidationError):
            ConsentimentoRequest(tipo="   ")


class TestResponses:
    def test_veiculo_response_serializa(self) -> None:
        resp = VeiculoResponse(
            id=uuid4(), placa="ABC1234", marca="Fiat", modelo="Uno", ano=2020
        )
        assert resp.placa == "ABC1234"

    def test_cliente_response_com_veiculos(self) -> None:
        veiculo = VeiculoResponse(
            id=uuid4(), placa="ABC1234", marca="Fiat", modelo="Uno", ano=2020
        )
        resp = ClienteResponse(
            id=uuid4(),
            nome="Joao",
            documento_formatado="212.497.225-19",
            documento_mascarado="***.***.***-19",
            tipo_documento="cpf",
            contato="11999",
            ativo=True,
            veiculos=[veiculo],
        )
        assert len(resp.veiculos) == 1
