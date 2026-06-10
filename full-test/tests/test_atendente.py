"""Testes unitarios da ``AtendenteJourney``.

NAO exige instancia viva. ``httpx.MockTransport`` simula o backend o
suficiente pra exercitar os 10 passos documentados na journey.

Cobertura:
  1. Happy path: todos os 10 passos completam com ``StatusJourney.OK``.
  2. Validacao do nome: a exportacao precisa conter o nome atualizado.
  3. Exclusao real: apos ``DELETE /dados-pessoais``, o ``GET`` subsequente
     volta 404 — o mock mantem o estado ``dados_excluidos`` pra forcar isso.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import httpx
import pytest
from full_test.client.system_client import SystemClient
from full_test.journeys.atendente import AtendenteJourney
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
    seed: int | None = 7


class _ServerFake:
    """Mock dos endpoints exercitados pela journey.

    Mantem estado minimo pra validar os dois comportamentos interessantes:
      - ``listar_veiculos`` retorna 1 elemento apos ``DELETE`` do primeiro
      - ``GET /dados-pessoais`` retorna 404 apos ``DELETE``
    """

    def __init__(self) -> None:
        self.cliente_id: UUID = uuid4()
        self.veiculo_ids: list[UUID] = [uuid4(), uuid4()]
        self._veiculos_criados = 0
        self.dados_excluidos = False
        self.ativo = True
        self.veiculos_removidos: set[UUID] = set()
        # nome atualizado e comparado pela journey — precisa bater com o que a
        # journey manda no PUT. A journey envia ``Cliente Atd 001 (atualizado)``.
        self.nome_atual = "Cliente Atd 001"

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

        if path == f"/api/v1/clientes/{self.cliente_id}" and method == "GET":
            return httpx.Response(200, json=self._cli())

        if path == f"/api/v1/clientes/{self.cliente_id}" and method == "PUT":
            # O SystemClient serializa ``nome``/``contato`` no body; a journey
            # envia o nome original + " (atualizado)". Ler do body garante que
            # o mock reflita fielmente o PUT e a exportacao tenha o dado certo.
            try:
                body = request.read().decode()
                import json

                parsed = json.loads(body) if body else {}
                if "nome" in parsed:
                    self.nome_atual = str(parsed["nome"])
            except (ValueError, UnicodeDecodeError):
                pass
            return httpx.Response(200, json=self._cli())

        if path == f"/api/v1/clientes/{self.cliente_id}/veiculos" and method == "POST":
            idx = self._veiculos_criados
            self._veiculos_criados += 1
            return httpx.Response(
                201,
                json={
                    "id": str(self.veiculo_ids[idx]),
                    "placa": f"ABC{1000 + idx}",
                    "marca": "F",
                    "modelo": "U",
                    "ano": 2018 + idx,
                },
            )

        if path == f"/api/v1/clientes/{self.cliente_id}/veiculos" and method == "GET":
            ativos = [
                {
                    "id": str(vid),
                    "placa": f"ABC{1000 + i}",
                    "marca": "F",
                    "modelo": "U",
                    "ano": 2018 + i,
                }
                for i, vid in enumerate(self.veiculo_ids)
                if vid not in self.veiculos_removidos
            ]
            return httpx.Response(200, json=ativos)

        if (
            path.startswith(f"/api/v1/clientes/{self.cliente_id}/veiculos/")
            and method == "DELETE"
        ):
            veiculo_id_str = path.rsplit("/", 1)[-1]
            self.veiculos_removidos.add(UUID(veiculo_id_str))
            return httpx.Response(204)

        if (
            path == f"/api/v1/clientes/{self.cliente_id}/consentimento"
            and method == "POST"
        ):
            try:
                body = request.read().decode()
                import json

                parsed = json.loads(body) if body else {}
                tipo = str(parsed.get("tipo", "marketing"))
            except (ValueError, UnicodeDecodeError):
                tipo = "marketing"
            return httpx.Response(
                201,
                json={
                    "id": str(uuid4()),
                    "cliente_id": str(self.cliente_id),
                    "tipo": tipo,
                    "concedido_em": "2026-04-22T10:00:00+00:00",
                    "revogado_em": None,
                    "ativo": True,
                },
            )
        if (
            path == f"/api/v1/clientes/{self.cliente_id}/consentimento"
            and method == "DELETE"
        ):
            return httpx.Response(204)

        if path == f"/api/v1/clientes/{self.cliente_id}/dados-pessoais":
            if method == "GET":
                if self.dados_excluidos:
                    return httpx.Response(
                        404,
                        json={
                            "erro": {
                                "codigo": "NAO_ENCONTRADO",
                                "mensagem": "cliente excluido",
                            }
                        },
                    )
                return httpx.Response(
                    200,
                    json={
                        "id": str(self.cliente_id),
                        "nome": self.nome_atual,
                        "documento_formatado": "12345678909",
                        "tipo_documento": "cpf",
                        "contato": "+55 11 922222222",
                        "veiculos": [],
                        "ativo": True,
                    },
                )
            if method == "DELETE":
                # Anonimizacao LGPD: sobrescreve PII + marca ativo=False,
                # nao deleta a linha (contrato do repository).
                self.dados_excluidos = True
                self.nome_atual = "ANONIMIZADO"
                self.ativo = False
                return httpx.Response(204)

        return httpx.Response(
            404, json={"detail": f"rota nao mockada: {method} {path}"}
        )

    def _cli(self) -> dict[str, object]:
        return {
            "id": str(self.cliente_id),
            "nome": self.nome_atual,
            "documento_formatado": "12345678909",
            "documento_mascarado": "***",
            "tipo_documento": "cpf",
            "contato": "+55 11 922222222",
            "ativo": self.ativo,
            "veiculos": [],
        }


def _fabrica_client_factory(
    transport: httpx.MockTransport,
) -> type[SystemClient]:
    """Factory que injeta o mock transport no ``SystemClient`` recem-criado.

    Mesmo padrao usado por ``test_cliente_fluxo_completo``/
    ``test_cliente_fluxos_alternativos``.
    """

    def fabrica(base_url: str, **kwargs: object) -> SystemClient:
        client = SystemClient(base_url=base_url, **kwargs)  # type: ignore[arg-type]
        client.close()
        client._client = httpx.Client(transport=transport, base_url=base_url)
        return client

    return fabrica  # type: ignore[return-value]


def _fake_config() -> FullTestConfig:
    return _CfgFake()  # type: ignore[return-value]


def test_atendente_fluxo_feliz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todos os 10 passos passam; ``StatusJourney.OK`` ao final."""
    server = _ServerFake()
    transport = httpx.MockTransport(server)

    monkeypatch.setattr(
        "full_test.journeys.atendente.SystemClient",
        _fabrica_client_factory(transport),
    )

    journey = AtendenteJourney(
        config=_fake_config(),
        instance_id="001",
        atendente_email="atendente-00@full-test.local",
        atendente_senha="FullTestSecret123!",
        rng=random.Random(0),  # noqa: S311
    )
    resultado = journey.rodar(timeout_s=30.0)

    assert resultado.status == StatusJourney.OK, (
        f"esperado OK, veio {resultado.status.value}: {resultado.falha}"
    )

    # Todos os passos documentados precisam aparecer no log — protege contra
    # renomeacao acidental ou remocao silenciosa de passo.
    nomes = [p.nome for p in resultado.passos]
    for esperado in (
        "setup/login-atendente",
        "criar-cliente",
        "cadastrar-veiculo-0",
        "cadastrar-veiculo-1",
        "atualizar-cliente",
        "consentimento-registrar/marketing",
        "consentimento-registrar/comunicacoes",
        "lgpd-exportar-dados",
        "consentimento-revogar/marketing",
        "remover-veiculo",
        "listar-veiculos-apos-remocao",
        "lgpd-excluir-dados",
        "lgpd-validar-anonimizacao",
        "teardown/logout",
    ):
        assert esperado in nomes, f"passo ausente: {esperado!r}; veio {nomes}"


