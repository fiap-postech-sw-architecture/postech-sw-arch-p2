"""ClienteFluxosAlternativosJourney: cobre caminhos nao-felizes do ciclo da OS.

Parametrizada por ``Cenario``: cada instancia exercita um cenario especifico.
O orchestrator (step 13) cria varias instancias, cada uma com um ``Cenario``
diferente, e todas rodam em threads distintas.

Cenarios cobertos (enum ``Cenario``):

- ``CANCELAMENTO_EM_RECEBIDA``     — cria OS, cancela imediatamente
- ``CANCELAMENTO_EM_DIAGNOSTICO``  — cria OS -> diagnostico -> cancela
- ``CANCELAMENTO_EM_AGUARDANDO``   — avanca ate AGUARDANDO_APROVACAO -> cancela
- ``CANCELAMENTO_EM_EXECUCAO``     — avanca ate EM_EXECUCAO -> cancela
- ``COMPLEMENTAR_APROVADO``        — execucao -> complementar -> aprovar -> finaliza
- ``COMPLEMENTAR_REJEITADO``       — execucao -> complementar -> rejeitar -> finaliza
- ``TRANSICOES_INVALIDAS``         — tenta transicoes ilegais (4 pares) e afirma 409

``TODOS_CENARIOS`` expoe a tupla de cenarios que o orchestrator itera.

Marker conceitual: ``@pytest.mark.slow`` (sem sleep obrigatorio; roda em CI).
O marker e aplicado pelo pytest entrypoint (step 14), nao nesta classe.

Nota sobre a cobertura de ``TRANSICOES_INVALIDAS``:
  Mantemos 4 pares representativos de (estado, acao_invalida) que cobrem as
  regioes criticas da maquina: (a) estado inicial onde acoes tardias sao
  rejeitadas; (b) estado intermediario onde re-entrada e rejeitada; (c)
  estados terminais onde ``cancelar`` tem que falhar. A matriz completa
  (46 endpoints x 8 estados) vive na ``RbacMatrixJourney`` (step 12) para
  nao duplicar superficie de teste.
"""

from __future__ import annotations

import random
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from full_test.client.errors import ConflitoError
from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney
from full_test.support.consistency import ConsistencyChecker

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

    from full_test.client import models
    from full_test.seeders.config import FullTestConfig


class Cenario(StrEnum):
    """Enumera os 7 cenarios alternativos cobertos pela journey."""

    CANCELAMENTO_EM_RECEBIDA = "cancelamento-em-recebida"
    CANCELAMENTO_EM_DIAGNOSTICO = "cancelamento-em-diagnostico"
    CANCELAMENTO_EM_AGUARDANDO = "cancelamento-em-aguardando"
    CANCELAMENTO_EM_EXECUCAO = "cancelamento-em-execucao"
    COMPLEMENTAR_APROVADO = "complementar-aprovado"
    COMPLEMENTAR_REJEITADO = "complementar-rejeitado"
    TRANSICOES_INVALIDAS = "transicoes-invalidas"


TODOS_CENARIOS: tuple[Cenario, ...] = tuple(Cenario)
"""Tupla imutavel com os 7 cenarios. O orchestrator (step 13) itera sobre ela."""


@dataclass(frozen=True, slots=True)
class RecursosSeed:
    """Recursos pre-criados (servico + item estoque) passados pelo orchestrator.

    Equivalente ao ``RecursosSeed`` da ``ClienteFluxoCompletoJourney``, mas sem
    ``item_estoque_qty_a_consumir``: esta journey sempre consome 1 unidade, ja
    que os cenarios focam em transicoes de estado, nao em conservacao de estoque.
    """

    servico_id: UUID
    item_estoque_id: UUID


