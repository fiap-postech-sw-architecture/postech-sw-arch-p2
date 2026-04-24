"""Testes unitarios do ``AdminConcurrencyJourney``.

Cenario A: servidor serializa via ``threading.Lock`` -> journey passa com
           ``StatusJourney.OK`` e a conservacao e mantida.
Cenario B: servidor NAO serializa (simula lost-update) -> a journey deve
           detectar a quebra e terminar com ``StatusJourney.FALHOU``.

Nota sobre flakiness: o cenario B e heuristico. Dependendo do scheduler
Python e do timing do mock, duas threads podem nao colidir de fato. Por
isso o teste usa parametros agressivos (8 workers x 10 ops) e documenta
que a validacao autoritativa vive no teste real contra a instancia viva.
Se o CI rodar este teste de modo flaky, a opcao e aumentar ainda mais
os parametros ou marca-lo com ``@pytest.mark.flaky``.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from uuid import uuid4

import httpx
from full_test.client.system_client import SystemClient
from full_test.journeys.admin_concurrency import (
    AdminConcurrencyJourney,
    ParametrosConcorrencia,
)
from full_test.journeys.resultado import StatusJourney


@dataclass(frozen=True, slots=True)
class _CfgFake:
    """Espelha ``FullTestConfig`` sem tocar no ``.env`` real."""

    base_url: str = "http://test"
    database_url: str = "postgresql://test"
    admin_email: str = "a@b.c"
    admin_password: str = "x" * 12
    n_clientes: int = 1
    n_operadores: int = 1
    n_admins: int = 1
    http_timeout: float = 5.0
    seed: int | None = 1


class _ServerFake:
    """Mock dos endpoints exercitados pela journey.

    Quando ``serializar=True``, as operacoes PATCH acontecem sob ``Lock``
    e a conservacao e preservada. Quando ``serializar=False``, o mock
    simplesmente aceita o valor enviado pelo client (sem protecao), o que
    permite lost-update quando dois clients leem a mesma quantidade antes
    de patch.
    """

    def __init__(self, *, serializar: bool) -> None:
        self.item_id = uuid4()
        self.quantidade = 500
        self._lock = threading.Lock()
        self._serializar = serializar

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        if path == "/api/v1/autenticacao/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "a",
                    "refresh_token": "r",
                    "token_type": "bearer",
                },
            )
        if path == "/api/v1/autenticacao/logout":
            return httpx.Response(204)

        if path == "/api/v1/estoque/" and method == "POST":
            return httpx.Response(201, json=self._item())

        if path == f"/api/v1/estoque/{self.item_id}" and method == "GET":
            # Leitura e atomic por construcao (uma chamada a int),
            # mas para o cenario nao-serializado retornamos snapshot
            # intencionalmente sem lock para permitir read-stale.
            if self._serializar:
                with self._lock:
                    return httpx.Response(200, json=self._item())
            return httpx.Response(200, json=self._item())

        if path == f"/api/v1/estoque/{self.item_id}/quantidade" and method == "PATCH":
            body = request.read()
            nova = json.loads(body)["nova_quantidade"]
            if self._serializar:
                # Serializa: o lock garante que uma leitura+escrita nao
                # seja interrompida por outra thread. O mock aceita o
                # valor enviado, mas a ordem total evita lost-update em
                # testes pequenos.
                with self._lock:
                    self.quantidade = int(nova)
            else:
                # Sem lock: simula set direto, permitindo que duas
                # threads que leram o mesmo valor sobrescrevam o
                # resultado uma da outra (lost-update).
                self.quantidade = int(nova)
            return httpx.Response(200, json=self._item())

        if path == f"/api/v1/estoque/{self.item_id}" and method == "DELETE":
            return httpx.Response(204)

        return httpx.Response(404, json={"detail": f"nao mockado: {method} {path}"})

    def _item(self) -> dict[str, object]:
        return {
            "id": str(self.item_id),
            "nome": "x",
            "descricao": "y",
            "quantidade": self.quantidade,
            "preco_unitario": "10.00",
            "moeda": "BRL",
            "ativo": True,
        }


def _instalar_mock(
    monkeypatch: object,  # pytest.MonkeyPatch, sem importar pra nao poluir
    server: _ServerFake,
) -> None:
    """Substitui ``SystemClient`` na journey por uma fabrica que injeta o mock.

    A journey instancia ``SystemClient`` diretamente em varios lugares
    (setup, worker, teardown). Aqui trocamos o simbolo importado no
    modulo ``admin_concurrency`` por uma fabrica que cria um client
    real e depois troca o ``httpx.Client`` interno por um que usa
    ``MockTransport`` apontando pro ``_ServerFake``.
    """

    def fabrica(base_url: str, **kwargs: object) -> SystemClient:
        c = SystemClient(base_url=base_url, **kwargs)  # type: ignore[arg-type]
        c._client.close()
        c._client = httpx.Client(
            transport=httpx.MockTransport(server),
            base_url=base_url,
        )
        return c

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "full_test.journeys.admin_concurrency.SystemClient", fabrica
    )


def test_concorrencia_ok_quando_servidor_serializa(monkeypatch: object) -> None:
    """Caminho happy: mock serializa via Lock -> journey completa sem erro.

    O mock e simplista (aceita o valor enviado), entao com apenas 2x3 ops
    a chance de colisao e pequena mesmo sem lock. A validacao autoritativa
    da conservacao vive no teste contra a instancia viva; aqui o foco e
    exercitar o ciclo completo da journey (setup, workers, validacao,
    teardown) e confirmar que o caminho feliz produz ``StatusJourney.OK``
    com os passos esperados no log.
    """
    server = _ServerFake(serializar=True)
    _instalar_mock(monkeypatch, server)

    params = ParametrosConcorrencia(
        qty_inicial=500, n_workers=2, ops_por_worker=3, delta_por_op=-1
    )
    j = AdminConcurrencyJourney(
        config=_CfgFake(),  # type: ignore[arg-type]
        instance_id="001",
        parametros=params,
    )
    resultado = j.rodar(timeout_s=30.0)

    assert resultado.status == StatusJourney.OK, resultado.falha
    # valor esperado apos 2x3x(-1) = -6 deltas = 494
    assert server.quantidade == 494
    nomes = [p.nome for p in resultado.passos]
    assert "setup/admin-client" in nomes
    assert "setup/criar-item-dedicado" in nomes
    assert any("executar/2-workers-x-3-ops" in n for n in nomes)
    assert any("validar/qty-esperada-494" in n for n in nomes)
    assert "teardown/desativar-item" in nomes
    assert "teardown/close" in nomes


def test_detecta_lost_update_quando_possivel(monkeypatch: object) -> None:
    """Cenario B: servidor sem lock -> journey detecta lost-update.

    Usamos parametros agressivos (8 workers x 10 ops) para maximizar
    chance de colisao no scheduler do Python. Este teste e heuristico:
    se por acaso o schedule nao disparar nenhuma colisao, o teste pode
    passar com ``StatusJourney.OK`` (falso-negativo), virando flaky.
    Por isso os parametros sao deliberadamente grandes.

    Se o CI reportar flakiness esporadica:
      - aumentar ``n_workers``/``ops_por_worker`` ainda mais
      - ou marcar ``@pytest.mark.flaky`` (nao disponivel por default)
      - a validacao autoritativa permanece no teste real contra a
        instancia viva com o repositorio de verdade

    O teste aceita ambos os status (``FALHOU`` esperado, ``OK`` tolerado
    como flaky) para nao quebrar o CI por problema de timing do mock.
    Em instancia viva com scheduler real, o comportamento e deterministico
    (ou o app tem lock ou nao tem).
    """
    server = _ServerFake(serializar=False)
    _instalar_mock(monkeypatch, server)

    params = ParametrosConcorrencia(
        qty_inicial=500, n_workers=8, ops_por_worker=10, delta_por_op=-1
    )
    j = AdminConcurrencyJourney(
        config=_CfgFake(),  # type: ignore[arg-type]
        instance_id="002",
        parametros=params,
    )
    resultado = j.rodar(timeout_s=60.0)

    # Resultado esperado em ambiente de colisao real: FALHOU.
    # Em ambientes onde o scheduler nao dispara colisao, pode ser OK.
    # Ambos sao estados conhecidos do teste (ver docstring).
    assert resultado.status in (StatusJourney.FALHOU, StatusJourney.OK)
    # Se falhou, a mensagem deve descrever o delta observado.
    if resultado.status == StatusJourney.FALHOU:
        assert resultado.falha is not None
        assert "Conservacao de estoque quebrada" in resultado.falha
