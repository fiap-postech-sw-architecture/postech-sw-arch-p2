"""Fase2ContratosJourney: exercita os contratos novos da fase 2 (RF-020..023).

Uma unica journey cobre as quatro mudancas de contrato introduzidas na fase 2,
cada uma sobre uma OS dedicada para manter os estados isolados:

- RF-020: ``criar_ordem`` aceita ``servicos`` e ``pecas`` no body; a OS ja
  nasce com itens (sem precisar de ``adicionar_item_ordem`` depois).
- RF-021: as respostas trazem ``situacao`` (rotulo legivel). A journey afirma
  ``"Recebida"`` na criacao e ``"Em diagnóstico"`` apos iniciar diagnostico.
- RF-022: decisao de orcamento via canal externo (webhook) — aprovada leva a
  ``em_execucao`` e recusada a ``cancelada``. Se o canal estiver desativado no
  servidor (503), a journey loga e segue (skip) em vez de falhar.
- RF-023: ``listar_ordens(incluir_encerradas=...)`` filtra estados terminais e
  ordena por prioridade de status (em_execucao antes de recebida).

Persona: time interno da oficina (credencial admin compartilhada, como nas
demais journeys). A parte do webhook usa um canal publico autenticado por
token, sem Bearer.

Marker conceitual: ``@pytest.mark.slow`` (sem sleep obrigatorio; roda em CI).
O marker e aplicado pelo pytest entrypoint, nao nesta classe.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

from full_test.client.errors import ErroInternoError
from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney

if TYPE_CHECKING:
    from uuid import UUID

    from full_test.client import models
    from full_test.seeders.config import FullTestConfig

# Rotulos legiveis da fase 2 (RF-021). Lidos direto do payload; nao importamos
# nenhum modulo do backend (ex.: situacao_de) — apenas comparamos strings.
_SITUACAO_RECEBIDA = "Recebida"
_SITUACAO_EM_DIAGNOSTICO = "Em diagnóstico"
_SITUACAO_EM_EXECUCAO = "Em execução"
_SITUACAO_CANCELADA = "Cancelada"


@dataclass(frozen=True, slots=True)
class RecursosSeed:
    """Recursos pre-criados (servico + item estoque) consumidos pela journey.

    Passados pelo orchestrator (builder) apos ``seed_completo``. A journey usa
    o servico em ``servicos`` e a peca (servico + item de estoque) em ``pecas``
    do ``criar_ordem`` (RF-020).
    """

    servico_id: UUID
    item_estoque_id: UUID


class Fase2ContratosJourney(UserJourney):
    """Exercita RF-020, RF-021, RF-022 e RF-023 numa unica passada."""

    nome_journey = "fase2-contratos"

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
        self._cliente: models.ClienteResponse | None = None
        self._veiculo: models.VeiculoResponse | None = None

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

        with self.log.passo("setup/criar-cliente-e-veiculo"):
            assert self._client is not None  # noqa: S101
            self._cliente = self._client.criar_cliente(
                nome=f"Cliente Fase2 {self._instance_id}",
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
        assert self._client is not None  # noqa: S101
        assert self._cliente is not None  # noqa: S101
        assert self._veiculo is not None  # noqa: S101

        # RF-020 + RF-021: criar com itens inline e afirmar situacao.
        ordem_inline = self._exec_rf020_rf021()
        # RF-022: aprovada (em_execucao) numa OS, recusada (cancelada) noutra.
        ordem_em_execucao = self._exec_rf022_aprovada()
        self._exec_rf022_recusada()
        # RF-023: filtro de encerradas + ordenacao por prioridade de status.
        self._exec_rf023(
            ordem_aberta=ordem_inline,
            ordem_em_execucao=ordem_em_execucao,
        )

    def teardown(self) -> None:
        if self._client is not None:
            with self.log.passo("teardown/close"):
                # NAO faz logout quando o token e compartilhado — revogar
                # invalidaria outras journeys. Apenas fecha o httpx pool.
                self._client.close()

    # ---------------- requisitos ----------------

    def _exec_rf020_rf021(self) -> models.OrdemDeServicoResponse:
        """RF-020 (itens inline) + RF-021 (situacao legivel)."""
        assert self._client is not None  # noqa: S101
        assert self._cliente is not None  # noqa: S101
        assert self._veiculo is not None  # noqa: S101

        with self.log.passo("rf020/criar-ordem-com-servicos-e-pecas"):
            ordem = self._client.criar_ordem(
                cliente_id=self._cliente.id,
                veiculo_id=self._veiculo.id,
                servicos=[
                    {"servico_catalogo_id": self._recursos.servico_id, "quantidade": 1}
                ],
                pecas=[
                    {
                        "servico_catalogo_id": self._recursos.servico_id,
                        "item_estoque_id": self._recursos.item_estoque_id,
                        "quantidade": 1,
                    }
                ],
            )
            assert ordem.status == "recebida", (  # noqa: S101
                f"Esperado RECEBIDA, veio {ordem.status}"
            )
            assert ordem.itens, "RF-020: OS criada com itens inline veio sem itens"  # noqa: S101
            assert ordem.situacao == _SITUACAO_RECEBIDA, (  # noqa: S101
                f"RF-021: esperado situacao {_SITUACAO_RECEBIDA!r}, "
                f"veio {ordem.situacao!r}"
            )

        with self.log.passo("rf021/iniciar-diagnostico-confirma-situacao"):
            ordem = self._client.iniciar_diagnostico(ordem.id)
            assert ordem.status == "em_diagnostico", (  # noqa: S101
                f"Esperado EM_DIAGNOSTICO, veio {ordem.status}"
            )
            assert ordem.situacao == _SITUACAO_EM_DIAGNOSTICO, (  # noqa: S101
                f"RF-021: esperado situacao {_SITUACAO_EM_DIAGNOSTICO!r}, "
                f"veio {ordem.situacao!r}"
            )

        return ordem

    def _exec_rf022_aprovada(self) -> models.OrdemDeServicoResponse | None:
        """RF-022 caminho aprovada: webhook leva aguardando_aprovacao -> em_execucao.

        Retorna a OS resultante (em_execucao) para reuso no RF-023, ou ``None``
        se o canal estiver desativado no servidor (503 -> skip).
        """
        ordem = self._criar_ordem_em_aguardando(sufixo="aprovada")

        with self.log.passo("rf022/webhook-aprovada"):
            acomp = self._chamar_webhook(ordem.id, decisao="aprovada")
            if acomp is None:
                return None
            assert acomp.status == "em_execucao", (  # noqa: S101
                f"RF-022: esperado EM_EXECUCAO pos-aprovada, veio {acomp.status}"
            )
            assert acomp.situacao == _SITUACAO_EM_EXECUCAO, (  # noqa: S101
                f"RF-022: esperado situacao {_SITUACAO_EM_EXECUCAO!r}, "
                f"veio {acomp.situacao!r}"
            )

        # Reconsulta o detalhe admin para devolver uma OS completa ao RF-023.
        assert self._client is not None  # noqa: S101
        with self.log.passo("rf022/reconsultar-ordem-em-execucao"):
            return self._client.obter_ordem(ordem.id)

    def _exec_rf022_recusada(self) -> None:
        """RF-022 caminho recusada: webhook leva aguardando_aprovacao -> cancelada."""
        ordem = self._criar_ordem_em_aguardando(sufixo="recusada")

        with self.log.passo("rf022/webhook-recusada"):
            acomp = self._chamar_webhook(ordem.id, decisao="recusada")
            if acomp is None:
                return
            assert acomp.status == "cancelada", (  # noqa: S101
                f"RF-022: esperado CANCELADA pos-recusada, veio {acomp.status}"
            )
            assert acomp.situacao == _SITUACAO_CANCELADA, (  # noqa: S101
                f"RF-022: esperado situacao {_SITUACAO_CANCELADA!r}, "
                f"veio {acomp.situacao!r}"
            )

    def _exec_rf023(
        self,
        *,
        ordem_aberta: models.OrdemDeServicoResponse,
        ordem_em_execucao: models.OrdemDeServicoResponse | None,
    ) -> None:
        """RF-023: ``incluir_encerradas`` filtra terminais e ordena por status.

        ``ordem_aberta`` esta em ``em_diagnostico`` (RF-020/021) e
        ``ordem_em_execucao`` em ``em_execucao`` (RF-022). Para validar a
        ordenacao precisamos de ambas; se o webhook foi pulado (canal off),
        a verificacao de ordenacao tambem e pulada.
        """
        assert self._client is not None  # noqa: S101

        with self.log.passo("rf023/listar-sem-encerradas"):
            abertas = self._client.listar_ordens(incluir_encerradas=False)
            ids_abertas = {i.id for i in abertas.items}
            assert ordem_aberta.id in ids_abertas, (  # noqa: S101
                "RF-023: OS aberta deveria aparecer sem incluir_encerradas"
            )

        with self.log.passo("rf023/listar-com-encerradas"):
            todas = self._client.listar_ordens(incluir_encerradas=True)
            ids_todas = {i.id for i in todas.items}

        # O conjunto sem encerradas e subconjunto do conjunto com encerradas:
        # estados terminais (entregue/cancelada) so podem surgir com True.
        assert ids_abertas <= ids_todas, (  # noqa: S101
            "RF-023: a lista com encerradas deve conter a lista sem encerradas"
        )

        if ordem_em_execucao is None:
            with self.log.passo("rf023/ordenacao-pulada-webhook-off"):
                pass
            return

        with self.log.passo("rf023/ordenacao-em-execucao-antes-de-recebida"):
            # Garante que existem ambos os status na listagem: uma OS recebida
            # fresca (esta journey) + a em_execucao do RF-022.
            self._criar_ordem_simples(sufixo="rf023-recebida")
            lista = self._client.listar_ordens(incluir_encerradas=False, limit=100)
            # A ordenacao por prioridade de status (RF-023) garante que TODA
            # OS em_execucao precede TODA OS recebida — independente de quais
            # journeys as criaram. Validamos a propriedade na propria pagina:
            # o ultimo indice de em_execucao deve vir antes do primeiro recebida.
            idx_exec = [
                i for i, item in enumerate(lista.items) if item.status == "em_execucao"
            ]
            idx_receb = [
                i for i, item in enumerate(lista.items) if item.status == "recebida"
            ]
            assert idx_exec, (  # noqa: S101
                "RF-023: esperava ao menos uma OS em_execucao na listagem aberta"
            )
            assert idx_receb, (  # noqa: S101
                "RF-023: esperava ao menos uma OS recebida na listagem aberta"
            )
            ultimo_exec = max(idx_exec)
            primeiro_receb = min(idx_receb)
            assert ultimo_exec < primeiro_receb, (  # noqa: S101
                "RF-023: toda OS em_execucao deve vir antes de qualquer recebida "
                f"(ult.exec@{ultimo_exec}, 1o.receb@{primeiro_receb})"
            )

    # ---------------- helpers ----------------

    def _criar_ordem_simples(self, *, sufixo: str) -> models.OrdemDeServicoResponse:
        """Cria uma OS em RECEBIDA (sem itens inline) para um cliente/veiculo novos."""
        from full_test.support.documentos import gerar_cpf, gerar_placa

        assert self._client is not None  # noqa: S101

        with self.log.passo(f"criar-ordem-simples/{sufixo}"):
            cliente = self._client.criar_cliente(
                nome=f"Cli Fase2 {sufixo} {self._instance_id}",
                documento=gerar_cpf(self._rng),
                tipo_documento="cpf",
                contato="+55 11 900000000",
            )
            veiculo = self._client.adicionar_veiculo(
                cliente.id,
                placa=gerar_placa(self._rng),
                marca="Fiat",
                modelo="Uno",
                ano=2016,
            )
            ordem = self._client.criar_ordem(
                cliente_id=cliente.id, veiculo_id=veiculo.id
            )
            assert ordem.status == "recebida", (  # noqa: S101
                f"Esperado RECEBIDA, veio {ordem.status}"
            )
            return ordem

    def _criar_ordem_em_aguardando(
        self, *, sufixo: str
    ) -> models.OrdemDeServicoResponse:
        """Cria uma OS e a avanca ate AGUARDANDO_APROVACAO (criar -> diag -> orcamento).

        Usa itens inline (RF-020) para que o orcamento tenha linhas. Cada OS
        usa cliente/veiculo proprios para nao colidir com as demais.
        """
        from full_test.support.documentos import gerar_cpf, gerar_placa

        assert self._client is not None  # noqa: S101

        with self.log.passo(f"preparar-aguardando/{sufixo}/criar-cliente-veiculo"):
            cliente = self._client.criar_cliente(
                nome=f"Cli Fase2 {sufixo} {self._instance_id}",
                documento=gerar_cpf(self._rng),
                tipo_documento="cpf",
                contato="+55 11 900000000",
            )
            veiculo = self._client.adicionar_veiculo(
                cliente.id,
                placa=gerar_placa(self._rng),
                marca="Fiat",
                modelo="Uno",
                ano=2017,
            )

        with self.log.passo(f"preparar-aguardando/{sufixo}/criar-ordem"):
            ordem = self._client.criar_ordem(
                cliente_id=cliente.id,
                veiculo_id=veiculo.id,
                servicos=[
                    {"servico_catalogo_id": self._recursos.servico_id, "quantidade": 1}
                ],
                pecas=[
                    {
                        "servico_catalogo_id": self._recursos.servico_id,
                        "item_estoque_id": self._recursos.item_estoque_id,
                        "quantidade": 1,
                    }
                ],
            )

        with self.log.passo(f"preparar-aguardando/{sufixo}/diagnostico"):
            ordem = self._client.iniciar_diagnostico(ordem.id)
        with self.log.passo(f"preparar-aguardando/{sufixo}/orcamento"):
            ordem = self._client.gerar_orcamento(ordem.id)
            assert ordem.status == "aguardando_aprovacao", (  # noqa: S101
                f"Esperado AGUARDANDO_APROVACAO, veio {ordem.status}"
            )
        return ordem

    def _chamar_webhook(
        self, ordem_id: UUID, *, decisao: str
    ) -> models.AcompanhamentoResponse | None:
        """Chama o webhook de decisao; retorna ``None`` se o canal estiver off (503).

        Token nao configurado no servidor responde 503 (``ErroInternoError``):
        nesse caso a journey loga e segue (skip), nunca falhando um ambiente
        sem o canal habilitado. Qualquer outro erro propaga normalmente.
        """
        assert self._client is not None  # noqa: S101
        try:
            return self._client.decidir_orcamento_webhook(
                ordem_id,
                decisao=decisao,
                webhook_token=self._config.webhook_token,
            )
        except ErroInternoError as exc:
            if exc.status_code == HTTPStatus.SERVICE_UNAVAILABLE:
                # Canal desativado no servidor (ORCAMENTO_WEBHOOK_TOKEN ausente).
                # Skip defensivo: nao red-flaga ambiente sem o canal configurado.
                # Registra um passo bem-sucedido (skip) no relatorio da journey.
                with self.log.passo(f"webhook-skip-503/{decisao}"):
                    pass
                return None
            raise
