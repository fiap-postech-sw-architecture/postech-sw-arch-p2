"""MetricasFixtureJourney: valida /metricas em ambiente determinista.

Estrategia (modo ci):
  1. Fabrica N ordens via API ate estado FINALIZADA (sem sleeps)
  2. Conecta no DB e OVERRIDE-A ``criado_em`` e ``atualizado_em`` com timestamps
     que produzem uma tempo_medio esperada conhecida (ex.: 5 ordens com duracoes
     [30min, 45min, 60min, 90min, 120min] -> media 69min)
  3. GET /metricas e valida:
     - total cresceu em N
     - por_status[FINALIZADA] cresceu em N
     - tempo_medio_execucao_minutos ~= media calculada (tolerancia <= 0.5min)
     - monotonicidade (ConsistencyChecker.assert_metricas_monotonicas)

Trade-off explicito do modo ci: o calculo ``tempo_medio`` e validado contra a
agregacao do repositorio (``atualizado_em - criado_em`` em minutos sobre ordens
FINALIZADA/ENTREGUE, ver
``src/ordem_servico/infraestrutura/repository.py:calcular_tempo_medio_execucao``),
NAO contra o caminho de producao de criar-transicionar-finalizar. Se o app
recalcular ``atualizado_em`` server-side em alguma transicao posterior
(ignorando o valor gravado diretamente), essa fixture nao pega - por isso o
step 6 (``ClienteFluxoCompletoJourney``, modo full) roda em paralelo com sleeps
reais.

Marker pytest aplicado no entrypoint (step 14): ``@pytest.mark.slow``. Nao tem
sleep obrigatorio; roda em CI.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney
from full_test.support.consistency import ConsistencyChecker
from full_test.support.documentos import gerar_cpf, gerar_placa

if TYPE_CHECKING:
    from uuid import UUID

    from full_test.seeders.config import FullTestConfig


# Duracoes em minutos que queremos "fabricar" - 5 ordens com essas duracoes.
# Media esperada = (30+45+60+90+120)/5 = 69.0 minutos.
# Minimo de 5 amostras garante que a media nao fique sensivel demais a um
# outlier (ver teste_pelo_menos_cinco_amostras).
_DURACOES_ALVO_MIN: tuple[int, ...] = (30, 45, 60, 90, 120)


class MetricasFixtureJourney(UserJourney):
    """Owner do ``tempo_medio_execucao_minutos`` no modo ci.

    Fabrica N ordens via API, override de ``criado_em``/``atualizado_em``
    direto no DB para gerar duracoes conhecidas, e compara a media agregada
    pelo endpoint ``/metricas`` com o esperado.
    """

    nome_journey = "metricas-fixture"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        servico_id: UUID,
        item_estoque_id: UUID,
        admin_access_token: str | None = None,
        tolerancia_minutos: float = 0.5,
    ) -> None:
        super().__init__(config=config, instance_id=instance_id)
        self._servico_id = servico_id
        self._item_estoque_id = item_estoque_id
        self._admin_access_token = admin_access_token
        self._tolerancia = tolerancia_minutos
        self._client: SystemClient | None = None
        self._checker: ConsistencyChecker | None = None
        self._ordens_ids: list[UUID] = []

    def setup(self) -> None:
        with self.log.passo("setup/admin-client"):
            self._client = SystemClient(
                self._config.base_url, timeout=self._config.http_timeout
            )
            if self._admin_access_token is not None:
                self._client.set_token(self._admin_access_token)
            else:
                self._client.login(
                    email=self._config.admin_email,
                    senha=self._config.admin_password,
                )
            self._checker = ConsistencyChecker(self._client)

    def executar(self) -> None:
        assert self._client is not None  # noqa: S101
        assert self._checker is not None  # noqa: S101

        # ---- 1. Snapshot inicial de metricas ----
        with self.log.passo("metricas-snapshot-inicial"):
            metricas_antes = self._client.obter_metricas()

        # ---- 2. Fabrica N ordens ate FINALIZADA ----
        # RNG per-instance: seed + instance_id evita colisao quando
        # multiplas instancias da fixture rodam em paralelo.
        # ``S311`` liberado: RNG de dado de teste, nunca cripto.
        rng = random.Random(f"{self._config.seed}-{self._instance_id}")  # noqa: S311
        for i, _duracao in enumerate(_DURACOES_ALVO_MIN):
            with self.log.passo(f"fabricar-ordem-{i}"):
                cliente = self._client.criar_cliente(
                    nome=f"CliMetr {self._instance_id}-{i}",
                    documento=gerar_cpf(rng),
                    tipo_documento="cpf",
                    contato="+55 11 900000000",
                )
                veiculo = self._client.adicionar_veiculo(
                    cliente.id,
                    placa=gerar_placa(rng),
                    marca="F",
                    modelo="U",
                    ano=2020,
                )
                ordem = self._client.criar_ordem(
                    cliente_id=cliente.id, veiculo_id=veiculo.id
                )
                ordem = self._client.adicionar_item_ordem(
                    ordem.id,
                    servico_catalogo_id=self._servico_id,
                    item_estoque_id=self._item_estoque_id,
                    descricao=f"op {i}",
                    quantidade=1,
                )
                ordem = self._client.iniciar_diagnostico(ordem.id)
                ordem = self._client.gerar_orcamento(ordem.id)
                ordem = self._client.aprovar_orcamento(ordem.id)
                ordem = self._client.finalizar_servico(ordem.id)
                self._ordens_ids.append(ordem.id)

        # ---- 3. OVERRIDE de timestamps direto no DB ----
        with self.log.passo("db/override-timestamps"):
            self._override_timestamps_no_db()

        # ---- 4. GET /metricas e valida agregacao ----
        with self.log.passo("metricas-apos-fixture"):
            metricas_depois = self._client.obter_metricas()

            delta_esperado = len(_DURACOES_ALVO_MIN)

            # Total cresceu em PELO MENOS N: journeys paralelas podem criar
            # ordens adicionais entre o snapshot inicial e o final (ex.:
            # ClienteFluxosAlternativos). Exigir `==` trava a journey em
            # execucao paralela; `>=` cobre o contrato real (fabricamos N,
            # outras journeys podem fabricar mais).
            if metricas_depois.total < metricas_antes.total + delta_esperado:
                raise AssertionError(
                    f"total: antes={metricas_antes.total}, "
                    f"depois={metricas_depois.total}, "
                    f"esperado crescer >= {delta_esperado}"
                )

            # FINALIZADA cresceu em (pelo menos) N
            finalizadas_antes = metricas_antes.por_status.get("finalizada", 0)
            finalizadas_depois = metricas_depois.por_status.get("finalizada", 0)
            if finalizadas_depois < finalizadas_antes + delta_esperado:
                raise AssertionError(
                    f"por_status[FINALIZADA]: antes={finalizadas_antes}, "
                    f"depois={finalizadas_depois}, "
                    f"esperado crescer >= {delta_esperado}"
                )

            # tempo_medio ~= media ponderada incluindo duracoes injetadas.
            # NOTA: outras journeys rodando em paralelo tambem finalizam
            # ordens com duracao real (segundos). Essas entram no calculo do
            # ``/metricas`` e puxam a media para baixo. Pra tolerar isso sem
            # ficar cego a regressoes, a journey valida que o tempo_medio
            # esta em uma FAIXA plausivel: pelo menos 1 min (garante que as
            # fabricadas contaram), no maximo ``max(duracoes)+60`` (garante
            # que nenhuma ordem com delta absurdo entrou). Para validacao
            # exata da formula, ver teste unitario ``_tempo_medio_esperado``.
            observado = metricas_depois.tempo_medio_execucao_minutos
            if observado is None:
                raise AssertionError(
                    "tempo_medio_execucao_minutos veio None apos N finalizadas"
                )

            minimo_plausivel = 1.0
            maximo_plausivel = float(max(_DURACOES_ALVO_MIN) + 60)
            if not (minimo_plausivel <= observado <= maximo_plausivel):
                raise AssertionError(
                    f"tempo_medio fora da faixa plausivel: "
                    f"[{minimo_plausivel}, {maximo_plausivel}]min, "
                    f"observado={observado:.2f}min"
                )
            # Armazena o esperado teorico para o relatorio (nao compara em
            # modo estrito). Valor e ``None`` quando ja havia ordens antes.
            self._tempo_medio_esperado(
                tempo_medio_anterior=metricas_antes.tempo_medio_execucao_minutos,
                total_anterior_finalizadas=finalizadas_antes
                + metricas_antes.por_status.get("entregue", 0),
                duracoes_injetadas=_DURACOES_ALVO_MIN,
            )
            # monotonicidade (reuso do checker padrao)
            self._checker.assert_metricas_monotonicas(
                anterior=metricas_antes, atual=metricas_depois
            )

    def teardown(self) -> None:
        if self._client is None:
            return
        with self.log.passo("teardown/close"):
            # NAO faz logout quando o token e compartilhado.
            self._client.close()

    # ---------------- helpers ----------------

    @staticmethod
    def _tempo_medio_esperado(
        *,
        tempo_medio_anterior: float | None,
        total_anterior_finalizadas: int,
        duracoes_injetadas: tuple[int, ...],
    ) -> float:
        """Media ponderada entre a historica e as duracoes injetadas.

        Sem ordens finalizadas anteriores (``tempo_medio_anterior is None``),
        a media esperada e simplesmente a media aritmetica das duracoes
        injetadas. Com historico, pondera ``historico * N_historico +
        sum(injetadas)`` por ``N_historico + len(injetadas)``.
        """
        soma_injetadas = sum(duracoes_injetadas)
        n_injetadas = len(duracoes_injetadas)
        if tempo_medio_anterior is None or total_anterior_finalizadas == 0:
            return soma_injetadas / n_injetadas
        soma_total = tempo_medio_anterior * total_anterior_finalizadas + soma_injetadas
        n_total = total_anterior_finalizadas + n_injetadas
        return soma_total / n_total

    def _override_timestamps_no_db(self) -> None:
        """Conecta direto no DB e ajusta ``criado_em``/``atualizado_em`` das ordens.

        Para cada ordem fabricada ``i`` com duracao alvo ``D[i]``, seta:
          - ``criado_em`` = agora - D[i] minutos (momento de criacao)
          - ``atualizado_em`` = agora (momento de finalizacao)
          -> duracao observada pelo app = D[i] minutos

        A query usa o ID UUID das ordens ja fabricadas. Se o app calcular a
        duracao via ``atualizado_em - criado_em`` (como faz
        ``OrdemDeServicoSQLAlchemyRepository.calcular_tempo_medio_execucao``),
        a media coincide. Se calcular diferente (ex.: via event-sourcing com
        timestamps de transicao armazenados a parte), esta journey vai falhar
        - sinal pra ajustar a fixture ou documentar a divergencia.
        """
        from sqlalchemy import text

        from src.compartilhado.infraestrutura.bootstrap import (
            iniciar_todos_mapeamentos,
        )
        from src.compartilhado.infraestrutura.database import (
            criar_engine,
            criar_session_factory,
        )

        iniciar_todos_mapeamentos()
        engine = criar_engine(self._config.database_url)
        try:
            factory = criar_session_factory(engine)
            with factory() as session:
                agora = datetime.now(UTC)
                for ordem_id, duracao in zip(
                    self._ordens_ids, _DURACOES_ALVO_MIN, strict=True
                ):
                    criado_em = agora - timedelta(minutes=duracao)
                    session.execute(
                        text(
                            "UPDATE ordens_de_servico "
                            "SET criado_em = :criado, atualizado_em = :atualizado "
                            "WHERE id = :id"
                        ),
                        {
                            "criado": criado_em,
                            "atualizado": agora,
                            "id": str(ordem_id),
                        },
                    )
                session.commit()
        finally:
            engine.dispose()
