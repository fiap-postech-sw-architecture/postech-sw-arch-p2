from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.compartilhado.dominio.events import DomainEvent


@dataclass(frozen=True)
class _EventoConcreto(DomainEvent):
    descricao: str = ""


class TestDomainEvent:
    def test_ocorrido_em_padrao_utc(self) -> None:
        antes = datetime.now(UTC)
        evento = DomainEvent(agregado_id=uuid4())
        depois = datetime.now(UTC)
        assert antes <= evento.ocorrido_em <= depois

    def test_agregado_id_armazenado(self) -> None:
        id_agregado = uuid4()
        evento = DomainEvent(agregado_id=id_agregado)
        assert evento.agregado_id == id_agregado

    def test_imutabilidade(self) -> None:
        evento = DomainEvent(agregado_id=uuid4())
        with pytest.raises(FrozenInstanceError):
            evento.agregado_id = uuid4()  # type: ignore[misc]

    def test_evento_concreto_com_payload(self) -> None:
        id_agregado = uuid4()
        evento = _EventoConcreto(
            agregado_id=id_agregado,
            descricao="teste",
        )
        assert evento.descricao == "teste"
        assert evento.agregado_id == id_agregado

    def test_evento_concreto_imutavel(self) -> None:
        evento = _EventoConcreto(agregado_id=uuid4(), descricao="teste")
        with pytest.raises(FrozenInstanceError):
            evento.descricao = "outro"  # type: ignore[misc]
