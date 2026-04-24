"""Testes unitarios da ``ClienteFluxosAlternativosJourney``.

Parametrizados pelos 7 cenarios de ``TODOS_CENARIOS``. Nao dependem de
instancia viva: ``httpx.MockTransport`` simula o backend com uma maquina
de status minima mas fiel o suficiente pra exercitar cada cenario.

O mock implementa:
  - transicoes validas (allow-list em ``_TRANSICOES``) -> 200 + novo estado
  - transicoes invalidas -> 409 (o que valida o cenario TRANSICOES_INVALIDAS)
  - cancelamento em estado nao-terminal -> 200 + CANCELADA
  - cancelamento em estado terminal -> 409
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest
from full_test.client.system_client import SystemClient
from full_test.journeys.cliente_fluxos_alternativos import (
    TODOS_CENARIOS,
    Cenario,
    ClienteFluxosAlternativosJourney,
    RecursosSeed,
)
from full_test.journeys.resultado import StatusJourney

if TYPE_CHECKING:
    from full_test.seeders.config import FullTestConfig


_ESTADOS_TERMINAIS = frozenset({"entregue", "cancelada"})


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
    seed: int | None = 99


class _ServerFake:
    """Mock com maquina de status minima pra exercitar os 7 cenarios.

    ``_TRANSICOES`` e ``cancelamento``/terminal sao a unica logica real: tudo
    que for transicao ilegal responde 409, o que e exatamente o que a journey
    precisa pra validar o cenario TRANSICOES_INVALIDAS. Um mock mais frouxo
    (aceitar qualquer transicao) tornaria esse cenario vacuo.
    """

    def __init__(self) -> None:
        self.cliente_id = uuid4()
        self.veiculo_id = uuid4()
        self.ordem_id = uuid4()
        self.servico_id = uuid4()
        self.item_id = uuid4()
        self.status = "recebida"

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
            return httpx.Response(201, json=self._cli())
        if path == f"/api/v1/clientes/{self.cliente_id}/veiculos" and method == "POST":
            return httpx.Response(201, json=self._vei())

        if path == "/api/v1/ordens-de-servico/" and method == "POST":
            return httpx.Response(201, json=self._ord())
        if (
            path == f"/api/v1/ordens-de-servico/{self.ordem_id}/itens"
            and method == "POST"
        ):
            return httpx.Response(200, json=self._ord())

        if path == "/api/v1/acompanhamento" and method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": self.status,
                    "criado_em": "2026-04-22T10:00:00+00:00",
                    "atualizado_em": "2026-04-22T11:00:00+00:00",
                },
            )

        return self._transicao(path, method)

    def _transicao(self, path: str, method: str) -> httpx.Response:
        prefixo = f"/api/v1/ordens-de-servico/{self.ordem_id}"
        # Allow-list (estado_atual, endpoint) -> estado_destino. Qualquer par
        # fora desse dict (e que nao seja o cancelamento, tratado abaixo)
        # devolve 409. E essa rigidez que garante que o cenario
        # ``TRANSICOES_INVALIDAS`` nao passe de graca.
        permitidas: dict[tuple[str, str], str] = {
            ("recebida", f"{prefixo}/diagnostico"): "em_diagnostico",
            ("em_diagnostico", f"{prefixo}/orcamento"): "aguardando_aprovacao",
            ("aguardando_aprovacao", f"{prefixo}/aprovacao"): "em_execucao",
            ("em_execucao", f"{prefixo}/finalizacao"): "finalizada",
            ("finalizada", f"{prefixo}/entrega"): "entregue",
            (
                "em_execucao",
                f"{prefixo}/orcamento-complementar",
            ): "aguardando_aprovacao_complementar",
            (
                "aguardando_aprovacao_complementar",
                f"{prefixo}/aprovacao-complementar",
            ): "em_execucao",
            (
                "aguardando_aprovacao_complementar",
                f"{prefixo}/rejeicao-complementar",
            ): "em_execucao",
        }

        # Cancelamento e permitido em qualquer estado NAO-TERMINAL.
        if path == f"{prefixo}/cancelamento" and method == "POST":
            if self.status in _ESTADOS_TERMINAIS:
                return httpx.Response(
                    409,
                    json={
                        "erro": {
                            "codigo": "TRANSICAO_INVALIDA",
                            "mensagem": f"estado terminal: {self.status}",
                        }
                    },
                )
            self.status = "cancelada"
            return httpx.Response(200, json=self._ord())

        if method != "POST":
            return httpx.Response(
                404, json={"detail": f"rota nao mockada: {method} {path}"}
            )

        destino = permitidas.get((self.status, path))
        if destino is None:
            return httpx.Response(
                409,
                json={
                    "erro": {
                        "codigo": "TRANSICAO_INVALIDA",
                        "mensagem": f"transicao invalida {self.status} -> {path}",
                    }
                },
            )
        self.status = destino
        return httpx.Response(200, json=self._ord())

    def _cli(self) -> dict[str, object]:
        return {
            "id": str(self.cliente_id),
            "nome": "C",
            "documento_formatado": "12345678909",
            "documento_mascarado": "***",
            "tipo_documento": "cpf",
            "contato": "+55 11 900000000",
            "ativo": True,
            "veiculos": [],
        }

    def _vei(self) -> dict[str, object]:
        return {
            "id": str(self.veiculo_id),
            "placa": "XYZ1234",
            "marca": "F",
            "modelo": "U",
            "ano": 2015,
        }

    def _ord(self) -> dict[str, object]:
        return {
            "id": str(self.ordem_id),
            "cliente_id": str(self.cliente_id),
            "veiculo_id": str(self.veiculo_id),
            "status": self.status,
            "itens": [
                {
                    "id": str(uuid4()),
                    "servico_catalogo_id": str(self.servico_id),
                    "item_estoque_id": str(self.item_id),
                    "descricao": "x",
                    "quantidade": 1,
                    "preco_unitario_centavos": 100,
                    "subtotal_centavos": 100,
                }
            ],
            "orcamento": None,
            "criado_em": "2026-04-22T10:00:00+00:00",
            "atualizado_em": "2026-04-22T11:00:00+00:00",
        }


def _fabrica_client_factory(
    handler: httpx.MockTransport,
) -> type[SystemClient]:
    """Retorna um callable compativel com o ctor do ``SystemClient``.

    Mesma estrategia do ``test_cliente_fluxo_completo``: substitui o
    ``_client`` pelo mock transport, e sobrescreve ``sem_autenticacao`` pra
    retornar outra instancia ligada ao MESMO mock (senao as consultas
    publicas viriam sem transport mockado e falhariam por rede indisponivel).
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


