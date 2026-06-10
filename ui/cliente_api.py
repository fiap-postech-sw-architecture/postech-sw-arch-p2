"""Cliente HTTP centralizado da UI.

Toda chamada ao backend passa por aqui. Responsabilidades:
- injecao automatica de ``Authorization: Bearer <token>``
- mapeamento de erros HTTP para excecoes tipadas
- refresh automatico em 401 com retentativa unica
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast

import httpx

from ui.estado import Papel, Sessao, StateStore, obter_store

if TYPE_CHECKING:
    from collections.abc import Mapping

# JWT compact serialization: header.payload.signature
_JWT_SEGMENTOS = 3


# ----- excecoes tipadas -----


class ApiError(Exception):
    """Base para erros do cliente."""


class NaoAutenticadoError(ApiError):
    """401 persistente (apos refresh falhar)."""


class AcessoNegadoError(ApiError):
    """403 — papel insuficiente."""

    def __init__(self, papel_necessario: str | None = None) -> None:
        super().__init__(f"Acesso negado. Papel necessario: {papel_necessario}")
        self.papel_necessario = papel_necessario


class ValidacaoError(ApiError):
    """422 — preserva ``detail`` do FastAPI."""

    def __init__(self, detalhes: list[dict[str, Any]]) -> None:
        super().__init__("Validacao falhou")
        self.detalhes = detalhes


class RateLimitExcedidoError(ApiError):
    """429 — retry depois do cooldown."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Rate limit. Retry em {retry_after}s")
        self.retry_after = retry_after


class ConflitoEstadoError(ApiError):
    """409 — acao nao permitida no estado atual da OS/recurso.

    Backend mapeia ``ViolacaoRegraDeNegocioException``,
    ``TransicaoStatusInvalidaException``, ``EstoqueInsuficienteException`` e
    ``EntidadeDuplicadaException`` para 409 (ver
    ``src/compartilhado/interfaces/error_handler.py``). Preserva o ``detail``
    do FastAPI para que a UI mostre a regra de negocio violada (ex.: "OS em
    AGUARDANDO_APROVACAO nao permite alterar itens").
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail or "Acao nao permitida no estado atual.")
        self.detail = detail


class BackendIndisponivelError(ApiError):
    """5xx."""


class BackendInacessivelError(ApiError):
    """Connection refused / timeout."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Backend inacessivel em {url}")
        self.url = url


# ----- cliente -----

_ROTAS_SEM_REFRESH = frozenset(
    {"/api/v1/autenticacao/refresh", "/api/v1/autenticacao/login"}
)


