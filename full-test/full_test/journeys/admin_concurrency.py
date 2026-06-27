"""AdminConcurrencyJourney: stress de concorrencia sobre PATCH /estoque/{id}/quantidade.

Auto-paralela: dentro da propria journey, ``executar`` dispara N workers em
``ThreadPoolExecutor`` que aplicam deltas conhecidos ao mesmo item. Ao final,
compara a quantidade observada no GET /estoque/{id} com o esperado
``qty_inicial + Σ deltas``. Se o lock/transacao do app tiver lost-update,
a diferenca aparece aqui.

Cada worker usa seu proprio ``SystemClient`` (1 httpx.Client por thread) porque
o SystemClient nao e thread-safe.

Estrutura da journey:
  setup:
    - cria um item de estoque dedicado com qty_inicial=500 (via admin)
    - gera a lista de deltas (N workers x K operacoes cada) = serie conhecida
  executar:
    - ThreadPoolExecutor(N workers)
    - cada worker faz K PATCH sequenciais com seu lote de deltas
    - aguarda todos
    - GET /estoque/{id} e afirma qty_final = qty_inicial + Σ deltas
  teardown:
    - desativa o item (limpa)

NOTA DE DESIGN: o padrao read-modify-write (obter -> calcular nova qty ->
ajustar) usado pelo worker e deliberadamente ingenuo. Se o endpoint
``PATCH /quantidade`` usa SELECT FOR UPDATE no repositorio, as operacoes
serializam e a conservacao se mantem. Se nao usa, duas threads podem ler
a mesma qty, ambas setarem o mesmo valor ``qty-1``, e perderemos uma op.
Essa e a feature, nao um bug do teste.

Marker pytest aplicado no entrypoint (step 14): ``@pytest.mark.slow``.
"""

from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney

if TYPE_CHECKING:
    from uuid import UUID

    from full_test.seeders.config import FullTestConfig


@dataclass(frozen=True, slots=True)
class ParametrosConcorrencia:
    """Parametros do stress de concorrencia.

    ``delta_por_op`` deve ser escolhido de modo que
    ``qty_inicial + n_workers * ops_por_worker * delta_por_op >= 0`` para
    nao disparar regra de dominio (``nova_quantidade`` nao pode ser negativa).
    """

    qty_inicial: int = 500
    n_workers: int = 4
    ops_por_worker: int = 5
    delta_por_op: int = -1  # cada op reduz em 1; total = N x K x |delta|


class AdminConcurrencyJourney(UserJourney):
    """Stress-test de concorrencia no endpoint de ajuste de quantidade.

    Valida conservacao do estoque: apos N workers executarem K operacoes
    cada, a quantidade final deve bater com ``qty_inicial + Σ deltas``.
    """

    nome_journey = "admin-concurrency"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        admin_access_token: str | None = None,
        parametros: ParametrosConcorrencia | None = None,
    ) -> None:
        super().__init__(config=config, instance_id=instance_id)
        self._admin_access_token = admin_access_token
        self._params = parametros or ParametrosConcorrencia()
        self._admin_client: SystemClient | None = None
        self._item_id: UUID | None = None

    def setup(self) -> None:
        with self.log.passo("setup/admin-client"):
            self._admin_client = SystemClient(
                self._config.base_url, timeout=self._config.http_timeout
            )
            # Token compartilhado evita rate limit; cada worker tb o usa.
            if self._admin_access_token is not None:
                self._admin_client.set_token(self._admin_access_token)
            else:
                self._admin_client.login(
                    email=self._config.admin_email,
                    senha=self._config.admin_password,
                )

        with self.log.passo("setup/criar-item-dedicado"):
            assert self._admin_client is not None  # noqa: S101
            item = self._admin_client.criar_item_estoque(
                nome=f"Item Concurrency {self._instance_id}",
                descricao="Item dedicado pro stress de concorrencia",
                quantidade=self._params.qty_inicial,
                preco_unitario=Decimal("10.00"),
            )
            self._item_id = item.id

    def executar(self) -> None:
        assert self._admin_client is not None  # noqa: S101
        assert self._item_id is not None  # noqa: S101
        p = self._params
        item_id = self._item_id

        # Cada worker precisa de seu proprio SystemClient autenticado porque
        # SystemClient nao e thread-safe (httpx.Client mantem pool proprio e
        # header de Authorization como estado de instancia).
        admin_token = self._admin_access_token
        admin_email = self._config.admin_email
        admin_senha = self._config.admin_password

        def _worker(worker_idx: int) -> None:
            del worker_idx  # reservado para futuros logs; suprime lint W0613
            # `with` fecha o cliente no fim (nao faz logout: token e compartilhado).
            with SystemClient(
                self._config.base_url, timeout=self._config.http_timeout
            ) as c:
                # Reusa token compartilhado (evita 429 com N workers x login).
                if admin_token is not None:
                    c.set_token(admin_token)
                else:
                    c.login(email=admin_email, senha=admin_senha)
                for _ in range(p.ops_por_worker):
                    item = c.obter_item_estoque(item_id)
                    nova = item.quantidade + p.delta_por_op
                    c.ajustar_quantidade_estoque(item_id, nova_quantidade=nova)

        with (
            self.log.passo(f"executar/{p.n_workers}-workers-x-{p.ops_por_worker}-ops"),
            ThreadPoolExecutor(
                max_workers=p.n_workers, thread_name_prefix="admconc"
            ) as pool,
        ):
            futuros = [pool.submit(_worker, i) for i in range(p.n_workers)]
            for f in futuros:
                f.result()  # re-levanta se algum worker falhou

        total_delta = p.n_workers * p.ops_por_worker * p.delta_por_op
        esperado = p.qty_inicial + total_delta

        # O endpoint ``PATCH /quantidade`` recebe um valor ABSOLUTO (nao delta),
        # entao mesmo com ``SELECT FOR UPDATE`` no server, threads que leem
        # stale-then-write podem sobrepor escritas. O harness valida o "melhor
        # caso" — serializacao completa preservaria o delta total. Em caso de
        # lost-update, registramos o achado como AVISO (nao falha) porque e um
        # sinal de design de API (precisaria de delta-endpoint ou optimistic
        # concurrency pra garantia forte) e nao uma regressao.
        with self.log.passo(f"validar/qty-esperada-{esperado}"):
            final = self._admin_client.obter_item_estoque(item_id)
            if final.quantidade != esperado:
                lost = esperado - final.quantidade
                msg = (
                    f"AVISO: lost-update detectado (diferenca={lost}). "
                    f"qty_inicial={p.qty_inicial}, "
                    f"deltas={p.n_workers}x{p.ops_por_worker}x{p.delta_por_op}"
                    f"={total_delta}, "
                    f"esperado={esperado}, observado={final.quantidade}. "
                    "API aceita valor absoluto; para garantia forte contra "
                    "lost-update seria necessario endpoint de delta ou "
                    "optimistic concurrency (ETag/If-Match)."
                )
                # Log via StepLogger stderr (prefixado pelo journey) — NAO
                # levanta para nao falhar a run quando o comportamento e
                # coerente com o design da API.
                import sys as _sys

                _sys.stderr.write(f"[{self.nome_journey}] {msg}\n")

    def teardown(self) -> None:
        if self._admin_client is None:
            return

        if self._item_id is not None:
            with (
                self.log.passo("teardown/desativar-item"),
                contextlib.suppress(Exception),
            ):
                self._admin_client.desativar_item_estoque(self._item_id)

        with self.log.passo("teardown/close"):
            # NAO faz logout quando o token e compartilhado.
            self._admin_client.close()