class ClienteFluxosAlternativosJourney(UserJourney):
    """Exercita UM cenario alternativo por instancia (ver ``Cenario``)."""

    nome_journey = "cliente-fluxos-alternativos"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        recursos: RecursosSeed,
        cenario: Cenario,
        admin_access_token: str | None = None,
        rng: random.Random | None = None,
    ) -> None:
        # O sufixo no instance_id mantem o log estruturado legivel quando o
        # orchestrator roda 7 instancias em paralelo com o mesmo id base.
        super().__init__(config=config, instance_id=f"{instance_id}:{cenario.value}")
        self._recursos = recursos
        self._cenario = cenario
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
        from full_test.support.documentos import gerar_cpf, gerar_placa

        with self.log.passo("setup/admin-client"):
            self._client = SystemClient(
                self._config.base_url, timeout=self._config.http_timeout
            )
            # Token compartilhado evita rate limit 5/min em /login.
            if self._admin_access_token is not None:
                self._client.set_token(self._admin_access_token)
            else:
                self._client.login(
                    email=self._config.admin_email,
                    senha=self._config.admin_password,
                )
            self._checker = ConsistencyChecker(self._client)

        with self.log.passo("setup/criar-cliente-e-veiculo"):
            assert self._client is not None  # noqa: S101
            self._cliente = self._client.criar_cliente(
                nome=f"Cliente Alt {self._instance_id}",
                documento=gerar_cpf(self._rng),
                tipo_documento="cpf",
                contato="+55 11 900000000",
            )
            self._veiculo = self._client.adicionar_veiculo(
                self._cliente.id,
                placa=gerar_placa(self._rng),
                marca="Fiat",
                modelo="Uno",
                ano=2015,
            )

    def executar(self) -> None:
        cenario = self._cenario
        if cenario == Cenario.TRANSICOES_INVALIDAS:
            self._exec_transicoes_invalidas()
            return

        if cenario.value.startswith("cancelamento-"):
            self._exec_cancelamento()
            return

        if cenario == Cenario.COMPLEMENTAR_APROVADO:
            self._exec_complementar(aprovar=True)
            return

        if cenario == Cenario.COMPLEMENTAR_REJEITADO:
            self._exec_complementar(aprovar=False)
            return

        raise AssertionError(f"Cenario nao mapeado: {cenario!r}")

    def teardown(self) -> None:
        if self._client is not None:
            with self.log.passo("teardown/close"):
                # NAO faz logout quando o token e compartilhado — revogar
                # invalidaria outras journeys. Apenas fecha o httpx pool.
                self._client.close()

    # ---------------- cenarios ----------------

    def _exec_cancelamento(self) -> None:
        """Cria OS, avanca ate o estado-alvo e cancela; valida status publico."""
        assert self._client is not None  # noqa: S101
        assert self._checker is not None  # noqa: S101
        assert self._cliente is not None  # noqa: S101
        assert self._veiculo is not None  # noqa: S101

        self._criar_ordem_com_item()

        # Mapa estatico do enum -> estado-alvo antes do cancelamento. Separado
        # do dict em ``_exec_transicoes_invalidas`` pra cada cenario declarar
        # exatamente onde quer parar.
        alvo = {
            Cenario.CANCELAMENTO_EM_RECEBIDA: "recebida",
            Cenario.CANCELAMENTO_EM_DIAGNOSTICO: "em_diagnostico",
            Cenario.CANCELAMENTO_EM_AGUARDANDO: "aguardando_aprovacao",
            Cenario.CANCELAMENTO_EM_EXECUCAO: "em_execucao",
        }[self._cenario]

        if alvo != "recebida":
            self._avancar_ate(alvo)

        assert self._ordem is not None  # noqa: S101
        with self.log.passo(f"cancelar-em/{alvo}"):
            self._ordem = self._client.cancelar_ordem(
                self._ordem.id, motivo="teste-full-alt"
            )
            assert self._ordem.status == "cancelada", (  # noqa: S101
                f"Esperado CANCELADA, veio {self._ordem.status}"
            )

        with self.log.passo("validar-status-publico-cancelada"):
            self._checker.assert_status_publico(
                placa=self._veiculo.placa,
                documento=self._cliente.documento_formatado,
                status_esperado="cancelada",
            )

    def _exec_complementar(self, *, aprovar: bool) -> None:
        """Avanca ate EM_EXECUCAO, gera orcamento complementar, aprova/rejeita.

        Apos a decisao:
          - ``aprovar=True``  -> EM_EXECUCAO (continua com escopo ampliado) ->
                                  FINALIZADA -> ENTREGUE
          - ``aprovar=False`` -> EM_EXECUCAO (volta ao escopo original; o
                                  complementar e descartado) -> FINALIZADA ->
                                  ENTREGUE

        O contrato de rejeicao (volta a EM_EXECUCAO) foi validado contra o
        ``router.py`` em 2026-04-22. Se o codigo evoluir para levar direto a
        CANCELADA ou permanecer em AGUARDANDO_APROVACAO_COMPLEMENTAR, ajustar
        aqui e tambem a cobertura correspondente no step 12.
        """
        assert self._client is not None  # noqa: S101

        self._criar_ordem_com_item()

        # Itens adicionais so podem ser adicionados nos estados
        # ``recebida`` ou ``em_diagnostico`` (ver
        # src/ordem_servico/dominio/item_da_ordem.py:estados_permitem_modificar).
        # Entao o extra "descoberto" e adicionado AINDA em diagnostico, nao
        # em execucao. A journey simula o caso real onde o mecanico percebe
        # a necessidade durante o diagnostico inicial.
        self._avancar_ate("em_diagnostico")
        assert self._ordem is not None  # noqa: S101
        with self.log.passo("adicionar-item-adicional-em-diagnostico"):
            self._ordem = self._client.adicionar_item_ordem(
                self._ordem.id,
                servico_catalogo_id=self._recursos.servico_id,
                item_estoque_id=None,
                descricao="Item adicional descoberto",
                quantidade=1,
            )
        # Prossegue pra em_execucao; o orcamento complementar reaggregara
        # todos os itens (originais + adicional) no estado aguardando_apro_compl.
        self._avancar_ate("em_execucao")

        with self.log.passo("gerar-orcamento-complementar"):
            self._ordem = self._client.gerar_orcamento_complementar(self._ordem.id)
            assert (  # noqa: S101
                self._ordem.status == "aguardando_aprovacao_complementar"
            ), f"Esperado AGUARDANDO_APROVACAO_COMPLEMENTAR, veio {self._ordem.status}"

        if aprovar:
            with self.log.passo("aprovar-complementar"):
                self._ordem = self._client.aprovar_orcamento_complementar(
                    self._ordem.id
                )
                assert self._ordem.status == "em_execucao", (  # noqa: S101
                    f"Esperado EM_EXECUCAO pos-aprovacao-complementar, "
                    f"veio {self._ordem.status}"
                )
            with self.log.passo("finalizar-apos-complementar-aprovado"):
                self._ordem = self._client.finalizar_servico(self._ordem.id)
                assert self._ordem.status == "finalizada"  # noqa: S101
        else:
            with self.log.passo("rejeitar-complementar"):
                self._ordem = self._client.rejeitar_orcamento_complementar(
                    self._ordem.id
                )
                assert self._ordem.status == "em_execucao", (  # noqa: S101
                    f"Esperado EM_EXECUCAO pos-rejeicao-complementar, "
                    f"veio {self._ordem.status}"
                )
            with self.log.passo("finalizar-apos-complementar-rejeitado"):
                self._ordem = self._client.finalizar_servico(self._ordem.id)
                assert self._ordem.status == "finalizada"  # noqa: S101

        with self.log.passo("entregar"):
            self._ordem = self._client.registrar_entrega(self._ordem.id)
            assert self._ordem.status == "entregue"  # noqa: S101

    def _exec_transicoes_invalidas(self) -> None:
        """Verifica que 4 pares (estado, acao_invalida) resultam em 409.

        Pares cobertos:
          1. ``(RECEBIDA, finalizar_servico)`` — pular EM_DIAGNOSTICO e
             demais estados intermediarios
          2. ``(RECEBIDA, aprovar_orcamento)`` — nao ha orcamento gerado
          3. ``(EM_EXECUCAO, iniciar_diagnostico)`` — reiniciar diagnostico
             apos aprovacao
          4. ``(ENTREGUE, cancelar_ordem)`` — estado terminal

        Dois estao em ``RECEBIDA`` (testa o estado inicial); um testa re-entrada
        em estado intermediario; um testa o terminal positivo. CANCELADA (outro
        terminal) nao e testado aqui para evitar consumir uma ordem so pra isso
        — a cobertura do cenario CANCELAMENTO_EM_RECEBIDA ja exercita o
        caminho ate CANCELADA, e 4 pares sao suficientes para sinalizar
        regressoes amplas na maquina de status.
        """
        assert self._client is not None  # noqa: S101

        self._criar_ordem_com_item()
        assert self._ordem is not None  # noqa: S101

        # 1. RECEBIDA -> finalizar (deveria avancar via EM_DIAGNOSTICO)
        with (
            self.log.passo("409/finalizar-em-recebida"),
            self._esperar_conflito(),
        ):
            self._client.finalizar_servico(self._ordem.id)

        # 2. RECEBIDA -> aprovar_orcamento (nao ha orcamento gerado)
        with (
            self.log.passo("409/aprovar-em-recebida"),
            self._esperar_conflito(),
        ):
            self._client.aprovar_orcamento(self._ordem.id)

        # 3. Avanca ate EM_EXECUCAO e tenta re-iniciar diagnostico
        self._avancar_ate("em_execucao")
        with (
            self.log.passo("409/iniciar-diagnostico-em-execucao"),
            self._esperar_conflito(),
        ):
            self._client.iniciar_diagnostico(self._ordem.id)

        # 4. Leva ate ENTREGUE (terminal) e tenta cancelar
        self._ordem = self._client.finalizar_servico(self._ordem.id)
        self._ordem = self._client.registrar_entrega(self._ordem.id)
        with (
            self.log.passo("409/cancelar-em-entregue"),
            self._esperar_conflito(),
        ):
            self._client.cancelar_ordem(self._ordem.id, motivo="tentativa-ilegal")

    # ---------------- helpers ----------------

    def _criar_ordem_com_item(self) -> None:
        """Cria a OS em RECEBIDA e adiciona um item de servico + estoque."""
        assert self._client is not None  # noqa: S101
        assert self._cliente is not None  # noqa: S101
        assert self._veiculo is not None  # noqa: S101

        with self.log.passo("criar-ordem"):
            self._ordem = self._client.criar_ordem(
                cliente_id=self._cliente.id,
                veiculo_id=self._veiculo.id,
            )
            assert self._ordem.status == "recebida", (  # noqa: S101
                f"Esperado RECEBIDA, veio {self._ordem.status}"
            )
        with self.log.passo("adicionar-item-principal"):
            self._ordem = self._client.adicionar_item_ordem(
                self._ordem.id,
                servico_catalogo_id=self._recursos.servico_id,
                item_estoque_id=self._recursos.item_estoque_id,
                descricao="Item principal",
                quantidade=1,
            )

    def _avancar_ate(self, alvo: str) -> None:
        """Avanca a ordem pelo happy path ate o estado-alvo (sem sleeps).

        Ao contrario do ``_transicao`` em ``ClienteFluxoCompletoJourney``, aqui
        nao ha consulta publica apos cada passo: estes sao cenarios de
        preparacao, nao de validacao de exposicao publica — ja coberta pelo
        step 6.
        """
        assert self._client is not None  # noqa: S101
        assert self._ordem is not None  # noqa: S101

        # ``caminho`` e a sequencia linear do happy path. Cada entrada e
        # ``(estado_origem, estado_destino, acao)`` — so executa a acao se
        # o estado atual bate com ``estado_origem``, o que torna o metodo
        # re-entrante (pode ser chamado com alvos intermediarios repetidos
        # sem disparar transicao invalida).
        caminho = [
            ("recebida", "em_diagnostico", self._client.iniciar_diagnostico),
            (
                "em_diagnostico",
                "aguardando_aprovacao",
                self._client.gerar_orcamento,
            ),
            (
                "aguardando_aprovacao",
                "em_execucao",
                self._client.aprovar_orcamento,
            ),
        ]
        for origem, destino, acao in caminho:
            if self._ordem.status == alvo:
                return
            if self._ordem.status != origem:
                # Estado atual esta a frente dessa transicao; skip para o proximo.
                continue
            with self.log.passo(f"avancar/{destino}"):
                self._ordem = acao(self._ordem.id)
                assert self._ordem.status == destino, (  # noqa: S101
                    f"Esperado {destino}, veio {self._ordem.status}"
                )

    @contextmanager
    def _esperar_conflito(self) -> Iterator[None]:
        """Context manager que exige que o bloco levante ``ConflitoError`` (409).

        Qualquer outra excecao propaga normalmente (falha da journey). Se o
        bloco nao levantar nada, a journey tambem falha: isso sinaliza que a
        API afrouxou uma validacao — exatamente o tipo de regressao que a
        journey existe para pegar.
        """
        try:
            yield
        except ConflitoError:
            return
        raise AssertionError("Esperado ConflitoError (409), mas nada foi levantado")
