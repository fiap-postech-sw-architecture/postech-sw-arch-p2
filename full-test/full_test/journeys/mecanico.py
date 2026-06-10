"""MecanicoJourney: fluxo do mecanico sobre uma OS existente.

Pre-requisito: o orchestrator (step 13) cria a OS via credencial admin e
passa ``ordem_id`` + ``servico_id`` + ``item_estoque_id`` ao
``MecanicoJourney``. A journey usa credencial MECANICO
(``mecanico-00@full-test.local``) para exercitar apenas o subset
admin+mecanico do contexto OS.

Passos (subset que MECANICO pode executar, ver ``src/ordem_servico/
interfaces/router.py:8-15``):

  1. login como MECANICO
  2. obter ordem inicial e validar status ``RECEBIDA``
  3. adicionar 2 itens a ordem (com e sem vinculo a estoque)
  4. iniciar diagnostico -> ``EM_DIAGNOSTICO``
  5. gerar orcamento -> ``AGUARDANDO_APROVACAO``
  6. teste negativo: tentar aprovar orcamento como MECANICO -> espera 403
  7. teardown: logout

Aprovacao do orcamento, finalizacao e entrega ficam fora: sao admin-only
(ou admin+mecanico no caso de finalizacao/entrega, mas o owner do happy
path ate a entrega e o ``ClienteFluxoCompletoJourney`` no step 6 via
admin). Aqui o foco e cobrir o subset exclusivo do mecanico e comprovar a
fronteira RBAC em ``POST /aprovacao``.

Marker pytest aplicado no entrypoint (step 14): ``@pytest.mark.slow``
(instancia viva HTTP+DB, sem sleep obrigatorio — roda em CI).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from full_test.client.errors import NaoAutorizadoError
from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney
from full_test.support.consistency import ConsistencyChecker

if TYPE_CHECKING:
    from uuid import UUID

    from full_test.client import models
    from full_test.seeders.config import FullTestConfig


class MecanicoJourney(UserJourney):
    """Exercita o subset admin+mecanico sobre uma OS ja criada por admin.

    Cada instancia recebe ``ordem_id`` + ``servico_id`` + ``item_estoque_id``
    pre-criados pelo orchestrator e executa a sequencia de transicoes
    permitidas ao papel MECANICO, encerrando com um teste negativo que
    valida a fronteira RBAC (aprovar orcamento e admin-only).
    """

    nome_journey = "mecanico"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        mecanico_email: str,
        mecanico_senha: str,
        ordem_id: UUID,
        servico_id: UUID,
        item_estoque_id: UUID,
    ) -> None:
        super().__init__(config=config, instance_id=instance_id)
        self._email = mecanico_email
        self._senha = mecanico_senha
        self._ordem_id = ordem_id
        self._servico_id = servico_id
        self._item_estoque_id = item_estoque_id
        self._client: SystemClient | None = None
        self._checker: ConsistencyChecker | None = None
        self._ordem: models.OrdemDeServicoResponse | None = None

    # ---------------- ciclo de vida ----------------

    def setup(self) -> None:
        with self.log.passo("setup/login-mecanico"):
            self._client = SystemClient(
                self._config.base_url, timeout=self._config.http_timeout
            )
            self._client.login(email=self._email, senha=self._senha)
            self._checker = ConsistencyChecker(self._client)

    def executar(self) -> None:
        assert self._client is not None  # noqa: S101
        assert self._checker is not None  # noqa: S101

        # 1. confirmar que a ordem criada pelo admin chega no estado esperado.
        #    Se vier algo diferente de RECEBIDA o pre-requisito quebrou —
        #    melhor estourar aqui do que mascarar uma falha de orquestracao.
        with self.log.passo("obter-ordem-inicial"):
            self._ordem = self._client.obter_ordem(self._ordem_id)
            assert self._ordem.status == "recebida", (  # noqa: S101
                f"MecanicoJourney espera ordem em RECEBIDA, veio {self._ordem.status}"
            )

        # 2. adicionar item vinculado a estoque (pecas reservaveis).
        with self.log.passo("adicionar-item-com-estoque"):
            self._ordem = self._client.adicionar_item_ordem(
                self._ordem_id,
                servico_catalogo_id=self._servico_id,
                item_estoque_id=self._item_estoque_id,
                descricao="Troca executada pelo mecanico",
                quantidade=1,
            )
            self._checker.assert_subtotais_dos_itens(self._ordem)

        # 3. adicionar item sem estoque (mao-de-obra pura).
        with self.log.passo("adicionar-item-sem-estoque"):
            self._ordem = self._client.adicionar_item_ordem(
                self._ordem_id,
                servico_catalogo_id=self._servico_id,
                item_estoque_id=None,
                descricao="Servico adicional (sem peca)",
                quantidade=2,
            )
            self._checker.assert_subtotais_dos_itens(self._ordem)

        # 4. RECEBIDA -> EM_DIAGNOSTICO.
        with self.log.passo("iniciar-diagnostico"):
            self._checker.assert_transicao_valida(de="recebida", para="em_diagnostico")
            self._ordem = self._client.iniciar_diagnostico(self._ordem_id)
            assert self._ordem.status == "em_diagnostico", (  # noqa: S101
                f"esperado EM_DIAGNOSTICO, veio {self._ordem.status}"
            )

        # 5. EM_DIAGNOSTICO -> AGUARDANDO_APROVACAO (deixa pendente para o admin).
        with self.log.passo("gerar-orcamento"):
            self._checker.assert_transicao_valida(
                de="em_diagnostico", para="aguardando_aprovacao"
            )
            self._ordem = self._client.gerar_orcamento(self._ordem_id)
            assert self._ordem.status == "aguardando_aprovacao", (  # noqa: S101
                f"esperado AGUARDANDO_APROVACAO, veio {self._ordem.status}"
            )
            self._checker.assert_total_orcamento(self._ordem)
            self._checker.assert_subtotais_dos_itens(self._ordem)

        # 6. Teste negativo: MECANICO NAO pode aprovar orcamento (admin-only).
        #    Se 403 nao vier, a matriz RBAC esta afrouxada — fail loud.
        with self.log.passo("negativo/aprovar-orcamento-403"):
            try:
                self._client.aprovar_orcamento(self._ordem_id)
            except NaoAutorizadoError:
                pass
            else:
                raise AssertionError(
                    "MECANICO conseguiu aprovar orcamento — RBAC quebrado"
                )

    def teardown(self) -> None:
        if self._client is not None:
            with (
                self.log.passo("teardown/logout"),
                contextlib.suppress(Exception),
            ):
                self._client.logout()
            self._client.close()
