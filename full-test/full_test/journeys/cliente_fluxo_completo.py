"""ClienteFluxoCompletoJourney: cliente passa pelo fluxo feliz completo da OS.

Persona: cliente final da oficina. Internamente a journey se auto-provisiona
cliente + veiculo proprios (uma thread, dados isolados — ver orchestrator
"Isolamento de dados"). Operacoes privilegiadas (criar ordem, iniciar
diagnostico, aprovar orcamento, finalizar, registrar entrega) sao feitas com
credencial admin compartilhada — isso e um test-double do time interno da
oficina; a feature coberta aqui e o que o CLIENTE consegue fazer: consultar
o status sem login atraves de ``/acompanhamento``.

Passos (cada transicao administrativa e seguida por consulta publica):

  1. (admin) cria cliente + veiculo proprios pra journey
  2. (admin) cria OS (status: RECEBIDA)
  3. (cliente sem auth) consulta /acompanhamento -> RECEBIDA
  4. (admin) adiciona item de servico + item de estoque
  5. (admin) iniciar_diagnostico -> EM_DIAGNOSTICO + consulta publica
  6. sleep(rand 2-5s) — gera delta de tempo mensuravel
  7. (admin) gerar_orcamento -> AGUARDANDO_APROVACAO + consulta publica
  8. sleep(2-5s)
  9. (admin) aprovar_orcamento -> EM_EXECUCAO + consulta publica
 10. sleep(2-5s)
 11. (admin) finalizar_servico -> FINALIZADA + consulta publica
 12. sleep(2-5s)
 13. (admin) registrar_entrega -> ENTREGUE + consulta publica
 14. (admin) snapshot final /metricas — orchestrator valida agregado no final

Marker conceitual: ``@pytest.mark.slowest`` (tem sleeps obrigatorios >= 1s).
O marker e aplicado pelo pytest entrypoint (step 14), nao nesta classe.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney
from full_test.support.consistency import ConsistencyChecker

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from full_test.client import models
    from full_test.seeders.config import FullTestConfig


_SLEEP_MIN_S = 2.0
_SLEEP_MAX_S = 5.0


@dataclass(frozen=True, slots=True)
class RecursosSeed:
    """Recursos pre-criados (servico + item estoque) que a journey consome.

    Passados pelo orchestrator (step 13) apos chamar
    ``seeders.orquestrar.seed_completo``. A quantidade a consumir do item
    de estoque e configuravel para exercitar diferentes pontos na
    conservacao de estoque.
    """

    servico_id: UUID
    item_estoque_id: UUID
    item_estoque_qty_a_consumir: int = 1


class ClienteFluxoCompletoJourney(UserJourney):
    nome_journey = "cliente-fluxo-completo"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        recursos: RecursosSeed,
        admin_access_token: str | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(config=config, instance_id=instance_id)
        self._recursos = recursos
        self._admin_access_token = admin_access_token
        # Seed per-instance: seed + instance_id garante CPFs/placas unicos
        # quando N journeys rodam em paralelo com o mesmo config.seed.
        # ``S311`` liberado: este RNG e dado de teste, nunca cripto.
        self._rng = rng or random.Random(f"{config.seed}-{instance_id}")  # noqa: S311
        self._client: SystemClient | None = None
        self._checker: ConsistencyChecker | None = None
        self._cliente: models.ClienteResponse | None = None
        self._veiculo: models.VeiculoResponse | None = None
        self._ordem: models.OrdemDeServicoResponse | None = None

    # ---------------- ciclo de vida ----------------

    def setup(self) -> None:
        with self.log.passo("setup/admin-client"):
            self._client = SystemClient(
                self._config.base_url, timeout=self._config.http_timeout
            )
            # Token compartilhado pelo builder evita rate limit em /login
            # (5/min) quando N journeys precisam de admin simultaneamente.
            if self._admin_access_token is not None:
                self._client.set_token(self._admin_access_token)
            else:
                self._client.login(
                    email=self._config.admin_email,
                    senha=self._config.admin_password,
                )
            self._checker = ConsistencyChecker(self._client)

        with self.log.passo("setup/criar-cliente"):
            assert self._client is not None  # noqa: S101
            suf = self._instance_id
            self._cliente = self._client.criar_cliente(
                nome=f"Cliente FullTest {suf}",
                documento=self._gerar_cpf_sintetico(),
                tipo_documento="cpf",
                contato=f"+55 11 9{suf.zfill(8)}",
            )

        with self.log.passo("setup/criar-veiculo"):
            assert self._client is not None  # noqa: S101
            assert self._cliente is not None  # noqa: S101
            self._veiculo = self._client.adicionar_veiculo(
                self._cliente.id,
                placa=self._gerar_placa_sintetica(),
                marca="Fiat",
                modelo="Uno",
                ano=2015,
            )

    def executar(self) -> None:
        assert self._client is not None  # noqa: S101
        assert self._checker is not None  # noqa: S101
        assert self._cliente is not None  # noqa: S101
        assert self._veiculo is not None  # noqa: S101

        # ---- 1. criar ordem (RECEBIDA) ----
        with self.log.passo("criar-ordem"):
            self._ordem = self._client.criar_ordem(
                cliente_id=self._cliente.id,
                veiculo_id=self._veiculo.id,
            )
            assert self._ordem.status == "recebida"  # noqa: S101

        # A primeira consulta publica bate ``RECEBIDA``: confirma que o
        # endpoint ve a ordem recem-criada antes mesmo de qualquer mutacao.
        self._confirmar_status_publico("recebida")

        # ---- 2. adicionar itens (ainda RECEBIDA) ----
        with self.log.passo("adicionar-item-servico"):
            self._ordem = self._client.adicionar_item_ordem(
                self._ordem.id,
                servico_catalogo_id=self._recursos.servico_id,
                item_estoque_id=self._recursos.item_estoque_id,
                descricao="Item principal",
                quantidade=self._recursos.item_estoque_qty_a_consumir,
            )
            self._checker.assert_subtotais_dos_itens(self._ordem)

        # ---- 3. iniciar diagnostico ----
        self._transicao(
            "iniciar-diagnostico",
            "recebida",
            "em_diagnostico",
            acao=lambda c, oid: c.iniciar_diagnostico(oid),
        )

        # ---- 4. gerar orcamento ----
        self._transicao(
            "gerar-orcamento",
            "em_diagnostico",
            "aguardando_aprovacao",
            acao=lambda c, oid: c.gerar_orcamento(oid),
            validacao_orcamento=True,
        )

        # ---- 5. aprovar orcamento ----
        self._transicao(
            "aprovar-orcamento",
            "aguardando_aprovacao",
            "em_execucao",
            acao=lambda c, oid: c.aprovar_orcamento(oid),
        )

        # ---- 6. finalizar servico ----
        self._transicao(
            "finalizar-servico",
            "em_execucao",
            "finalizada",
            acao=lambda c, oid: c.finalizar_servico(oid),
        )

        # ---- 7. registrar entrega ----
        # Ultima transicao: nao precisa dormir; o snapshot final fica logo
        # em seguida e nao ha mais mutacoes pra gerar delta.
        self._transicao(
            "registrar-entrega",
            "finalizada",
            "entregue",
            acao=lambda c, oid: c.registrar_entrega(oid),
            sleep=False,
        )

        # ---- 8. snapshot final de metricas (consumido pelo orchestrator) ----
        with self.log.passo("snapshot-metricas-final"):
            _ = self._client.obter_metricas()

    def teardown(self) -> None:
        if self._client is not None:
            with self.log.passo("teardown/close"):
                # NAO faz logout quando o token e compartilhado — revogar
                # invalidaria outras journeys. Apenas fecha o httpx pool.
                # Se a journey tem seu proprio token (fallback), ainda assim
                # pulamos logout — o token expira naturalmente.
                self._client.close()

    # ---------------- helpers ----------------

    def _transicao(
        self,
        nome_passo: str,
        estado_anterior: str,
        estado_esperado: str,
        *,
        acao: Callable[[SystemClient, UUID], models.OrdemDeServicoResponse],
        sleep: bool = True,
        validacao_orcamento: bool = False,
    ) -> None:
        """Executa uma transicao da ordem + consulta publica + sleep opcional.

        Sequencia:
          1. ``assert_transicao_valida(de, para)``: garante que a
             transicao pedida e legal pelo dominio (defesa contra bugs na
             journey que levariam o API a rejeitar 409).
          2. ``acao(client, ordem_id)``: chama o endpoint admin correspondente.
          3. Valida ``status == estado_esperado`` + totais de orcamento se
             ``validacao_orcamento`` estiver ligado.
          4. Consulta publica ``/acompanhamento`` — sem token — para confirmar
             que o cliente final ve o novo status.
          5. Sleep de 2-5s (exceto na ultima transicao) para gerar delta de
             tempo mensuravel para o calculo de ``tempo_medio_execucao_minutos``.
        """
        assert self._client is not None  # noqa: S101
        assert self._checker is not None  # noqa: S101
        assert self._ordem is not None  # noqa: S101

        with self.log.passo(f"validar-transicao/{nome_passo}"):
            self._checker.assert_transicao_valida(
                de=estado_anterior, para=estado_esperado
            )

        with self.log.passo(nome_passo):
            self._ordem = acao(self._client, self._ordem.id)
            assert self._ordem.status == estado_esperado, (  # noqa: S101
                f"Esperado {estado_esperado}, veio {self._ordem.status}"
            )
            if validacao_orcamento:
                self._checker.assert_total_orcamento(self._ordem)
                self._checker.assert_subtotais_dos_itens(self._ordem)

        self._confirmar_status_publico(estado_esperado)

        if sleep:
            delay = self._rng.uniform(_SLEEP_MIN_S, _SLEEP_MAX_S)
            with self.log.passo(f"sleep/{nome_passo}/{delay:.2f}s"):
                time.sleep(delay)

    def _confirmar_status_publico(self, status_esperado: str) -> None:
        """Chama ``/acompanhamento`` sem auth e compara com ``status_esperado``.

        E o owner do requisito explicito #1 do orchestrator: o cliente
        final sempre consulta SEM login e recebe o mesmo status que o
        detalhe admin. O ``ConsistencyChecker`` internamente usa
        ``SystemClient.sem_autenticacao()`` — nenhum token vaza.
        """
        assert self._checker is not None  # noqa: S101
        assert self._veiculo is not None  # noqa: S101
        assert self._cliente is not None  # noqa: S101
        with self.log.passo(f"acompanhamento-publico/{status_esperado}"):
            self._checker.assert_status_publico(
                placa=self._veiculo.placa,
                documento=self._cliente.documento_formatado,
                status_esperado=status_esperado,
            )

    def _gerar_cpf_sintetico(self) -> str:
        """CPF valido gerado a partir do ``rng`` da journey.

        Implementacao completa (digitos verificadores) delegada a
        ``full_test.support.documentos`` para evitar importar codigo de
        producao. Se o CPF gerado ja existir no banco (runs repetidos no
        mesmo dataset), o API retorna 409 — o orchestrator executa
        ``reset`` entre runs para evitar colisoes.
        """
        from full_test.support.documentos import gerar_cpf

        return gerar_cpf(self._rng)

    def _gerar_placa_sintetica(self) -> str:
        """Placa sintetica (padrao antigo) a partir do mesmo ``rng``."""
        from full_test.support.documentos import gerar_placa

        return gerar_placa(self._rng)