class ClienteApi:
    def __init__(
        self,
        base_url: str,
        store: StateStore | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._store = store or obter_store()
        # follow_redirects=True: FastAPI/Starlette emite 307 pra rotas com
        # trailing slash diferente (ex. /api/v1/clientes -> /api/v1/clientes/).
        # Seguir automaticamente evita "Status inesperado 307" em helpers.
        self._client = httpx.Client(
            base_url=self._base_url,
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
        )

    # ----- metodos publicos por verbo -----

    def get(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("GET", path, params=params)

    def post(
        self, path: str, *, json_body: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("POST", path, json_body=json_body)

    def put(
        self, path: str, *, json_body: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("PUT", path, json_body=json_body)

    def patch(
        self, path: str, *, json_body: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("PATCH", path, json_body=json_body)

    def delete(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("DELETE", path, params=params)

    # ----- auth -----

    def login(self, *, email: str, senha: str) -> None:
        """Faz login e salva sessao decodificando papel do JWT."""
        resposta = self._client.post(
            "/api/v1/autenticacao/login",
            json={"email": email, "senha": senha},
        )
        if resposta.status_code != HTTPStatus.OK:
            raise NaoAutenticadoError(f"Login falhou: {resposta.status_code}")
        body = resposta.json()
        access = body["access_token"]
        papel = _extrair_papel_do_jwt(access)
        # NAO fazer fallback para um papel default: um JWT valido do backend
        # sempre tras `papel`. None indica token malformado ou de issuer errado,
        # e defaultar para "admin" (ou qualquer outro) escala privilegios.
        if papel is None:
            raise NaoAutenticadoError("Login falhou: token sem papel valido")
        self._store.salvar_sessao(
            Sessao(
                access_token=access,
                refresh_token=body["refresh_token"],
                email=email,
                papel=papel,
            )
        )

    def logout(self) -> None:
        """Logout best-effort. Limpa sessao local mesmo se backend falhar."""
        token = self._store.token_atual()
        if token:
            # Notificar o backend e best-effort: falha de rede/5xx nao deve
            # impedir limpeza local da sessao.
            with contextlib.suppress(Exception):
                self._client.post(
                    "/api/v1/autenticacao/logout",
                    headers={"Authorization": f"Bearer {token}"},
                )
        self._store.limpar_sessao()

    def tentar_login_sem_salvar(self, *, email: str, senha: str) -> int | None:
        """Testa credenciais sem alterar estado da sessao UI.

        Retorna:
            int: o status HTTP retornado pelo backend (200 se login OK,
                 401 se credenciais invalidas, outros se falha no servidor).
            None: se o backend nao foi alcancado (connect/timeout).

        O chamador distingue 401 (seed ausente) de None (backend offline)
        para evitar mensagens ambiguas quando a rede esta caida.
        """
        try:
            resposta = self._client.post(
                "/api/v1/autenticacao/login",
                json={"email": email, "senha": senha},
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            return None
        return resposta.status_code

    # ----- helpers por contexto: clientes + veiculos -----

    def listar_clientes(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.get("/api/v1/clientes", params={"offset": offset, "limit": limit}),
        )

    def obter_cliente(self, cliente_id: str) -> dict[str, Any]:
        return cast("dict[str, Any]", self.get(f"/api/v1/clientes/{cliente_id}"))

    def criar_cliente(self, body: Mapping[str, Any]) -> dict[str, Any]:
        return cast("dict[str, Any]", self.post("/api/v1/clientes", json_body=body))

    def atualizar_cliente(
        self, cliente_id: str, body: Mapping[str, Any]
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.put(f"/api/v1/clientes/{cliente_id}", json_body=body),
        )

    def desativar_cliente(self, cliente_id: str) -> None:
        self.delete(f"/api/v1/clientes/{cliente_id}")

    def listar_veiculos(self, cliente_id: str) -> list[dict[str, Any]]:
        return cast(
            "list[dict[str, Any]]",
            self.get(f"/api/v1/clientes/{cliente_id}/veiculos"),
        )

    def adicionar_veiculo(
        self, cliente_id: str, body: Mapping[str, Any]
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.post(f"/api/v1/clientes/{cliente_id}/veiculos", json_body=body),
        )

    def remover_veiculo(self, cliente_id: str, veiculo_id: str) -> None:
        self.delete(f"/api/v1/clientes/{cliente_id}/veiculos/{veiculo_id}")

    # servicos

    def listar_servicos(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.get("/api/v1/servicos", params={"offset": offset, "limit": limit}),
        )

    def criar_servico(self, body: Mapping[str, Any]) -> dict[str, Any]:
        return cast("dict[str, Any]", self.post("/api/v1/servicos", json_body=body))

    def atualizar_servico(
        self, servico_id: str, body: Mapping[str, Any]
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.put(f"/api/v1/servicos/{servico_id}", json_body=body),
        )

    def desativar_servico(self, servico_id: str) -> None:
        self.delete(f"/api/v1/servicos/{servico_id}")

    # estoque

    def listar_estoque(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.get("/api/v1/estoque", params={"offset": offset, "limit": limit}),
        )

    def criar_item_estoque(self, body: Mapping[str, Any]) -> dict[str, Any]:
        return cast("dict[str, Any]", self.post("/api/v1/estoque", json_body=body))

    def atualizar_item_estoque(
        self, item_id: str, body: Mapping[str, Any]
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.put(f"/api/v1/estoque/{item_id}", json_body=body),
        )

    def ajustar_quantidade(self, item_id: str, nova_quantidade: int) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.patch(
                f"/api/v1/estoque/{item_id}/quantidade",
                json_body={"nova_quantidade": nova_quantidade},
            ),
        )

    def desativar_item_estoque(self, item_id: str) -> None:
        self.delete(f"/api/v1/estoque/{item_id}")

    # LGPD

    def exportar_dados_cliente(self, cliente_id: str) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.get(f"/api/v1/clientes/{cliente_id}/dados-pessoais/exportar"),
        )

    def excluir_dados_cliente(self, cliente_id: str) -> None:
        self.delete(f"/api/v1/clientes/{cliente_id}/dados-pessoais")

    def registrar_consentimento(self, cliente_id: str, tipo: str) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.post(
                f"/api/v1/clientes/{cliente_id}/consentimento",
                json_body={"tipo": tipo},
            ),
        )

    def revogar_consentimento(self, cliente_id: str, tipo: str) -> None:
        self.delete(
            f"/api/v1/clientes/{cliente_id}/consentimento",
            params={"tipo": tipo},
        )

    # acompanhamento publico (sem auth)

    def acompanhamento_publico(self, *, placa: str, documento: str) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.get(
                "/api/v1/acompanhamento",
                params={"placa": placa, "documento": documento},
            ),
        )

    # ordens de servico

    def listar_ordens(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.get(
                "/api/v1/ordens-de-servico",
                params={"offset": offset, "limit": limit},
            ),
        )

    def obter_ordem(self, ordem_id: str) -> dict[str, Any]:
        return cast("dict[str, Any]", self.get(f"/api/v1/ordens-de-servico/{ordem_id}"))

    def criar_ordem(self, cliente_id: str, veiculo_id: str) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.post(
                "/api/v1/ordens-de-servico",
                json_body={"cliente_id": cliente_id, "veiculo_id": veiculo_id},
            ),
        )

    def adicionar_item_ordem(
        self, ordem_id: str, body: Mapping[str, Any]
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.post(f"/api/v1/ordens-de-servico/{ordem_id}/itens", json_body=body),
        )

    def remover_item_ordem(self, ordem_id: str, item_id: str) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.delete(f"/api/v1/ordens-de-servico/{ordem_id}/itens/{item_id}"),
        )

    def executar_transicao(
        self,
        ordem_id: str,
        endpoint: str,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Executa uma transicao de estado (ex endpoint='/diagnostico')."""
        return cast(
            "dict[str, Any]",
            self.post(
                f"/api/v1/ordens-de-servico/{ordem_id}{endpoint}",
                json_body=body,
            ),
        )

    def metricas_ordens(self) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.get("/api/v1/ordens-de-servico/metricas"),
        )

    # ----- interno -----

    def _request(
        self,
        metodo: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        _ja_tentou_refresh: bool = False,
    ) -> dict[str, Any] | list[Any]:
        headers: dict[str, str] = {}
        token = self._store.token_atual()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            resposta = self._client.request(
                metodo, path, headers=headers, params=params, json=json_body
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise BackendInacessivelError(self._base_url) from exc

        if (
            resposta.status_code == HTTPStatus.UNAUTHORIZED
            and not _ja_tentou_refresh
            and path not in _ROTAS_SEM_REFRESH
            and self._store.refresh_token_atual()
        ):
            if self._tentar_refresh():
                return self._request(
                    metodo,
                    path,
                    params=params,
                    json_body=json_body,
                    _ja_tentou_refresh=True,
                )
            # refresh falhou: limpa sessao e propaga
            self._store.limpar_sessao()
            raise NaoAutenticadoError("Sessao expirada")

        return self._interpretar_resposta(resposta)

    def _tentar_refresh(self) -> bool:
        """Executa POST /refresh uma vez. Retorna True se atualizou tokens."""
        refresh_token = self._store.refresh_token_atual()
        if not refresh_token:
            return False
        try:
            resposta = self._client.post(
                "/api/v1/autenticacao/refresh",
                json={"refresh_token": refresh_token},
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
        if resposta.status_code != HTTPStatus.OK:
            return False
        body = resposta.json()
        # Preserva email e papel atuais; so troca os tokens. Se papel estiver
        # ausente (sessao corrompida), aborta o refresh em vez de escolher um
        # default — qualquer escolha aqui pode escalar privilegios indevidamente.
        email = self._store.email_atual()
        papel = self._store.papel_atual()
        if email is None or papel is None:
            return False
        self._store.salvar_sessao(
            Sessao(
                access_token=body["access_token"],
                refresh_token=body["refresh_token"],
                email=email,
                papel=papel,
            )
        )
        return True

    def _interpretar_resposta(
        self, resposta: httpx.Response
    ) -> dict[str, Any] | list[Any]:
        status = resposta.status_code
        if HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
            if status == HTTPStatus.NO_CONTENT or not resposta.content:
                return {}
            return resposta.json()  # type: ignore[no-any-return]
        if status == HTTPStatus.UNAUTHORIZED:
            raise NaoAutenticadoError("Nao autenticado")
        if status == HTTPStatus.FORBIDDEN:
            detail = _extrair_detail(resposta)
            raise AcessoNegadoError(detail)
        if status == HTTPStatus.CONFLICT:
            raise ConflitoEstadoError(_extrair_detail(resposta) or "")
        if status == HTTPStatus.UNPROCESSABLE_ENTITY:
            body = resposta.json()
            detalhes = body.get("detail", []) if isinstance(body, dict) else []
            raise ValidacaoError(detalhes if isinstance(detalhes, list) else [])
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            retry = int(resposta.headers.get("Retry-After", "60"))
            raise RateLimitExcedidoError(retry_after=retry)
        if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise BackendIndisponivelError(f"Erro {status}")
        raise ApiError(f"Status inesperado {status}")


def _extrair_detail(resposta: httpx.Response) -> str | None:
    try:
        body = resposta.json()
    except json.JSONDecodeError:
        return None
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
    return None


def _extrair_papel_do_jwt(token: str) -> Papel | None:
    """Decodifica payload do JWT sem verificar assinatura."""
    try:
        partes = token.split(".")
        if len(partes) != _JWT_SEGMENTOS:
            return None
        padded = partes[1] + "=" * (-len(partes[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        papel = payload.get("papel")
        if isinstance(papel, str) and papel in {"admin", "atendente", "mecanico"}:
            return cast("Papel", papel)
    except (ValueError, json.JSONDecodeError, binascii.Error, KeyError):
        # Token malformado, base64 invalido, ou JSON quebrado — fail soft.
        return None
    return None
