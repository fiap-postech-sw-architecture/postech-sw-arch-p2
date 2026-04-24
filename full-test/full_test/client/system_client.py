"""SystemClient: facade tipada sobre os 46 endpoints da API PyTStop.

Thread-safety: instancias NAO sao thread-safe (``httpx.Client`` mantem pool
proprio). Crie uma instancia por thread no orchestrator (step 13). Ou use
``Lock`` explicito em cenarios onde varias threads compartilhem uma mesma
credencial — mas o padrao do orchestrator e 1 cliente por journey.

Envelope de erro:

- Handler padrao (``src/compartilhado/interfaces/error_handler.py``):
  ``{"erro": {"codigo", "mensagem", "id_requisicao"}}``
- FastAPI/HTTPBearer (401) e validacao de body (422): ``{"detail": ...}``
- SlowAPI (429): ``{"error": "Rate limit exceeded: ..."}``

O ``_raise_for_status`` extrai ``detail`` cobrindo os tres formatos; para a
correlation id ele prefere o header ``X-Request-ID`` (injetado pelo
``SecurityHeadersMiddleware``) e usa o ``id_requisicao`` do envelope como
fallback.
"""

from __future__ import annotations

import random
import time
import uuid
from typing import TYPE_CHECKING, Any

import httpx

from full_test.client import models
from full_test.client.errors import RateLimitError, erro_para

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal
    from uuid import UUID

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES_ON_429 = 8
# Backoff: base * 2**tentativa + jitter. Evita sincronizacao de N threads
# batendo juntas no endpoint de login/refresh apos Retry-After==0.
_BACKOFF_BASE = 0.5
# Rate limits da API vao de 5/min a 10/min por endpoint. O cap precisa ser
# maior que 60s pra absorver uma janela completa quando varias threads
# batem simultaneamente; antes em 10s causava falhas residuais mesmo com
# retries (8 x 10s = 80s dividido por backoff exponencial/jitter, insuficiente
# para tipo "5/min").
_BACKOFF_MAX = 70.0


class SystemClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        correlation_prefix: str = "full-test",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": "full-test-harness/1.0"},
        )
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._correlation_prefix = correlation_prefix

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SystemClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------------- credenciais ----------------

    @property
    def token(self) -> str | None:
        return self._token

    def set_token(self, access_token: str, refresh_token: str | None = None) -> None:
        """Injeta credenciais pre-obtidas (usado por journeys rodando em threads).

        Evita o overhead de um segundo login por thread quando a mesma credencial
        ja foi negociada e esta valida.
        """
        self._token = access_token
        self._refresh_token = refresh_token

    def clear_token(self) -> None:
        """Remove credenciais do cliente (usado para exercitar endpoints publicos)."""
        self._token = None
        self._refresh_token = None

    def sem_autenticacao(self) -> SystemClient:
        """Retorna uma nova instancia sem token, para exercitar endpoints publicos.

        O caller e responsavel por ``close()`` na instancia retornada (ou usar
        ``with``). Compartilha a mesma base_url e prefixo de correlation id.
        """
        return SystemClient(
            self._base_url,
            timeout=self._timeout,
            correlation_prefix=self._correlation_prefix,
        )

    # ---------------- transport ----------------

    def _headers(self, *, authenticated: bool) -> dict[str, str]:
        headers: dict[str, str] = {
            "X-Correlation-ID": f"{self._correlation_prefix}-{uuid.uuid4().hex[:12]}",
        }
        if authenticated:
            if self._token is None:
                raise RuntimeError(
                    "SystemClient nao autenticado; chame login(...) antes "
                    "de operacoes protegidas."
                )
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        headers = self._headers(authenticated=authenticated)
        response: httpx.Response | None = None
        for tentativa in range(_MAX_RETRIES_ON_429 + 1):
            response = self._client.request(
                method, path, json=json, params=params, headers=headers
            )
            if response.status_code != 429:
                break
            if tentativa == _MAX_RETRIES_ON_429:
                break
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            espera = (
                retry_after
                if retry_after is not None
                else _BACKOFF_BASE * (2**tentativa) + random.uniform(0, 0.25)  # noqa: S311
            )
            time.sleep(min(espera, _BACKOFF_MAX))
        # Garantido: response foi atribuido em ao menos uma iteracao
        assert response is not None  # noqa: S101
        if response.status_code >= 400:
            self._raise_for_status(response)
        return response

    def _raise_for_status(self, response: httpx.Response) -> None:
        correlation_id, detail = _extrair_detalhe(response)
        if response.status_code == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            raise RateLimitError(
                status_code=response.status_code,
                detail=detail,
                correlation_id=correlation_id,
                retry_after_seconds=retry_after,
            )
        err_cls = erro_para(response.status_code)
        raise err_cls(
            status_code=response.status_code,
            detail=detail,
            correlation_id=correlation_id,
        )

    # ---------------- autenticacao ----------------

    def login(self, *, email: str, senha: str) -> models.TokenResponse:
        response = self._request(
            "POST",
            "/api/v1/autenticacao/login",
            json={"email": email, "senha": senha},
            authenticated=False,
        )
        tokens = models.TokenResponse._parse(response.json())
        self._token = tokens.access_token
        self._refresh_token = tokens.refresh_token
        return tokens

    def logout(self) -> None:
        self._request("POST", "/api/v1/autenticacao/logout")
        self._token = None
        self._refresh_token = None

    def refresh(self) -> models.TokenResponse:
        if self._refresh_token is None:
            raise RuntimeError("Sem refresh_token; faca login primeiro.")
        response = self._request(
            "POST",
            "/api/v1/autenticacao/refresh",
            json={"refresh_token": self._refresh_token},
            authenticated=False,
        )
        tokens = models.TokenResponse._parse(response.json())
        self._token = tokens.access_token
        self._refresh_token = tokens.refresh_token
        return tokens

    def registrar(self, *, email: str, senha: str) -> models.UsuarioResponse:
        """Cria usuario ADMIN (API nao suporta outros papeis via DTO).

        O endpoint ``POST /api/v1/autenticacao/registrar`` sempre cria papel
        ADMIN porque ``Usuario.criar`` tem default ``papel=Papel.ADMIN`` e
        ``RegistrarDTO`` nao expoe ``papel``. Para seedar ATENDENTE/MECANICO,
        veja ``full_test/seeders/seed_usuarios.py`` (step 3).

        Requer token de admin ativo no cliente.
        """
        response = self._request(
            "POST",
            "/api/v1/autenticacao/registrar",
            json={"email": email, "senha": senha},
        )
        return models.UsuarioResponse._parse(response.json())

    # ---------------- clientes ----------------

    def criar_cliente(
        self,
        *,
        nome: str,
        documento: str,
        tipo_documento: str,
        contato: str,
    ) -> models.ClienteResponse:
        resp = self._request(
            "POST",
            "/api/v1/clientes/",
            json={
                "nome": nome,
                "documento": documento,
                "tipo_documento": tipo_documento,
                "contato": contato,
            },
        )
        return models.ClienteResponse._parse(resp.json())

    def listar_clientes(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> models.ClienteListaResponse:
        resp = self._request(
            "GET", "/api/v1/clientes/", params={"offset": offset, "limit": limit}
        )
        return models.ClienteListaResponse._parse(resp.json())

    def obter_cliente(self, cliente_id: UUID) -> models.ClienteResponse:
        resp = self._request("GET", f"/api/v1/clientes/{cliente_id}")
        return models.ClienteResponse._parse(resp.json())

    def atualizar_cliente(
        self,
        cliente_id: UUID,
        *,
        nome: str,
        contato: str,
    ) -> models.ClienteResponse:
        resp = self._request(
            "PUT",
            f"/api/v1/clientes/{cliente_id}",
            json={"nome": nome, "contato": contato},
        )
        return models.ClienteResponse._parse(resp.json())

    def desativar_cliente(self, cliente_id: UUID) -> None:
        self._request("DELETE", f"/api/v1/clientes/{cliente_id}")

    def adicionar_veiculo(
        self,
        cliente_id: UUID,
        *,
        placa: str,
        marca: str,
        modelo: str,
        ano: int,
    ) -> models.VeiculoResponse:
        resp = self._request(
            "POST",
            f"/api/v1/clientes/{cliente_id}/veiculos",
            json={"placa": placa, "marca": marca, "modelo": modelo, "ano": ano},
        )
        return models.VeiculoResponse._parse(resp.json())

    def listar_veiculos(self, cliente_id: UUID) -> list[models.VeiculoResponse]:
        resp = self._request("GET", f"/api/v1/clientes/{cliente_id}/veiculos")
        return [models.VeiculoResponse._parse(v) for v in resp.json()]

    def remover_veiculo(self, cliente_id: UUID, veiculo_id: UUID) -> None:
        self._request(
            "DELETE",
            f"/api/v1/clientes/{cliente_id}/veiculos/{veiculo_id}",
        )

    def exportar_dados_pessoais(
        self,
        cliente_id: UUID,
    ) -> models.DadosPessoaisResponse:
        resp = self._request("GET", f"/api/v1/clientes/{cliente_id}/dados-pessoais")
        return models.DadosPessoaisResponse._parse(resp.json())

    def excluir_dados_pessoais(self, cliente_id: UUID) -> None:
        self._request("DELETE", f"/api/v1/clientes/{cliente_id}/dados-pessoais")

    def registrar_consentimento(
        self,
        cliente_id: UUID,
        *,
        tipo: str,
    ) -> models.ConsentimentoResponse:
        resp = self._request(
            "POST",
            f"/api/v1/clientes/{cliente_id}/consentimento",
            json={"tipo": tipo},
        )
        return models.ConsentimentoResponse._parse(resp.json())

    def revogar_consentimento(self, cliente_id: UUID, *, tipo: str) -> None:
        self._request(
            "DELETE",
            f"/api/v1/clientes/{cliente_id}/consentimento",
            params={"tipo": tipo},
        )

    # ---------------- catalogo de servicos ----------------

    def criar_servico(
        self,
        *,
        nome: str,
        descricao: str,
        preco: Decimal,
    ) -> models.ServicoResponse:
        resp = self._request(
            "POST",
            "/api/v1/servicos/",
            json={"nome": nome, "descricao": descricao, "preco": f"{preco:.2f}"},
        )
        return models.ServicoResponse._parse(resp.json())

    def listar_servicos(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> models.ServicoListaResponse:
        resp = self._request(
            "GET", "/api/v1/servicos/", params={"offset": offset, "limit": limit}
        )
        return models.ServicoListaResponse._parse(resp.json())

    def obter_servico(self, servico_id: UUID) -> models.ServicoResponse:
        resp = self._request("GET", f"/api/v1/servicos/{servico_id}")
        return models.ServicoResponse._parse(resp.json())

    def atualizar_servico(
        self,
        servico_id: UUID,
        *,
        nome: str,
        descricao: str,
        preco: Decimal,
    ) -> models.ServicoResponse:
        resp = self._request(
            "PUT",
            f"/api/v1/servicos/{servico_id}",
            json={"nome": nome, "descricao": descricao, "preco": f"{preco:.2f}"},
        )
        return models.ServicoResponse._parse(resp.json())

    def desativar_servico(self, servico_id: UUID) -> None:
        self._request("DELETE", f"/api/v1/servicos/{servico_id}")

    # ---------------- estoque ----------------

    def criar_item_estoque(
        self,
        *,
        nome: str,
        descricao: str,
        quantidade: int,
        preco_unitario: Decimal,
    ) -> models.ItemEstoqueResponse:
        resp = self._request(
            "POST",
            "/api/v1/estoque/",
            json={
                "nome": nome,
                "descricao": descricao,
                "quantidade": quantidade,
                "preco_unitario": f"{preco_unitario:.2f}",
            },
        )
        return models.ItemEstoqueResponse._parse(resp.json())

    def listar_itens_estoque(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> models.ItemEstoqueListaResponse:
        resp = self._request(
            "GET", "/api/v1/estoque/", params={"offset": offset, "limit": limit}
        )
        return models.ItemEstoqueListaResponse._parse(resp.json())

    def obter_item_estoque(self, item_id: UUID) -> models.ItemEstoqueResponse:
        resp = self._request("GET", f"/api/v1/estoque/{item_id}")
        return models.ItemEstoqueResponse._parse(resp.json())

    def atualizar_item_estoque(
        self,
        item_id: UUID,
        *,
        nome: str,
        descricao: str,
        preco_unitario: Decimal,
    ) -> models.ItemEstoqueResponse:
        resp = self._request(
            "PUT",
            f"/api/v1/estoque/{item_id}",
            json={
                "nome": nome,
                "descricao": descricao,
                "preco_unitario": f"{preco_unitario:.2f}",
            },
        )
        return models.ItemEstoqueResponse._parse(resp.json())

    def ajustar_quantidade_estoque(
        self,
        item_id: UUID,
        *,
        nova_quantidade: int,
    ) -> models.ItemEstoqueResponse:
        resp = self._request(
            "PATCH",
            f"/api/v1/estoque/{item_id}/quantidade",
            json={"nova_quantidade": nova_quantidade},
        )
        return models.ItemEstoqueResponse._parse(resp.json())

    def desativar_item_estoque(self, item_id: UUID) -> None:
        self._request("DELETE", f"/api/v1/estoque/{item_id}")

    # ---------------- ordem de servico ----------------

    def criar_ordem(
        self,
        *,
        cliente_id: UUID,
        veiculo_id: UUID,
    ) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "POST",
            "/api/v1/ordens-de-servico/",
            json={"cliente_id": str(cliente_id), "veiculo_id": str(veiculo_id)},
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def listar_ordens(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> models.OrdemListaResponse:
        resp = self._request(
            "GET",
            "/api/v1/ordens-de-servico/",
            params={"offset": offset, "limit": limit},
        )
        return models.OrdemListaResponse._parse(resp.json())

    def obter_metricas(self) -> models.MetricasResponse:
        resp = self._request("GET", "/api/v1/ordens-de-servico/metricas")
        return models.MetricasResponse._parse(resp.json())

    def obter_ordem(self, ordem_id: UUID) -> models.OrdemDeServicoResponse:
        resp = self._request("GET", f"/api/v1/ordens-de-servico/{ordem_id}")
        return models.OrdemDeServicoResponse._parse(resp.json())

    def adicionar_item_ordem(
        self,
        ordem_id: UUID,
        *,
        servico_catalogo_id: UUID,
        item_estoque_id: UUID | None,
        descricao: str,
        quantidade: int,
    ) -> models.OrdemDeServicoResponse:
        payload: dict[str, object] = {
            "servico_catalogo_id": str(servico_catalogo_id),
            "descricao": descricao,
            "quantidade": quantidade,
        }
        if item_estoque_id is not None:
            payload["item_estoque_id"] = str(item_estoque_id)
        resp = self._request(
            "POST", f"/api/v1/ordens-de-servico/{ordem_id}/itens", json=payload
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def remover_item_ordem(
        self,
        ordem_id: UUID,
        item_id: UUID,
    ) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "DELETE",
            f"/api/v1/ordens-de-servico/{ordem_id}/itens/{item_id}",
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def iniciar_diagnostico(
        self,
        ordem_id: UUID,
    ) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "POST", f"/api/v1/ordens-de-servico/{ordem_id}/diagnostico"
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def gerar_orcamento(self, ordem_id: UUID) -> models.OrdemDeServicoResponse:
        resp = self._request("POST", f"/api/v1/ordens-de-servico/{ordem_id}/orcamento")
        return models.OrdemDeServicoResponse._parse(resp.json())

    def aprovar_orcamento(self, ordem_id: UUID) -> models.OrdemDeServicoResponse:
        resp = self._request("POST", f"/api/v1/ordens-de-servico/{ordem_id}/aprovacao")
        return models.OrdemDeServicoResponse._parse(resp.json())

    def finalizar_servico(self, ordem_id: UUID) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "POST", f"/api/v1/ordens-de-servico/{ordem_id}/finalizacao"
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def registrar_entrega(self, ordem_id: UUID) -> models.OrdemDeServicoResponse:
        resp = self._request("POST", f"/api/v1/ordens-de-servico/{ordem_id}/entrega")
        return models.OrdemDeServicoResponse._parse(resp.json())

    def cancelar_ordem(
        self,
        ordem_id: UUID,
        *,
        motivo: str,
    ) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "POST",
            f"/api/v1/ordens-de-servico/{ordem_id}/cancelamento",
            json={"motivo": motivo},
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def gerar_orcamento_complementar(
        self,
        ordem_id: UUID,
    ) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "POST",
            f"/api/v1/ordens-de-servico/{ordem_id}/orcamento-complementar",
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def aprovar_orcamento_complementar(
        self,
        ordem_id: UUID,
    ) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "POST",
            f"/api/v1/ordens-de-servico/{ordem_id}/aprovacao-complementar",
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    def rejeitar_orcamento_complementar(
        self,
        ordem_id: UUID,
    ) -> models.OrdemDeServicoResponse:
        resp = self._request(
            "POST",
            f"/api/v1/ordens-de-servico/{ordem_id}/rejeicao-complementar",
        )
        return models.OrdemDeServicoResponse._parse(resp.json())

    # ---------------- publicos (sem autenticacao) ----------------

    def saude(self) -> dict[str, str]:
        resp = self._request("GET", "/api/v1/saude", authenticated=False)
        data = resp.json()
        return {k: str(v) for k, v in data.items()}

    def consultar_acompanhamento(
        self,
        *,
        placa: str,
        documento: str,
    ) -> models.AcompanhamentoResponse:
        """Consulta publica — NAO requer autenticacao. Usado pelo cliente final."""
        resp = self._request(
            "GET",
            "/api/v1/acompanhamento",
            params={"placa": placa, "documento": documento},
            authenticated=False,
        )
        return models.AcompanhamentoResponse._parse(resp.json())


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _extrair_detalhe(response: httpx.Response) -> tuple[str | None, str]:
    """Extrai ``(correlation_id, detail_string)`` do ``response`` de erro.

    Cobre as tres shapes de envelope usadas pela API:

    1. ``{"erro": {"codigo", "mensagem", "id_requisicao"}}`` — handler padrao.
    2. ``{"detail": str | list}`` — FastAPI/HTTPBearer (401) e validacao de body
       (422, onde ``detail`` e uma lista).
    3. ``{"error": "..."}`` — SlowAPI (429).

    Prefere ``X-Request-ID`` do header como correlation id (injetado pelo
    ``SecurityHeadersMiddleware``); usa ``erro.id_requisicao`` como fallback.
    """
    header_cid = response.headers.get("X-Request-ID") or response.headers.get(
        "X-Correlation-ID"
    )
    detail: str = response.text or ""
    body_cid: str | None = None
    try:
        body: Any = response.json()
    except ValueError:
        return header_cid, detail

    if isinstance(body, dict):
        if "erro" in body and isinstance(body["erro"], dict):
            envelope = body["erro"]
            codigo = envelope.get("codigo")
            mensagem = envelope.get("mensagem") or ""
            body_cid = (
                str(envelope["id_requisicao"])
                if envelope.get("id_requisicao") is not None
                else None
            )
            detail = f"{codigo}: {mensagem}" if codigo else str(mensagem)
        elif "detail" in body:
            raw = body["detail"]
            detail = _stringify_detail(raw)
        elif "error" in body:
            detail = str(body["error"])
        else:
            detail = str(body)
    else:
        detail = str(body)

    return (header_cid or body_cid), detail


def _stringify_detail(raw: Any) -> str:
    """Converte ``detail`` de ``{"detail": ...}`` numa string curta e util.

    422 serializa ``detail`` como lista de objetos com ``loc``/``msg``/``type``;
    achatamos em ``loc: msg`` para facilitar debug.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        linhas: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                loc = ".".join(str(x) for x in item.get("loc", []))
                msg = str(item.get("msg") or item)
                linhas.append(f"{loc}: {msg}" if loc else msg)
            else:
                linhas.append(str(item))
        return "; ".join(linhas)
    return str(raw)
