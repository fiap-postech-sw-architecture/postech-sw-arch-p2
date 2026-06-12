"""Testes unitarios da ``MecanicoJourney``.

Nao exige instancia viva. ``httpx.MockTransport`` simula o backend o
suficiente para exercitar os passos documentados, incluindo a fronteira
RBAC: ``POST /aprovacao`` deve retornar 403 para MECANICO.

Cobertura:
  1. Happy path: todos os passos completam com ``StatusJourney.OK`` e
     o passo ``negativo/aprovar-orcamento-403`` aparece no log.
  2. Regressao RBAC: se o servidor permitir (bug) que o mecanico aprove
     o orcamento, a journey precisa falhar com mensagem descritiva.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import httpx
import pytest
from full_test.client.system_client import SystemClient
from full_test.journeys.mecanico import MecanicoJourney
from full_test.journeys.resultado import StatusJourney

if TYPE_CHECKING:
    from full_test.seeders.config import FullTestConfig


@dataclass(frozen=True, slots=True)
class _CfgFake:
    """Espelha o shape de ``FullTestConfig`` sem tocar no ``.env`` real."""

    base_url: str = "http://test"
    database_url: str = "postgresql://test"
    admin_email: str = "a@b.c"
    admin_password: str = "x" * 12
    n_clientes: int = 1
    n_operadores: int = 1
    n_admins: int = 1
    http_timeout: float = 5.0
    seed: int | None = 11


class _ServerFake:
    """Mock dos endpoints exercitados pela journey.

    Mantem estado minimo: ``status`` avanca deterministicamente a cada
    POST de transicao, e ``POST /aprovacao`` e sempre 403 (comportamento
    esperado do backend para MECANICO).
    """

    def __init__(
        self,
        ordem_id: UUID,
        servico_id: UUID,
        item_id: UUID,
    ) -> None:
        self.ordem_id = ordem_id
        self.servico_id = servico_id
        self.item_id = item_id
        self.status = "recebida"
        self.itens: list[dict[str, object]] = []
        self.com_orcamento = False
        self.cliente_id = uuid4()
        self.veiculo_id = uuid4()

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

        prefixo = f"/api/v1/ordens-de-servico/{self.ordem_id}"

        if path == prefixo and method == "GET":
            return httpx.Response(200, json=self._ordem_payload())

        if path == f"{prefixo}/itens" and method == "POST":
            self._adicionar_item_do_body(request)
            return httpx.Response(201, json=self._ordem_payload())

        if path == f"{prefixo}/diagnostico" and method == "POST":
            self.status = "em_diagnostico"
            return httpx.Response(200, json=self._ordem_payload())

        if path == f"{prefixo}/orcamento" and method == "POST":
            self.status = "aguardando_aprovacao"
            self.com_orcamento = True
            return httpx.Response(200, json=self._ordem_payload())

        if path == f"{prefixo}/aprovacao" and method == "POST":
            # RBAC: MECANICO nao pode aprovar. O handler padrao do backend
            # devolve envelope {"erro": {"codigo": "...", "mensagem": "..."}}.
            return httpx.Response(
                403,
                json={
                    "erro": {
                        "codigo": "PAPEL_NAO_AUTORIZADO",
                        "mensagem": "papel nao autorizado",
                    }
                },
            )

        return httpx.Response(
            404, json={"detail": f"rota nao mockada: {method} {path}"}
        )

    def _adicionar_item_do_body(self, request: httpx.Request) -> None:
        """Le o body do POST e guarda item+quantidade para calcular subtotal.

        O mock precisa preservar ``quantidade`` para que
        ``subtotal = preco_unitario * quantidade`` bata no ``ConsistencyChecker``
        (senao ``assert_subtotais_dos_itens`` levanta).
        """
        import json

        try:
            body = request.read().decode()
            parsed = json.loads(body) if body else {}
        except (ValueError, UnicodeDecodeError):
            parsed = {}

        quantidade = int(parsed.get("quantidade", 1))
        descricao = str(parsed.get("descricao", ""))
        item_est = parsed.get("item_estoque_id")
        preco = 1000  # centavos
        self.itens.append(
            {
                "id": str(uuid4()),
                "servico_catalogo_id": str(self.servico_id),
                "item_estoque_id": str(item_est) if item_est is not None else None,
                "descricao": descricao,
                "quantidade": quantidade,
                "preco_unitario_centavos": preco,
                "subtotal_centavos": preco * quantidade,
            }
        )

    def _ordem_payload(self) -> dict[str, object]:
        orcamento = None
        if self.com_orcamento:
            total = sum(int(i["subtotal_centavos"]) for i in self.itens)
            orcamento = {
                "total_centavos": total,
                "gerado_em": "2026-04-22T10:00:00+00:00",
                "itens": [],
            }
        return {
            "id": str(self.ordem_id),
            "cliente_id": str(self.cliente_id),
            "veiculo_id": str(self.veiculo_id),
            "status": self.status,
            "itens": self.itens,
            "orcamento": orcamento,
            "criado_em": "2026-04-22T10:00:00+00:00",
            "atualizado_em": "2026-04-22T11:00:00+00:00",
        }


def _fabrica_client_factory(
    transport: httpx.MockTransport,
) -> type[SystemClient]:
    """Factory que injeta o mock transport no ``SystemClient`` recem-criado.

    Mesmo padrao usado pelos outros testes de journey (``test_atendente``,
    ``test_cliente_*``). O ``client.close()`` descarta o httpx.Client real
    antes de substituir pelo transport mockado — evita leak de conexao.
    """

    def fabrica(base_url: str, **kwargs: object) -> SystemClient:
        client = SystemClient(base_url=base_url, **kwargs)  # type: ignore[arg-type]
        client.close()
        client._client = httpx.Client(transport=transport, base_url=base_url)
        return client

    return fabrica  # type: ignore[return-value]


def _fake_config() -> FullTestConfig:
    return _CfgFake()  # type: ignore[return-value]


def test_mecanico_fluxo_feliz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: MECANICO exerce todas as transicoes permitidas e o
    passo negativo comprova que o backend respeita a fronteira RBAC."""
    ordem_id, servico_id, item_id = uuid4(), uuid4(), uuid4()
    server = _ServerFake(ordem_id, servico_id, item_id)
    transport = httpx.MockTransport(server)

    monkeypatch.setattr(
        "full_test.journeys.mecanico.SystemClient",
        _fabrica_client_factory(transport),
    )

    journey = MecanicoJourney(
        config=_fake_config(),
        instance_id="001",
        mecanico_email="mecanico-00@full-test.local",
        mecanico_senha="FullTestSecret123!",
        ordem_id=ordem_id,
        servico_id=servico_id,
        item_estoque_id=item_id,
    )
    resultado = journey.rodar(timeout_s=30.0)

    assert resultado.status == StatusJourney.OK, (
        f"esperado OK, veio {resultado.status.value}: {resultado.falha}"
    )

    # Todos os passos documentados precisam aparecer no log — protege
    # contra renomeacao acidental ou remocao silenciosa de passo.
    nomes = [p.nome for p in resultado.passos]
    for esperado in (
        "setup/login-mecanico",
        "obter-ordem-inicial",
        "adicionar-item-com-estoque",
        "adicionar-item-sem-estoque",
        "iniciar-diagnostico",
        "gerar-orcamento",
        "negativo/aprovar-orcamento-403",
        "teardown/logout",
    ):
        assert esperado in nomes, f"passo ausente: {esperado!r}; veio {nomes}"


