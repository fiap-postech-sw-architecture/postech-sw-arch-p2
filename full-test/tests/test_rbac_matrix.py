"""Testes unitarios da matriz RBAC.

Nao exige instancia viva. Valida:

1. Integridade da matriz: total de celulas, cobertura de papeis, regras
   de publicacao/admin-only ancoradas no codigo.
2. Spot-check end-to-end com ``httpx.MockTransport``: exerce um punhado
   de celulas contra um servidor fake para provar o ciclo completo
   (setup/login, chamada, classificacao de ok vs falha, relatorio).

Cobrir 180 celulas em mocks seria redundante com os testes de
integracao que rodam contra a instancia viva (step 16). Aqui basta
garantir que o laco central nao esta quebrado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
import pytest
from full_test.client.system_client import SystemClient
from full_test.journeys.rbac_matrix import (
    RBAC_ESPERADO,
    Papel,
    RbacMatrixJourney,
    total_celulas,
)
from full_test.journeys.resultado import StatusJourney

if TYPE_CHECKING:
    from full_test.seeders.config import FullTestConfig


# ---------------- integridade da matriz ----------------


def test_matriz_tem_180_celulas() -> None:
    """45 endpoints (contagem verificada nos routers) x 4 papeis = 180."""
    assert total_celulas() == 180, f"total={total_celulas()}, esperado=180"


def test_matriz_cobre_45_endpoints() -> None:
    """45 endpoints vivos em ``src/**/interfaces/router*.py``."""
    assert len(RBAC_ESPERADO) == 45


def test_todos_papeis_cobertos_em_cada_endpoint() -> None:
    """Toda linha da matriz precisa declarar todos os 4 papeis."""
    esperados = {Papel.ANON, Papel.ATENDENTE, Papel.MECANICO, Papel.ADMIN}
    for chave, mapa in RBAC_ESPERADO.items():
        assert set(mapa.keys()) == esperados, (
            f"{chave} nao cobre todos os papeis: {mapa.keys()}"
        )


def test_publicos_permitem_anon_sem_401() -> None:
    """``/saude`` e ``/acompanhamento`` sao publicos — nunca 401 pra anon."""
    saude = RBAC_ESPERADO[("GET", "/api/v1/saude")][Papel.ANON]
    assert saude == 200

    acomp = RBAC_ESPERADO[("GET", "/api/v1/acompanhamento")][Papel.ANON]
    aceitos = acomp if isinstance(acomp, frozenset) else frozenset({acomp})
    assert 401 not in aceitos, "Endpoint publico nao pode exigir autenticacao"


def test_metricas_admin_only() -> None:
    """``/metricas`` deve ser admin-only (403 para papeis menores)."""
    metricas = RBAC_ESPERADO[("GET", "/api/v1/ordens-de-servico/metricas")]
    assert metricas[Papel.ATENDENTE] == 403
    assert metricas[Papel.MECANICO] == 403
    assert metricas[Papel.ADMIN] == 200


def test_estoque_fora_do_atendente() -> None:
    """Router de estoque exige admin/mecanico: atendente sempre 403."""
    assert RBAC_ESPERADO[("GET", "/api/v1/estoque/")][Papel.ATENDENTE] == 403
    assert RBAC_ESPERADO[("POST", "/api/v1/estoque/")][Papel.ATENDENTE] == 403


def test_aprovacao_e_cancelamento_admin_only() -> None:
    """Aprovar orcamento, cancelar e rejeitar complementar sao admin-only."""
    aprovacao = RBAC_ESPERADO[("POST", "/api/v1/ordens-de-servico/{id}/aprovacao")]
    assert aprovacao[Papel.MECANICO] == 403
    assert aprovacao[Papel.ATENDENTE] == 403

    cancelamento = RBAC_ESPERADO[
        ("POST", "/api/v1/ordens-de-servico/{id}/cancelamento")
    ]
    assert cancelamento[Papel.MECANICO] == 403
    assert cancelamento[Papel.ATENDENTE] == 403

    rejeicao = RBAC_ESPERADO[
        ("POST", "/api/v1/ordens-de-servico/{id}/rejeicao-complementar")
    ]
    assert rejeicao[Papel.MECANICO] == 403
    assert rejeicao[Papel.ATENDENTE] == 403


# ---------------- spot-check end-to-end ----------------


@dataclass(frozen=True, slots=True)
class _CfgFake:
    """Espelha o shape de ``FullTestConfig`` sem tocar no .env real."""

    base_url: str = "http://test"
    database_url: str = "postgresql://test"
    admin_email: str = "admin@full-test.local"
    admin_password: str = "AdminFullTest12"
    n_clientes: int = 1
    n_operadores: int = 1
    n_admins: int = 1
    http_timeout: float = 5.0
    seed: int | None = 12


class _ServerFake:
    """Mock minimalista que cobre login + alguns endpoints da matriz.

    Por padrao devolve ``401`` para chamadas sem token e o status que a
    matriz espera para anonimo do endpoint equivalente. Para chamadas com
    token, devolve ``200`` para GET publico e ``403`` onde a matriz prev.
    O objetivo NAO e reproduzir o backend inteiro — e apenas exercitar o
    laco principal da journey sem erros sistemicos.
    """

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        tem_token = "authorization" in {k.lower() for k in request.headers}

        if path == "/api/v1/autenticacao/login" and method == "POST":
            return httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "refresh_token": "ref",
                    "token_type": "bearer",
                },
            )

        # Saude: sempre 200 (publico).
        if path == "/api/v1/saude":
            return httpx.Response(200, json={"status": "ok"})

        # Acompanhamento: publico, devolve 404 (par nao casa).
        if path == "/api/v1/acompanhamento":
            return httpx.Response(
                404,
                json={
                    "erro": {
                        "codigo": "NAO_ENCONTRADO",
                        "mensagem": "Ordem nao encontrada",
                    }
                },
            )

        # Regra geral: sem token -> 401, com token -> 404 (recurso sintetico)
        # ou 403 dependendo do endpoint. Para esse mock basta devolver 404 com
        # token, pois a maioria das celulas aceita 404 como "passou na auth".
        if not tem_token:
            return httpx.Response(
                401,
                json={"detail": "Token de autenticacao nao fornecido"},
            )

        # Endpoints onde a matriz explicitamente espera 403 para o papel
        # enviado. Como o mock nao distingue papeis (todos os tokens vem do
        # mesmo login), devolvemos 404/200 de forma permissiva — o teste
        # abaixo nao tenta casar papel: ele so confirma que a journey faz o
        # laco, loga passos e conclui.
        return httpx.Response(
            200 if method == "GET" else 204,
            json={},
        )


def _fabrica_client_factory(
    transport: httpx.MockTransport,
) -> type[SystemClient]:
    """Mesmo padrao usado por test_atendente/test_mecanico: troca transporte."""

    def fabrica(base_url: str, **kwargs: object) -> SystemClient:
        client = SystemClient(base_url=base_url, **kwargs)  # type: ignore[arg-type]
        client.close()
        client._client = httpx.Client(transport=transport, base_url=base_url)
        return client

    return fabrica  # type: ignore[return-value]


def _fake_config() -> FullTestConfig:
    return _CfgFake()  # type: ignore[return-value]


def test_journey_faz_laco_completo_e_registra_passos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garante que a journey percorre a matriz sem crash sistematico.

    O mock e permissivo: devolve statuses que passam na maioria das
    celulas. A journey pode acusar falhas pra celulas onde o mock nao
    distinguiu papeis — isso e esperado (e por isso o resultado pode
    ser FALHOU ou OK). O que importa e que ``rodar()`` completa, os
    passos ``setup/login-*`` + ``matriz/*`` aparecem no log e nenhum
    crash inesperado interrompe o laco.
    """
    transport = httpx.MockTransport(_ServerFake())

    monkeypatch.setattr(
        "full_test.journeys.rbac_matrix.SystemClient",
        _fabrica_client_factory(transport),
    )

    journey = RbacMatrixJourney(
        config=_fake_config(),
        instance_id="001",
        atendente_email="atendente-00@full-test.local",
        atendente_senha="FullTestSecret123",
        mecanico_email="mecanico-00@full-test.local",
        mecanico_senha="FullTestSecret123",
    )
    resultado = journey.rodar(timeout_s=60.0)

    # O resultado pode ser OK ou FALHOU — o mock nao simula os 403 por
    # papel. O que garantimos aqui e: a journey rodou ate o fim (sem
    # crash), os passos de setup estao todos registrados e o passo
    # resumo da matriz aparece.
    assert resultado.status in {StatusJourney.OK, StatusJourney.FALHOU}
    nomes = {p.nome for p in resultado.passos}
    for esperado in (
        "setup/login-atendente",
        "setup/login-mecanico",
        "setup/login-admin",
    ):
        assert esperado in nomes, f"passo ausente: {esperado!r}"
    # O passo resumo leva o formato "matriz/total-180-ok-N".
    tem_resumo = any(n.startswith("matriz/total-180-ok-") for n in nomes)
    assert tem_resumo, f"passo resumo da matriz ausente; passos={nomes}"
