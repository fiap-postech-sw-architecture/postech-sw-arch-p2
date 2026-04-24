"""RbacMatrixJourney: matriz 45 x 4 de autorizacao por endpoint/papel.

Matriz escrita a mao (``RBAC_ESPERADO``) para ser fonte da verdade
independente do codigo. Cada entrada e ``(metodo, path_template)`` ->
``{papel -> status_esperado}``.

Contagem real: enumerando os routers em
``src/{autenticacao,cliente_veiculo,catalogo_servicos,estoque,ordem_servico}/
interfaces/router.py`` + ``src/compartilhado/interfaces/router_publico.py``
chegamos a **45 endpoints**. O orchestrator menciona "46" como aproximacao
de documentacao; a contagem exata vem dos routers em tempo de leitura.

Status especiais:
    - 200/201/204: autorizado, resposta bem-sucedida
    - 401: anon tentando endpoint protegido
    - 403: autenticado mas papel insuficiente
    - 404: passa na auth, recurso inexistente (aceitavel pra RBAC)
    - 409: passa na auth, conflito de estado (aceitavel pra RBAC)
    - 422: passa na auth, body invalido (aceitavel pra RBAC)

Ou seja: o que importa aqui e o 401/403 (RBAC) ser ou NAO ser emitido
conforme a matriz. Os payloads sao minimos, propositalmente sintetizados
com UUIDs inexistentes para nao efetivar mudancas no sistema.

Marker: ``@pytest.mark.slow`` (sem sleep; 180 chamadas HTTP).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from full_test.client.errors import (
    ConflitoError,
    NaoAutenticadoError,
    NaoAutorizadoError,
    NaoEncontradoError,
    RateLimitError,
    SystemClientError,
    ValidacaoError,
)
from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney

if TYPE_CHECKING:
    from full_test.seeders.config import FullTestConfig


class Papel(StrEnum):
    """Papeis que a matriz exercita. ``ANON`` = requisicao sem Authorization."""

    ANON = "anon"
    ATENDENTE = "atendente"
    MECANICO = "mecanico"
    ADMIN = "admin"


_AUTH_NECESSARIA = 401
_PAPEL_INSUFICIENTE = 403


# Chave: ``(metodo_http, path_template)``. Valor: dict
# ``papel -> int | frozenset[int]``. Um ``frozenset`` permite multiplos
# statuses aceitaveis (ex.: 200 OU 404 quando o UUID sintetico nao casa com
# nenhum recurso real).
RBAC_ESPERADO: dict[tuple[str, str], dict[Papel, int | frozenset[int]]] = {
    # ---------- autenticacao (/api/v1/autenticacao) ----------
    ("POST", "/api/v1/autenticacao/login"): {
        # Anon pode tentar login: 200 se casar credencial, 401 se nao casar,
        # 422 se o payload nao passar na validacao. 429 e valido sob rate
        # limit (5/min em /login) — comportamento real de producao. Nao ha
        # 403 aqui — quem esta autenticado tambem pode relogar.
        Papel.ANON: frozenset({200, 401, 422, 429}),
        Papel.ATENDENTE: frozenset({200, 401, 422, 429}),
        Papel.MECANICO: frozenset({200, 401, 422, 429}),
        Papel.ADMIN: frozenset({200, 401, 422, 429}),
    },
    ("POST", "/api/v1/autenticacao/registrar"): {
        # 429 aceito: /registrar tb tem rate limit 5/min.
        Papel.ANON: frozenset({401, 429}),
        Papel.ATENDENTE: frozenset({403, 429}),
        Papel.MECANICO: frozenset({403, 429}),
        Papel.ADMIN: frozenset({201, 409, 422, 429}),
    },
    ("POST", "/api/v1/autenticacao/logout"): {
        # Logout nao tem dependencia de papel: qualquer autenticado desloga.
        # Status devolvido pelo handler e 200 (ver ``obter_logout``) — o
        # router nao sobrescreve com 204. 429 aceito: /logout rate-limited 10/min.
        Papel.ANON: frozenset({401, 429}),
        Papel.ATENDENTE: frozenset({200, 204, 429}),
        Papel.MECANICO: frozenset({200, 204, 429}),
        Papel.ADMIN: frozenset({200, 204, 429}),
    },
    ("POST", "/api/v1/autenticacao/refresh"): {
        # 429 aceito: /refresh tb tem rate limit 10/min.
        Papel.ANON: frozenset({200, 401, 422, 429}),
        Papel.ATENDENTE: frozenset({200, 401, 422, 429}),
        Papel.MECANICO: frozenset({200, 401, 422, 429}),
        Papel.ADMIN: frozenset({200, 401, 422, 429}),
    },
    # ---------- clientes (/api/v1/clientes) ----------
    ("POST", "/api/v1/clientes/"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({201, 409, 422}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({201, 409, 422}),
    },
    ("GET", "/api/v1/clientes/"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: 200,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: 200,
    },
    ("GET", "/api/v1/clientes/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({200, 404}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404}),
    },
    ("PUT", "/api/v1/clientes/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({200, 404, 422}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404, 422}),
    },
    ("DELETE", "/api/v1/clientes/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({204, 404}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({204, 404}),
    },
    ("POST", "/api/v1/clientes/{id}/veiculos"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({201, 404, 422}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({201, 404, 422}),
    },
    ("GET", "/api/v1/clientes/{id}/veiculos"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({200, 404}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404}),
    },
    ("DELETE", "/api/v1/clientes/{id}/veiculos/{veiculo_id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({204, 404}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({204, 404}),
    },
    ("GET", "/api/v1/clientes/{id}/dados-pessoais"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({200, 404}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404}),
    },
    # Endpoint ``/dados-pessoais/exportar`` existe no router (mesmas
    # permissoes que ``/dados-pessoais``). Nao constava no spec original
    # do step — ver "Deviations" no reporte do step 12.
    ("GET", "/api/v1/clientes/{id}/dados-pessoais/exportar"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({200, 404}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404}),
    },
    ("DELETE", "/api/v1/clientes/{id}/dados-pessoais"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({204, 404}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({204, 404}),
    },
    ("POST", "/api/v1/clientes/{id}/consentimento"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({201, 404, 422}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({201, 404, 422}),
    },
    ("DELETE", "/api/v1/clientes/{id}/consentimento"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({204, 404, 422}),
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({204, 404, 422}),
    },
    # ---------- catalogo servicos (/api/v1/servicos) ----------
    ("POST", "/api/v1/servicos/"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({201, 409, 422}),
    },
    ("GET", "/api/v1/servicos/"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: 200,
        Papel.MECANICO: 200,
        Papel.ADMIN: 200,
    },
    ("GET", "/api/v1/servicos/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({200, 404}),
        Papel.MECANICO: frozenset({200, 404}),
        Papel.ADMIN: frozenset({200, 404}),
    },
    ("PUT", "/api/v1/servicos/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404, 422}),
    },
    ("DELETE", "/api/v1/servicos/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({204, 404}),
    },
    # ---------- estoque (/api/v1/estoque) ----------
    # ATENDENTE NAO pode acessar estoque (router exige admin/mecanico).
    ("POST", "/api/v1/estoque/"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({201, 409, 422}),
    },
    ("GET", "/api/v1/estoque/"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: 200,
        Papel.ADMIN: 200,
    },
    ("GET", "/api/v1/estoque/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 404}),
        Papel.ADMIN: frozenset({200, 404}),
    },
    ("PUT", "/api/v1/estoque/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404, 422}),
    },
    ("PATCH", "/api/v1/estoque/{id}/quantidade"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404, 422}),
    },
    ("DELETE", "/api/v1/estoque/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({204, 404}),
    },
    # ---------- ordens de servico (/api/v1/ordens-de-servico) ----------
    ("POST", "/api/v1/ordens-de-servico/"): {
        # 409 aceito: o payload sintetico usa UUIDs random que podem casar
        # estados conflitantes; e contrato valido do server responder 409.
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({201, 404, 409, 422}),
    },
    ("GET", "/api/v1/ordens-de-servico/"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: 200,
        Papel.MECANICO: 200,
        Papel.ADMIN: 200,
    },
    ("GET", "/api/v1/ordens-de-servico/metricas"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: 200,
    },
    ("GET", "/api/v1/ordens-de-servico/{id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: frozenset({200, 404}),
        Papel.MECANICO: frozenset({200, 404}),
        Papel.ADMIN: frozenset({200, 404}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/itens"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 201, 404, 409, 422}),
        Papel.ADMIN: frozenset({200, 201, 404, 409, 422}),
    },
    ("DELETE", "/api/v1/ordens-de-servico/{id}/itens/{item_id}"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 204, 404, 409}),
        Papel.ADMIN: frozenset({200, 204, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/diagnostico"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 404, 409}),
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/orcamento"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 404, 409}),
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/aprovacao"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/finalizacao"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 404, 409}),
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/entrega"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 404, 409}),
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/cancelamento"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404, 409, 422}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/orcamento-complementar"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 404, 409}),
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/aprovacao-complementar"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: frozenset({200, 404, 409}),
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/rejeicao-complementar"): {
        Papel.ANON: _AUTH_NECESSARIA,
        Papel.ATENDENTE: _PAPEL_INSUFICIENTE,
        Papel.MECANICO: _PAPEL_INSUFICIENTE,
        Papel.ADMIN: frozenset({200, 404, 409}),
    },
    # ---------- publicos (/api/v1/saude, /api/v1/acompanhamento) ----------
    ("GET", "/api/v1/saude"): {
        Papel.ANON: 200,
        Papel.ATENDENTE: 200,
        Papel.MECANICO: 200,
        Papel.ADMIN: 200,
    },
    ("GET", "/api/v1/acompanhamento"): {
        # Endpoint publico — nunca 401. 404 quando o par placa+documento
        # nao casa (shape constante, ver ``router_publico.py:65-74``).
        # 422 se os query params nao passarem nos limites de tamanho.
        # 429 aceito: rate limit 10/min por IP, atingido se muitas journeys
        # paralelas consultam /acompanhamento na mesma janela.
        Papel.ANON: frozenset({200, 404, 422, 429}),
        Papel.ATENDENTE: frozenset({200, 404, 422, 429}),
        Papel.MECANICO: frozenset({200, 404, 422, 429}),
        Papel.ADMIN: frozenset({200, 404, 422, 429}),
    },
}


def total_celulas() -> int:
    """Numero total de celulas (linha da matriz x papel)."""
    return sum(len(papeis) for papeis in RBAC_ESPERADO.values())


# Payloads minimos por endpoint — apenas o necessario para nao disparar 422
# antes do 401/403. Quando a chave nao existe, ``None`` (sem body) e o padrao.
_PAYLOADS_MINIMOS: dict[tuple[str, str], dict[str, object]] = {
    ("POST", "/api/v1/autenticacao/login"): {
        "email": "x@x.com",
        "senha": "x" * 12,
    },
    ("POST", "/api/v1/autenticacao/registrar"): {
        "email": "novo@x.com",
        "senha": "x" * 12,
    },
    ("POST", "/api/v1/autenticacao/refresh"): {"refresh_token": "invalid"},
    ("POST", "/api/v1/clientes/"): {
        "nome": "C",
        "documento": "12345678909",
        "tipo_documento": "cpf",
        "contato": "+5511999999999",
    },
    ("PUT", "/api/v1/clientes/{id}"): {
        "nome": "C",
        "contato": "+5511999999999",
    },
    ("POST", "/api/v1/clientes/{id}/veiculos"): {
        "placa": "ABC1234",
        "marca": "F",
        "modelo": "U",
        "ano": 2020,
    },
    ("POST", "/api/v1/clientes/{id}/consentimento"): {"tipo": "marketing"},
    ("POST", "/api/v1/servicos/"): {
        "nome": "X",
        "descricao": "y",
        "preco": "10.00",
    },
    ("PUT", "/api/v1/servicos/{id}"): {
        "nome": "X",
        "descricao": "y",
        "preco": "10.00",
    },
    ("POST", "/api/v1/estoque/"): {
        "nome": "X",
        "descricao": "y",
        "quantidade": 1,
        "preco_unitario": "10.00",
    },
    ("PUT", "/api/v1/estoque/{id}"): {
        "nome": "X",
        "descricao": "y",
        "preco_unitario": "10.00",
    },
    ("PATCH", "/api/v1/estoque/{id}/quantidade"): {"nova_quantidade": 1},
    ("POST", "/api/v1/ordens-de-servico/"): {
        "cliente_id": "00000000-0000-0000-0000-000000000000",
        "veiculo_id": "00000000-0000-0000-0000-000000000000",
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/itens"): {
        "servico_catalogo_id": "00000000-0000-0000-0000-000000000000",
        "descricao": "x",
        "quantidade": 1,
    },
    ("POST", "/api/v1/ordens-de-servico/{id}/cancelamento"): {"motivo": "x"},
}

_QUERY_PARAMS: dict[tuple[str, str], dict[str, str]] = {
    # ``tipo`` e obrigatorio na query; sem isso e 422 mesmo autorizado.
    ("DELETE", "/api/v1/clientes/{id}/consentimento"): {"tipo": "marketing"},
    ("GET", "/api/v1/acompanhamento"): {
        "placa": "ABC1234",
        "documento": "12345678909",
    },
}


@dataclass(frozen=True, slots=True)
class Celula:
    """Resultado observado pra uma combinacao ``(endpoint, papel)``."""

    metodo: str
    path: str
    papel: Papel
    esperado: int | frozenset[int]
    observado: int | None = None
    erro: str | None = None

    def ok(self) -> bool:
        """True se o observado casa com o esperado (single-int ou frozenset)."""
        if self.observado is None:
            return False
        esperado = (
            self.esperado
            if isinstance(self.esperado, frozenset)
            else frozenset({self.esperado})
        )
        return self.observado in esperado


class RbacMatrixJourney(UserJourney):
    """Exercita a matriz RBAC completa (45 endpoints x 4 papeis = 180 celulas).

    A journey obtem um token por papel no ``setup`` (reusa credenciais
    criadas pelos seeders do step 3 + admin seedado pelo boot). Em
    ``executar``, para cada celula faz uma chamada HTTP e compara o
    ``status_code`` observado com o esperado.

    Se uma ou mais celulas falharem, a journey levanta
    ``AssertionError`` no final (collect-all) — o orchestrator converte
    em ``StatusJourney.FALHOU``.

    Bonus: apos a matriz, exerce o requisito explicito #1 ("consulta
    publica com shape constante 404") via
    ``ConsistencyChecker.assert_acompanhamento_404``.
    """

    nome_journey = "rbac-matrix"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        atendente_email: str,
        atendente_senha: str,
        mecanico_email: str,
        mecanico_senha: str,
        admin_access_token: str | None = None,
    ) -> None:
        super().__init__(config=config, instance_id=instance_id)
        self._creds: dict[Papel, tuple[str, str]] = {
            Papel.ATENDENTE: (atendente_email, atendente_senha),
            Papel.MECANICO: (mecanico_email, mecanico_senha),
            Papel.ADMIN: (config.admin_email, config.admin_password),
        }
        self._admin_access_token = admin_access_token
        self._tokens: dict[Papel, str] = {}
        self._falhas: list[Celula] = []

    # ---------------- ciclo de vida ----------------

    def setup(self) -> None:
        """Autentica cada papel e cacheia o access_token.

        Se ``admin_access_token`` foi passado pelo builder, reusa direto
        (evita rate limit em /login). Atendente e mecanico sempre fazem
        login proprio — sao poucos (2 logins).
        """
        if self._admin_access_token is not None:
            self._tokens[Papel.ADMIN] = self._admin_access_token
        for papel, (email, senha) in self._creds.items():
            if papel in self._tokens:
                continue
            with self.log.passo(f"setup/login-{papel.value}"):
                cli = SystemClient(
                    self._config.base_url, timeout=self._config.http_timeout
                )
                try:
                    tokens = cli.login(email=email, senha=senha)
                    self._tokens[papel] = tokens.access_token
                finally:
                    cli.close()

    def executar(self) -> None:
        """Percorre ``RBAC_ESPERADO`` e avalia cada celula.

        Ordem de iteracao: endpoints NAO-destrutivos primeiro, ``/logout`` por
        ultimo. Motivo: testar ``/logout`` com token autenticado revoga o JTI
        no servidor; se isso rodasse no meio da matriz, todas as celulas
        subsequentes do mesmo papel falhariam com ``401 Token revogado``.
        """
        total = total_celulas()
        ok = 0
        destrutivos = {("POST", "/api/v1/autenticacao/logout")}
        cells_nao_destrutivos = [
            (chave, mapa)
            for chave, mapa in RBAC_ESPERADO.items()
            if chave not in destrutivos
        ]
        cells_destrutivos = [
            (chave, mapa)
            for chave, mapa in RBAC_ESPERADO.items()
            if chave in destrutivos
        ]
        for (metodo, path_template), mapa in cells_nao_destrutivos + cells_destrutivos:
            for papel, esperado in mapa.items():
                celula = self._exercitar_celula(metodo, path_template, papel, esperado)
                if celula.ok():
                    ok += 1
                else:
                    self._falhas.append(celula)

        with self.log.passo(f"matriz/total-{total}-ok-{ok}"):
            if self._falhas:
                raise AssertionError(self._relatorio_falhas(total))

        # Bonus: verificacao do shape constante do 404 publico (req #1).
        with self.log.passo("acompanhamento/404-placa-inexistente"):
            cli = SystemClient(self._config.base_url, timeout=self._config.http_timeout)
            try:
                from full_test.support.consistency import ConsistencyChecker

                checker = ConsistencyChecker(cli)
                checker.assert_acompanhamento_404(
                    placa="ZZZ9999",
                    documento="00000000000",
                )
            finally:
                cli.close()

    def teardown(self) -> None:
        """Nao ha recurso persistente para liberar.

        Tokens expiram naturalmente; nao vale o custo de rodar N logouts
        aqui — isso alongaria a journey e geraria ruido nos rate limits
        de ``/logout``.
        """

    # ---------------- helpers ----------------

    def _exercitar_celula(
        self,
        metodo: str,
        path_template: str,
        papel: Papel,
        esperado: int | frozenset[int],
    ) -> Celula:
        """Faz uma chamada HTTP para ``(metodo, path)`` no contexto de ``papel``.

        Usa ``SystemClient`` apenas para a infraestrutura de headers/retry;
        as chamadas reais vao via ``_client.request`` para capturar o
        ``status_code`` bruto sem converter 4xx em excecao. Excecoes de
        transporte (rate limit, 5xx apos retries) viram erros observados
        para que a falha apareca no relatorio ao inves de abortar a matriz.
        """
        path = self._materializar_path(path_template)
        cli = SystemClient(self._config.base_url, timeout=self._config.http_timeout)
        try:
            # Celula destrutiva: /logout REVOGA o JTI do token usado. Se
            # reutilizassemos o token cacheado (``self._tokens[papel]``), a
            # revogacao propagaria para: (a) proximas celulas autenticadas
            # desse papel, (b) journeys paralelas que usam o mesmo admin
            # token compartilhado (``ClienteFluxoCompleto`` etc). Por isso,
            # para /logout fazemos um login throw-away dedicado: consome um
            # slot do rate limit (5/min), mas preserva o cache.
            eh_logout_autenticado = (
                metodo == "POST"
                and path_template == "/api/v1/autenticacao/logout"
                and papel != Papel.ANON
            )
            if papel != Papel.ANON:
                if eh_logout_autenticado:
                    token_descartavel = self._login_descartavel(papel)
                    cli.set_token(token_descartavel)
                else:
                    cli.set_token(self._tokens[papel])

            body = _PAYLOADS_MINIMOS.get((metodo, path_template))
            params = _QUERY_PARAMS.get((metodo, path_template))
            authenticated = papel != Papel.ANON

            try:
                headers = cli._headers(authenticated=authenticated)
                response = cli._client.request(
                    metodo,
                    path,
                    json=body,
                    params=params,
                    headers=headers,
                )
                return Celula(
                    metodo=metodo,
                    path=path_template,
                    papel=papel,
                    esperado=esperado,
                    observado=response.status_code,
                )
            except (
                NaoAutenticadoError,
                NaoAutorizadoError,
                NaoEncontradoError,
                ConflitoError,
                ValidacaoError,
                RateLimitError,
                SystemClientError,
            ) as exc:
                # Reservado: ``_client.request`` nao levanta essas — mas
                # mantemos o fallback para caso alguem troque por ``_request``.
                return Celula(
                    metodo=metodo,
                    path=path_template,
                    papel=papel,
                    esperado=esperado,
                    observado=getattr(exc, "status_code", None),
                    erro=str(exc),
                )
        finally:
            with contextlib.suppress(Exception):
                cli.close()

    def _login_descartavel(self, papel: Papel) -> str:
        """Faz login temporario para testar /logout sem invalidar tokens cacheados.

        Retorna access_token fresco descartavel. Contra-indicacao: consome
        um slot do rate limit de /login (5/min), entao so usar no cenario
        onde realmente queremos revogar — i.e., a celula de /logout da matriz.
        """
        email, senha = self._creds[papel]
        cli = SystemClient(self._config.base_url, timeout=self._config.http_timeout)
        try:
            tokens = cli.login(email=email, senha=senha)
            return tokens.access_token
        finally:
            cli.close()

    @staticmethod
    def _materializar_path(path_template: str) -> str:
        """Substitui placeholders por UUIDs sinteticos."""
        return (
            path_template.replace("{id}", str(uuid4()))
            .replace("{veiculo_id}", str(uuid4()))
            .replace("{item_id}", str(uuid4()))
        )

    def _relatorio_falhas(self, total: int) -> str:
        """Monta uma mensagem compacta listando as celulas divergentes."""
        mensagens = [
            f"{c.metodo} {c.path} [{c.papel.value}]: "
            f"esperado={c.esperado!r}, observado={c.observado!r}"
            + (f", erro={c.erro!r}" if c.erro else "")
            for c in self._falhas
        ]
        cabecalho = f"{len(self._falhas)}/{total} celulas RBAC falharam:"
        if len(mensagens) > 20:
            corpo = "\n".join(mensagens[:20])
            return f"{cabecalho}\n{corpo}\n... e mais {len(mensagens) - 20}"
        return f"{cabecalho}\n" + "\n".join(mensagens)
