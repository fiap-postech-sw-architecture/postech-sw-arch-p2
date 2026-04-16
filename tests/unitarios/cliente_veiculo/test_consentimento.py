from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.cliente_veiculo.dominio.consentimento import ConsentimentoCliente


class TestConsentimentoCliente:
    def test_criar_consentimento_valido(self) -> None:
        agora = datetime.now(tz=UTC)
        c = ConsentimentoCliente(
            _cliente_id=uuid4(),
            _tipo="tratamento_dados",
            _concedido_em=agora,
        )
        assert c.tipo == "tratamento_dados"
        assert c.concedido_em == agora
        assert c.revogado_em is None
        assert c.ativo is True

    def test_revogar_consentimento(self) -> None:
        agora = datetime.now(tz=UTC)
        c = ConsentimentoCliente(
            _cliente_id=uuid4(),
            _tipo="marketing",
            _concedido_em=agora,
        )
        revogacao = datetime.now(tz=UTC)
        c.revogar(revogacao)
        assert c.revogado_em == revogacao
        assert c.ativo is False

    def test_revogar_consentimento_ja_revogado_falha(self) -> None:
        agora = datetime.now(tz=UTC)
        c = ConsentimentoCliente(
            _cliente_id=uuid4(),
            _tipo="compartilhamento",
            _concedido_em=agora,
        )
        c.revogar(agora)
        with pytest.raises(ValueError, match="ja foi revogado"):
            c.revogar(agora)

    def test_consentimento_sem_cliente_id_falha(self) -> None:
        with pytest.raises(ValueError, match="cliente_id"):
            ConsentimentoCliente(
                _tipo="tratamento_dados",
                _concedido_em=datetime.now(tz=UTC),
            )

    def test_consentimento_sem_tipo_falha(self) -> None:
        with pytest.raises(ValueError, match="tipo"):
            ConsentimentoCliente(
                _cliente_id=uuid4(),
                _concedido_em=datetime.now(tz=UTC),
            )

    def test_consentimento_sem_concedido_em_falha(self) -> None:
        with pytest.raises(ValueError, match="concedido_em"):
            ConsentimentoCliente(
                _cliente_id=uuid4(),
                _tipo="tratamento_dados",
            )

    def test_cliente_id_property(self) -> None:
        cid = uuid4()
        agora = datetime.now(tz=UTC)
        c = ConsentimentoCliente(
            _cliente_id=cid,
            _tipo="marketing",
            _concedido_em=agora,
        )
        assert c.cliente_id == cid