def test_todos_cenarios_exporta_sete_valores() -> None:
    """Garante o contrato exposto ao orchestrator (step 13 itera sobre a tupla).

    Se alguem adicionar/remover um membro de ``Cenario`` sem atualizar o
    orchestrator, este teste quebra antes de o step 13 executar em paralelo.
    """
    assert len(TODOS_CENARIOS) == 7
    assert set(TODOS_CENARIOS) == set(Cenario)


@pytest.mark.parametrize(
    "cenario",
    list(TODOS_CENARIOS),
    ids=lambda c: c.value,
)
def test_cenario_executa_ate_o_fim(
    monkeypatch: pytest.MonkeyPatch,
    cenario: Cenario,
) -> None:
    """Cada um dos 7 cenarios roda ate o fim com ``StatusJourney.OK``."""
    server = _ServerFake()
    transport = httpx.MockTransport(server)

    monkeypatch.setattr(
        "full_test.journeys.cliente_fluxos_alternativos.SystemClient",
        _fabrica_client_factory(transport),
    )

    recursos = RecursosSeed(
        servico_id=server.servico_id, item_estoque_id=server.item_id
    )
    j = ClienteFluxosAlternativosJourney(
        config=_fake_config(),
        instance_id="001",
        recursos=recursos,
        cenario=cenario,
        rng=random.Random(0),  # noqa: S311
    )
    resultado = j.rodar(timeout_s=30.0)

    assert resultado.status == StatusJourney.OK, (
        f"cenario={cenario.value} falhou: {resultado.falha}"
    )
