from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.compartilhado.dominio.aggregate_root import AggregateRoot
from src.compartilhado.dominio.events import DomainEvent


@dataclass(eq=False)
class _AgregadoTeste(AggregateRoot):
    _nome: str = ""

    def executar_acao(self) -> None:
        self._registrar_evento(DomainEvent(agregado_id=self.id))


class TestAggregateRoot:
    def test_herda_de_entity(self) -> None:
        agregado = _AgregadoTeste()
        assert hasattr(agregado, "id")

    def test_sem_eventos_pendentes_inicialmente(self) -> None:
        agregado = _AgregadoTeste()
        assert agregado.coletar_eventos() == []

    def test_registrar_evento(self) -> None:
        agregado = _AgregadoTeste()
        agregado.executar_acao()
        eventos = agregado.coletar_eventos()
        assert len(eventos) == 1
        assert eventos[0].agregado_id == agregado.id

    def test_coletar_eventos_retorna_copia(self) -> None:
        agregado = _AgregadoTeste()
        agregado.executar_acao()
        eventos = agregado.coletar_eventos()
        eventos.clear()
        assert len(agregado.coletar_eventos()) == 1

    def test_limpar_eventos(self) -> None:
        agregado = _AgregadoTeste()
        agregado.executar_acao()
        agregado.limpar_eventos()
        assert agregado.coletar_eventos() == []

    def test_multiplos_eventos(self) -> None:
        agregado = _AgregadoTeste()
        agregado.executar_acao()
        agregado.executar_acao()
        assert len(agregado.coletar_eventos()) == 2

    def test_eventos_preservam_ordem(self) -> None:
        agregado = _AgregadoTeste()
        agregado.executar_acao()
        agregado.executar_acao()
        eventos = agregado.coletar_eventos()
        assert eventos[0].ocorrido_em <= eventos[1].ocorrido_em

    def test_identidade_por_uuid(self) -> None:
        id_fixo = uuid4()
        a = _AgregadoTeste(id=id_fixo)
        b = _AgregadoTeste(id=id_fixo)
        assert a == b
