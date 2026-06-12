"""Testes unitarios da ``ClienteFluxoCompletoJourney``.

NAO exige instancia viva. Usa ``httpx.MockTransport`` para simular respostas
do API, e monkeypatch em ``time.sleep`` para acelerar o fluxo — sleeps
reais 2-5s sao para a execucao contra docker compose (orchestrator step 13).

Cobertura:
  1. Happy path completo: todas as 6 transicoes passam, e a consulta publica
     ``/acompanhamento`` e executada apos cada uma.
  2. Divergencia: se o ``/acompanhamento`` devolve status diferente do que a
     transicao admin registrou, a journey falha com mensagem descritiva.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest
from full_test.client.system_client import SystemClient
from full_test.journeys.cliente_fluxo_completo import (
    ClienteFluxoCompletoJourney,
    RecursosSeed,
)
from full_test.journeys.resultado import StatusJourney

if TYPE_CHECKING:
    from full_test.seeders.config import FullTestConfig


@dataclass(frozen=True, slots=True)
class _CfgFake:
    """Espelha o shape de ``FullTestConfig`` sem tocar no .env real."""

    base_url: str = "http://test"
    database_url: str = "postgresql://test"
    admin_email: str = "a@b.c"
    admin_password: str = "x" * 12
    n_clientes: int = 1
    n_operadores: int = 1
    n_admins: int = 1
    http_timeout: float = 5.0
    seed: int | None = 42


class _ServerFake:
    """Simula o backend do API para a journey completa.

    O estado ``self.status`` avanca deterministicamente a cada POST em endpoint
    de transicao. O endpoint publico ``/acompanhamento`` le o mesmo ``status``,
    por isso o happy path bate — e o segundo teste mente injetando um handler
    substituto que ignora a transicao.
    """

    def __init__(self) -> None:
        self.cliente_id = uuid4()
        self.veiculo_id = uuid4()
        self.ordem_id = uuid4()
        self.servico_id = uuid4()
        self.item_estoque_id = uuid4()
        self.status = "recebida"
        self.placa = "XYZ1234"
        self.documento = "12345678909"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        if path == "/api/v1/autenticacao/login" and method == "POST":
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

        if path == "/api/v1/clientes/" and method == "POST":
            return httpx.Response(201, json=self._cliente_payload())
        if path == f"/api/v1/clientes/{self.cliente_id}/veiculos" and method == "POST":
            return httpx.Response(201, json=self._veiculo_payload())

        if path == "/api/v1/ordens-de-servico/" and method == "POST":
            return httpx.Response(201, json=self._ordem_payload())
        if (
            path == f"/api/v1/ordens-de-servico/{self.ordem_id}/itens"
            and method == "POST"
        ):
            return httpx.Response(201, json=self._ordem_payload(com_item=True))

        base = f"/api/v1/ordens-de-servico/{self.ordem_id}"
        transicoes = {
            f"{base}/diagnostico": "em_diagnostico",
            f"{base}/orcamento": "aguardando_aprovacao",
            f"{base}/aprovacao": "em_execucao",
            f"{base}/finalizacao": "finalizada",
            f"{base}/entrega": "entregue",
        }
        if path in transicoes and method == "POST":
            self.status = transicoes[path]
            return httpx.Response(
                200,
                json=self._ordem_payload(com_item=True, com_orcamento=True),
            )

        if path == "/api/v1/acompanhamento" and method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": self.status,
                    "criado_em": "2026-04-22T10:00:00+00:00",
                    "atualizado_em": "2026-04-22T11:00:00+00:00",
                },
            )

        if path == "/api/v1/ordens-de-servico/metricas" and method == "GET":
            return httpx.Response(
                200,
                json={
                    "total": 1,
                    "por_status": {self.status: 1},
                    "tempo_medio_execucao_minutos": None,
                },
            )

        return httpx.Response(
            404, json={"detail": f"rota nao mockada: {method} {path}"}
        )

    def _cliente_payload(self) -> dict[str, object]:
        return {
            "id": str(self.cliente_id),
            "nome": "Cliente",
            "documento_formatado": self.documento,
            "documento_mascarado": "***",
            "tipo_documento": "cpf",
            "contato": "+55 11 900000000",
            "ativo": True,
            "veiculos": [],
        }

    def _veiculo_payload(self) -> dict[str, object]:
        return {
            "id": str(self.veiculo_id),
            "placa": self.placa,
            "marca": "F",
            "modelo": "U",
            "ano": 2015,
        }

    def _ordem_payload(
        self,
        *,
        com_item: bool = False,
        com_orcamento: bool = False,
    ) -> dict[str, object]:
        itens: list[dict[str, object]] = []
        orcamento: dict[str, object] | None = None
        if com_item:
            itens = [
                {
                    "id": str(uuid4()),
                    "servico_catalogo_id": str(self.servico_id),
                    "item_estoque_id": str(self.item_estoque_id),
                    "descricao": "x",
                    "quantidade": 1,
                    "preco_unitario_centavos": 1000,
                    "subtotal_centavos": 1000,
                }
            ]
        if com_orcamento:
            orcamento = {
                "total_centavos": 1000,
                "gerado_em": "2026-04-22T10:00:00+00:00",
                "itens": [],
            }
        return {
            "id": str(self.ordem_id),
            "cliente_id": str(self.cliente_id),
            "veiculo_id": str(self.veiculo_id),
            "status": self.status,
            "itens": itens,
            "orcamento": orcamento,
            "criado_em": "2026-04-22T10:00:00+00:00",
            "atualizado_em": "2026-04-22T11:00:00+00:00",
        }


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anula ``time.sleep`` dentro da journey pra acelerar os testes unitarios.

    Os sleeps 2-5s sao parte do contrato da journey (gerar delta de tempo para
    tempo_medio_execucao_minutos) mas em testes unitarios nao adicionam valor.
    Patching o simbolo no modulo da journey garante que a journey segue
    exercitando o caminho que chama sleep — so que retorna imediatamente.
    O alvo e escrito como string para contornar ``--strict`` do mypy, que
    rejeita acesso a modulos importados sem ``__all__``.
    """
    monkeypatch.setattr(
        "full_test.journeys.cliente_fluxo_completo.time.sleep",
        lambda _s: None,
    )


