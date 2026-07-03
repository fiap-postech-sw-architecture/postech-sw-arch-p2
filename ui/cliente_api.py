"""Cliente HTTP centralizado da UI.

Toda chamada ao backend passa por aqui. Responsabilidades:
- injecao automatica de ``Authorization: Bearer <token>``
- mapeamento de erros HTTP para excecoes tipadas
- refresh automatico em 401 com retentativa unica
"""

from __future__ import annotations

import contextlib
import json
import threading
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast
from weakref import WeakKeyDictionary

import httpx
import jwt

from ui.estado import PAPEIS_VALIDOS, Papel, Sessao, StateStore, obter_store

if TYPE_CHECKING:
    from collections.abc import Mapping


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


class NaoEncontradoError(ApiError):
    """404 — recurso inexistente ou removido."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or "Recurso nao encontrado")


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

# Lock de refresh por StateStore: ``obter_api()`` cria um ClienteApi novo a
# cada chamada, entao um lock por instancia nao serializaria nada — a unidade
# compartilhada entre handlers concorrentes e o store. WeakKey pra nao segurar
# stores de teste vivos pra sempre.
_REFRESH_LOCKS: WeakKeyDictionary[StateStore, threading.Lock] = WeakKeyDictionary()
_REFRESH_LOCKS_GUARD = threading.Lock()


def _refresh_lock_do_store(store: StateStore) -> threading.Lock:
    with _REFRESH_LOCKS_GUARD:
        lock = _REFRESH_LOCKS.get(store)
        if lock is None:
            lock = threading.Lock()
            _REFRESH_LOCKS[store] = lock
        return lock


def criar_http_client(
    base_url: str,
    *,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 10.0,
) -> httpx.Client:
    """Constroi o ``httpx.Client`` com a configuracao padrao do ClienteApi.

    Exposto pra que ``ui.app`` crie UM client compartilhado de processo
    (httpx.Client e thread-safe e reusa conexoes) em vez de um por request.

    follow_redirects=True: FastAPI/Starlette emite 307 pra rotas com
    trailing slash diferente (ex. /api/v1/clientes -> /api/v1/clientes/).
    Seguir automaticamente evita "Status inesperado 307" em helpers.
    """
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
    )


class ClienteApi:
    def __init__(
        self,
        base_url: str,
        store: StateStore | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._store = store or obter_store()
        # ``http_client`` injetado (ui.app) e compartilhado — quem cria fecha.
        # Sem injecao (testes com ``transport``), cria um proprio.
        self._client = http_client or criar_http_client(
            self._base_url, transport=transport, timeout=timeout
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
        try:
            resposta = self._client.post(
                "/api/v1/autenticacao/login",
                json={"email": email, "senha": senha},
            )
        except httpx.TransportError as exc:
            raise BackendInacessivelError(self._base_url) from exc
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
        sessao = self._store.sessao_atual()
        if sessao:
            self.revogar_sessao(sessao)
        self._store.limpar_sessao()

    def revogar_sessao(self, sessao: Sessao) -> None:
        """Revoga uma sessao especifica no backend, sem tocar o store local.

        Best-effort: falha de rede/5xx nao deve impedir o fluxo do chamador.
        O backend so revoga o refresh token quando ele vem no body
        (``refresh_token`` opcional em POST /logout, issue #118) — sem o body
        o logout invalidava apenas o access token e o refresh continuava
        utilizavel ate expirar.
        """
        with contextlib.suppress(Exception):
            self._client.post(
                "/api/v1/autenticacao/logout",
                headers={"Authorization": f"Bearer {sessao.access_token}"},
                json={"refresh_token": sessao.refresh_token},
            )

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
        except httpx.TransportError:
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

    def listar_ordens(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        incluir_encerradas: bool = False,
    ) -> dict[str, Any]:
        # RF-023: por padrao o backend exclui FINALIZADA/ENTREGUE/CANCELADA;
        # ``incluir_encerradas=True`` anexa as encerradas (ordem do backend).
        return cast(
            "dict[str, Any]",
            self.get(
                "/api/v1/ordens-de-servico",
                params={
                    "offset": offset,
                    "limit": limit,
                    "incluir_encerradas": incluir_encerradas,
                },
            ),
        )

    def obter_ordem(self, ordem_id: str) -> dict[str, Any]:
        return cast("dict[str, Any]", self.get(f"/api/v1/ordens-de-servico/{ordem_id}"))

    def criar_ordem(
        self,
        cliente_id: str,
        veiculo_id: str,
        *,
        servicos: list[dict[str, Any]] | None = None,
        pecas: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        # RF-020: servicos/pecas opcionais na criacao. O backend usa
        # ``extra='forbid'``, entao so incluimos as chaves com valor — sem
        # itens o corpo fica byte-identico ao da fase 1.
        body: dict[str, Any] = {"cliente_id": cliente_id, "veiculo_id": veiculo_id}
        if servicos is not None:
            body["servicos"] = servicos
        if pecas is not None:
            body["pecas"] = pecas
        return cast(
            "dict[str, Any]",
            self.post("/api/v1/ordens-de-servico", json_body=body),
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
        except httpx.TransportError as exc:
            # TransportError cobre connect/timeout/protocolo/leitura — qualquer
            # falha de transporte vira a mesma mensagem amigavel de backend
            # fora do ar, em vez de um traceback httpx cru na pagina.
            raise BackendInacessivelError(self._base_url) from exc

        if (
            resposta.status_code == HTTPStatus.UNAUTHORIZED
            and not _ja_tentou_refresh
            and path not in _ROTAS_SEM_REFRESH
            and self._store.refresh_token_atual()
        ):
            if self._tentar_refresh(token_expirado=token):
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

    def _tentar_refresh(self, token_expirado: str | None = None) -> bool:
        """Executa POST /refresh serializado por store. True se ha tokens novos.

        Serializacao via lock por store: dois handlers concorrentes que tomam
        401 com o mesmo access token expirado nao podem postar o mesmo refresh
        token duas vezes — com rotacao single-use no backend, o segundo POST
        falharia e derrubaria a sessao. Sob o lock, re-le o estado atual:
        se outro thread ja renovou (access token mudou), reaproveita a sessao
        nova sem gastar outra rotacao.
        """
        with _refresh_lock_do_store(self._store):
            if token_expirado is not None and self._store.token_atual() not in (
                None,
                token_expirado,
            ):
                # Outro thread renovou enquanto esperavamos o lock.
                return True
            # Re-le o refresh token DENTRO do lock — nunca postar valor stale.
            refresh_token = self._store.refresh_token_atual()
            if not refresh_token:
                return False
            try:
                resposta = self._client.post(
                    "/api/v1/autenticacao/refresh",
                    json={"refresh_token": refresh_token},
                )
            except httpx.TransportError:
                return False
            if resposta.status_code != HTTPStatus.OK:
                return False
            body = resposta.json()
            # Preserva email e papel atuais; so troca os tokens. Se papel estiver
            # ausente (sessao corrompida), aborta o refresh em vez de escolher um
            # default — qualquer escolha aqui pode escalar privilegios
            # indevidamente.
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
            # 401 que chegou ate aqui e terminal (refresh ja tentado, sem
            # refresh token ou rota sem refresh): limpa a sessao pra UI nao
            # reter tokens mortos no storage — o handler da pagina captura
            # NaoAutenticadoError e redireciona pro /login.
            self._store.limpar_sessao()
            raise NaoAutenticadoError("Nao autenticado")
        if status == HTTPStatus.FORBIDDEN:
            detail = _extrair_detail(resposta)
            raise AcessoNegadoError(detail)
        if status == HTTPStatus.NOT_FOUND:
            raise NaoEncontradoError(_extrair_detail(resposta))
        if status == HTTPStatus.CONFLICT:
            raise ConflitoEstadoError(_extrair_detail(resposta) or "")
        if status == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise ValidacaoError(_detalhes_validacao(resposta))
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            raise RateLimitExcedidoError(retry_after=_retry_after(resposta))
        if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise BackendIndisponivelError(f"Erro {status}")
        raise ApiError(f"Status inesperado {status}")


def _detalhes_validacao(resposta: httpx.Response) -> list[dict[str, Any]]:
    """Extrai o ``detail`` de um 422 com fallback pra body nao-JSON.

    Proxy/gateway pode emitir 422 sem JSON — lista vazia em vez de estourar
    ``JSONDecodeError`` mascarando o erro original.
    """
    try:
        body = resposta.json()
    except json.JSONDecodeError:
        return []
    detalhes = body.get("detail", []) if isinstance(body, dict) else []
    return detalhes if isinstance(detalhes, list) else []


def _retry_after(resposta: httpx.Response) -> int:
    """Le o header Retry-After de um 429.

    Pode vir como HTTP-date (RFC 9110) ou lixo — nesses casos cai no default
    de 60s em vez de ValueError.
    """
    try:
        return int(resposta.headers.get("Retry-After", "60"))
    except ValueError:
        return 60


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
    """Decodifica payload do JWT sem verificar assinatura (deliberado).

    A UI confia no backend que emitiu o token e so usa o papel para
    exibicao/roteamento local — a autorizacao real e verificada pelo
    backend, que valida a assinatura a cada request.
    """
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        # Token malformado (segmentos, base64 ou JSON quebrados) — fail soft.
        return None
    papel = payload.get("papel")
    if isinstance(papel, str) and papel in PAPEIS_VALIDOS:
        return cast("Papel", papel)
    return None