def test_atendente_falha_se_anonimizacao_nao_aplicada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se o ``DELETE /dados-pessoais`` nao anonimizar, a journey precisa falhar.

    Contrato LGPD deste app: DELETE anonimiza (``nome="ANONIMIZADO"``,
    ``ativo=False``), nao deleta. O mock aqui aceita o DELETE mas NAO muta o
    estado — simulando um bug onde o handler retorna 204 sem aplicar. A
    journey tem que pegar via comparacao de ``nome`` + ``ativo`` pos-DELETE.
    """
    server = _ServerFake()

    # Override: 204 no DELETE /dados-pessoais sem mutar nome/ativo.
    original_call = server.__call__

    def call_sem_anonimizar(request: httpx.Request) -> httpx.Response:
        if (
            request.url.path == f"/api/v1/clientes/{server.cliente_id}/dados-pessoais"
            and request.method == "DELETE"
        ):
            return httpx.Response(204)  # 204 mas sem mutacao de estado
        return original_call(request)

    transport = httpx.MockTransport(call_sem_anonimizar)

    monkeypatch.setattr(
        "full_test.journeys.atendente.SystemClient",
        _fabrica_client_factory(transport),
    )

    journey = AtendenteJourney(
        config=_fake_config(),
        instance_id="002",
        atendente_email="atendente-00@full-test.local",
        atendente_senha="FullTestSecret123!",
        rng=random.Random(1),  # noqa: S311
    )
    resultado = journey.rodar(timeout_s=30.0)

    assert resultado.status == StatusJourney.FALHOU, (
        f"esperado FALHOU (anonimizacao falsa nao foi detectada), "
        f"veio {resultado.status}"
    )
    assert resultado.falha is not None
    assert "ANONIMIZADO" in resultado.falha, (
        f"mensagem de falha nao menciona ANONIMIZADO: {resultado.falha!r}"
    )
