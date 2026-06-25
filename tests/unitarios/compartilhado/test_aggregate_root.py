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

    def test_remover_eventos_remove_por_identidade_preservando_o_resto(self) -> None:
        agregado = _AgregadoTeste()
        agregado.executar_acao()
        agregado.executar_acao()
        agregado.executar_acao()
        eventos = agregado.coletar_eventos()
        a_remover = [eventos[0], eventos[2]]

        agregado.remover_eventos(a_remover)

        restantes = agregado.coletar_eventos()
        assert len(restantes) == 1
        # O sobrevivente e EXATAMENTE o objeto do meio (identidade, nao valor).
        assert restantes[0] is eventos[1]

    def test_remover_eventos_usa_identidade_nao_igualdade(self) -> None:
        # Dois DomainEvent distintos com o MESMO agregado_id sao iguais por
        # valor (dataclass) mas linhas distintas. Remover um nao deve apagar o
        # outro: a UoW remove instancias enfileiradas especificas, nao "iguais".
        id_fixo = uuid4()
        ev_a = DomainEvent(agregado_id=id_fixo)
        ev_b = DomainEvent(agregado_id=id_fixo)
        agregado = _AgregadoTeste()
        agregado._registrar_evento(ev_a)
        agregado._registrar_evento(ev_b)

        agregado.remover_eventos([ev_a])

        restantes = agregado.coletar_eventos()
        assert len(restantes) == 1
        assert restantes[0] is ev_b

    def test_remover_eventos_lista_vazia_e_noop(self) -> None:
        agregado = _AgregadoTeste()
        agregado.executar_acao()

        agregado.remover_eventos([])

        assert len(agregado.coletar_eventos()) == 1