def _fabrica_client_factory(
    handler: httpx.MockTransport,
) -> type[SystemClient]:
    """Constroi um factory compativel com o ctor do ``SystemClient``.

    Tres peculiaridades:
      1. Substitui ``_client`` pelo mock transport (senao o init real tentaria
         HTTP de verdade no login).
      2. Sobrescreve ``sem_autenticacao`` para retornar outra instancia ligada
         ao MESMO mock — sem isso, a consulta publica criaria um ``httpx.Client``
         real e a chamada /acompanhamento fracassaria por rede indisponivel.
      3. O cast de retorno e ``type[SystemClient]`` apenas por simetria de
         assinatura — o valor de fato retornado e um callable que produz
         instancias; ``monkeypatch.setattr`` aceita qualquer callable.
    """

    def fabrica(base_url: str, **kwargs: object) -> SystemClient:
        client = SystemClient(base_url=base_url, **kwargs)  # type: ignore[arg-type]
        client.close()
        client._client = httpx.Client(transport=handler, base_url=base_url)

        def _sem_auth_override() -> SystemClient:
            anon = SystemClient(base_url=base_url, **kwargs)  # type: ignore[arg-type]
            anon.close()
            anon._client = httpx.Client(transport=handler, base_url=base_url)
            return anon

        client.sem_autenticacao = _sem_auth_override  # type: ignore[method-assign]
        return client

    return fabrica  # type: ignore[return-value]


def _fake_config() -> FullTestConfig:
    return _CfgFake()  # type: ignore[return-value]


def test_fluxo_completo_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Roda o fluxo completo e verifica que /acompanhamento bateu em cada transicao."""
    server = _ServerFake()
    transport = httpx.MockTransport(server)

    monkeypatch.setattr(
        "full_test.journeys.cliente_fluxo_completo.SystemClient",
        _fabrica_client_factory(transport),
    )

    recursos = RecursosSeed(
        servico_id=server.servico_id, item_estoque_id=server.item_estoque_id
    )
    j = ClienteFluxoCompletoJourney(
        config=_fake_config(),
        instance_id="001",
        recursos=recursos,
        rng=random.Random(0),  # noqa: S311
    )
    resultado = j.rodar(timeout_s=60.0)

    assert resultado.status == StatusJourney.OK, f"falhou: {resultado.falha}"
    nomes = [p.nome for p in resultado.passos]

    # Requisito explicito #1 do orchestrator: /acompanhamento (publico, sem auth)
    # deve ser chamado apos CADA uma das 6 transicoes de estado (incluindo a
    # criacao em RECEBIDA — que conta como a primeira observacao externa).
    transicoes = [
        "recebida",
        "em_diagnostico",
        "aguardando_aprovacao",
        "em_execucao",
        "finalizada",
        "entregue",
    ]
    acompanhamentos = [n for n in nomes if n.startswith("acompanhamento-publico/")]
    assert len(acompanhamentos) == 6, (
        f"Esperado 6 consultas publicas, vieram "
        f"{len(acompanhamentos)}: {acompanhamentos}"
    )
    for t in transicoes:
        assert any(t in n for n in acompanhamentos), (
            f"consulta publica para {t} nao foi executada; "
            f"acompanhamentos observados: {acompanhamentos}"
        )

    # Assegura que snapshot final de metricas rodou — e o valor consumido pelo
    # orchestrator na etapa de agregacao (step 13).
    assert "snapshot-metricas-final" in nomes


def test_fluxo_falha_se_acompanhamento_divergir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se /acompanhamento mente sobre o status, a journey deve falhar."""
    server = _ServerFake()
    server_original_call = server.__call__

    def handler_mentindo(request: httpx.Request) -> httpx.Response:
        # Trava a resposta publica em RECEBIDA — as transicoes admin continuam
        # funcionando, entao o primeiro ``_confirmar_status_publico("recebida")``
        # passa; o segundo (apos iniciar_diagnostico) e o que detona.
        if request.url.path == "/api/v1/acompanhamento":
            return httpx.Response(
                200,
                json={
                    "status": "recebida",
                    "criado_em": "2026-04-22T10:00:00+00:00",
                    "atualizado_em": "2026-04-22T11:00:00+00:00",
                },
            )
        return server_original_call(request)

    transport = httpx.MockTransport(handler_mentindo)

    monkeypatch.setattr(
        "full_test.journeys.cliente_fluxo_completo.SystemClient",
        _fabrica_client_factory(transport),
    )

    recursos = RecursosSeed(
        servico_id=server.servico_id, item_estoque_id=server.item_estoque_id
    )
    j = ClienteFluxoCompletoJourney(
        config=_fake_config(),
        instance_id="002",
        recursos=recursos,
        rng=random.Random(0),  # noqa: S311
    )
    resultado = j.rodar(timeout_s=60.0)

    assert resultado.status == StatusJourney.FALHOU
    falha = (resultado.falha or "").lower()
    # A mensagem do ConsistencyChecker cita /acompanhamento + status esperado.
    assert "acompanhamento" in falha or "status" in falha, (
        f"falha inesperada: {resultado.falha}"
    )