def test_mecanico_falha_se_aprovacao_nao_retornar_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regressao RBAC: se o servidor deixar o mecanico aprovar (bug), a
    journey DEVE falhar com mensagem mencionando RBAC ou aprovacao.
    """
    ordem_id, servico_id, item_id = uuid4(), uuid4(), uuid4()
    server = _ServerFake(ordem_id, servico_id, item_id)

    # Override: deixa ``POST /aprovacao`` passar com 200. Simula exatamente
    # o bug que queremos detectar.
    original_call = server.__call__

    def handler_permissivo(request: httpx.Request) -> httpx.Response:
        prefixo = f"/api/v1/ordens-de-servico/{server.ordem_id}"
        if request.url.path == f"{prefixo}/aprovacao" and request.method == "POST":
            server.status = "em_execucao"
            return httpx.Response(200, json=server._ordem_payload())
        return original_call(request)

    transport = httpx.MockTransport(handler_permissivo)

    monkeypatch.setattr(
        "full_test.journeys.mecanico.SystemClient",
        _fabrica_client_factory(transport),
    )

    journey = MecanicoJourney(
        config=_fake_config(),
        instance_id="002",
        mecanico_email="mecanico-00@full-test.local",
        mecanico_senha="FullTestSecret123!",
        ordem_id=ordem_id,
        servico_id=servico_id,
        item_estoque_id=item_id,
    )
    resultado = journey.rodar(timeout_s=30.0)

    assert resultado.status == StatusJourney.FALHOU, (
        f"esperado FALHOU (RBAC afrouxado nao foi detectado), "
        f"veio {resultado.status.value}"
    )
    assert resultado.falha is not None
    # A mensagem levantada pela journey e "RBAC quebrado" — qualquer uma
    # das palavras-chave garante que e esse assert especifico que disparou.
    assert ("RBAC" in resultado.falha) or ("aprovar" in resultado.falha), (
        f"mensagem de falha nao menciona RBAC/aprovar: {resultado.falha!r}"
    )
