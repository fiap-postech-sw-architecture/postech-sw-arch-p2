from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.ordem_servico.interfaces.schemas import (
    AcompanhamentoResponse,
    AdicionarItemRequest,
    CancelarOrdemRequest,
    CriarOrdemRequest,
    OrdemDeServicoResponse,
    OrdemResumoResponse,
)


class TestCriarOrdemRequest:
    def test_valido(self) -> None:
        req = CriarOrdemRequest(cliente_id=uuid4(), veiculo_id=uuid4())
        assert req.cliente_id is not None

    def test_rejeita_extras(self) -> None:
        with pytest.raises(ValidationError):
            CriarOrdemRequest(
                cliente_id=uuid4(),
                veiculo_id=uuid4(),
                extra="x",  # type: ignore[call-arg]
            )


class TestAdicionarItemRequest:
    def test_rejeita_quantidade_zero(self) -> None:
        with pytest.raises(ValidationError):
            AdicionarItemRequest(
                servico_catalogo_id=uuid4(),
                descricao="X",
                quantidade=0,
            )


class TestCancelarOrdemRequest:
    def test_rejeita_motivo_vazio(self) -> None:
        with pytest.raises(ValidationError):
            CancelarOrdemRequest(motivo="")


class TestOrdemDeServicoResponse:
    def test_serializa(self) -> None:
        resp = OrdemDeServicoResponse(
            id=uuid4(),
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            status="recebida",
            itens=[],
            orcamento=None,
            criado_em=datetime.now(UTC),
            atualizado_em=datetime.now(UTC),
        )
        assert resp.status == "recebida"
        # Campos enriquecidos cross-context tem default None pra UI ter
        # placeholder quando o contexto Cliente+Veiculo nao resolveu.
        assert resp.cliente_nome is None
        assert resp.veiculo_placa is None

    def test_aceita_cliente_nome_e_veiculo_placa(self) -> None:
        resp = OrdemDeServicoResponse(
            id=uuid4(),
            cliente_id=uuid4(),
            cliente_nome="Maria Silva",
            veiculo_id=uuid4(),
            veiculo_placa="ABC1234",
            status="recebida",
            itens=[],
            orcamento=None,
            criado_em=datetime.now(UTC),
            atualizado_em=datetime.now(UTC),
        )
        assert resp.cliente_nome == "Maria Silva"
        assert resp.veiculo_placa == "ABC1234"

    def test_situacao_derivada_do_status(self) -> None:
        # RF-021: `situacao` traduz o status tecnico para o vocabulario
        # do challenge sem substituir o campo `status` (compatibilidade).
        resp = OrdemDeServicoResponse(
            id=uuid4(),
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            status="em_diagnostico",
            itens=[],
            orcamento=None,
            criado_em=datetime.now(UTC),
            atualizado_em=datetime.now(UTC),
        )
        assert resp.situacao == "Em diagnóstico"
        dump = resp.model_dump()
        assert dump["situacao"] == "Em diagnóstico"
        assert dump["status"] == "em_diagnostico"


class TestOrdemResumoResponse:
    def test_aceita_cliente_nome_e_veiculo_placa(self) -> None:
        resp = OrdemResumoResponse(
            id=uuid4(),
            cliente_id=uuid4(),
            cliente_nome="Joao",
            veiculo_id=uuid4(),
            veiculo_placa="XYZ9876",
            status="recebida",
            criado_em=datetime.now(UTC),
        )
        assert resp.cliente_nome == "Joao"
        assert resp.veiculo_placa == "XYZ9876"

    def test_default_none_quando_omitidos(self) -> None:
        resp = OrdemResumoResponse(
            id=uuid4(),
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            status="recebida",
            criado_em=datetime.now(UTC),
        )
        assert resp.cliente_nome is None
        assert resp.veiculo_placa is None

    def test_situacao_derivada_do_status(self) -> None:
        # RF-021 + gap §2/RN-020: o item de listagem tambem expoe
        # `situacao`; a espera complementar apresenta o mesmo rotulo
        # da espera de aprovacao.
        resp = OrdemResumoResponse(
            id=uuid4(),
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            status="aguardando_aprovacao_complementar",
            criado_em=datetime.now(UTC),
        )
        assert resp.situacao == "Aguardando aprovação"
        assert resp.model_dump()["status"] == "aguardando_aprovacao_complementar"


class TestAcompanhamentoResponse:
    def test_situacao_derivada_do_status(self) -> None:
        # RF-021: a consulta publica por placa+documento tambem informa
        # `situacao` no vocabulario do challenge ao lado do `status`
        # tecnico, mesmo padrao dos responses autenticados.
        resp = AcompanhamentoResponse(
            status="em_execucao",
            criado_em=datetime.now(UTC),
            atualizado_em=datetime.now(UTC),
        )
        assert resp.situacao == "Em execução"
        dump = resp.model_dump()
        assert dump["situacao"] == "Em execução"
        assert dump["status"] == "em_execucao"
