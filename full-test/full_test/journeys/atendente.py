"""AtendenteJourney: fluxo tipico de um atendente da oficina.

Passos executados por uma instancia:

  1. login com credencial ATENDENTE (``atendente-00@full-test.local``, semeada
     pelo step 3 via DB bypass)
  2. criar cliente (CPF, dados sinteticos gerados pelo ``support.documentos``)
  3. cadastrar 2 veiculos pro cliente
  4. atualizar cliente (nome/contato)
  5. registrar consentimentos (``marketing``, ``comunicacoes``)
  6. exportar dados pessoais (LGPD artigo 15/18) e validar shape
  7. revogar consentimento ``marketing``
  8. remover um veiculo
  9. listar veiculos do cliente e afirmar que restou apenas 1
 10. excluir dados pessoais (direito ao esquecimento) e validar 404 posterior

Nao toca em ordem de servico — esse fluxo e do step 9 (``MecanicoJourney``).

Marker pytest aplicado no entrypoint (step 14): ``@pytest.mark.slow`` (instancia
viva HTTP+DB, sem sleep obrigatorio). Nao tem sleeps reais, entao roda em CI.
"""

from __future__ import annotations

import contextlib
import random
from typing import TYPE_CHECKING

from full_test.client.system_client import SystemClient
from full_test.journeys.base import UserJourney
from full_test.support.consistency import ConsistencyChecker

if TYPE_CHECKING:
    from full_test.client import models
    from full_test.seeders.config import FullTestConfig


class AtendenteJourney(UserJourney):
    """Exercita o fluxo de um atendente no contexto Cliente+Veiculo.

    Cobre cadastro, atualizacao, consentimentos (LGPD) e direito ao
    esquecimento. Cada instancia opera no proprio cliente (isolamento de
    dados — ver orchestrator secao "Isolamento de dados entre journeys").
    """

    nome_journey = "atendente"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        atendente_email: str,
        atendente_senha: str,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(config=config, instance_id=instance_id)
        self._atendente_email = atendente_email
        self._atendente_senha = atendente_senha
        # RNG per-instance: seed + instance_id garante CPFs/placas unicos
        # quando N journeys rodam em paralelo com o mesmo seed.
        # ``S311`` liberado: este RNG e dado de teste, nunca cripto.
        self._rng = rng or random.Random(f"{config.seed}-{instance_id}")  # noqa: S311
        self._client: SystemClient | None = None
        self._checker: ConsistencyChecker | None = None
        self._cliente: models.ClienteResponse | None = None
        self._veiculos: list[models.VeiculoResponse] = []

    # ---------------- ciclo de vida ----------------

    def setup(self) -> None:
        with self.log.passo("setup/login-atendente"):
            self._client = SystemClient(
                self._config.base_url, timeout=self._config.http_timeout
            )
            self._client.login(email=self._atendente_email, senha=self._atendente_senha)
            self._checker = ConsistencyChecker(self._client)

    def executar(self) -> None:
        from full_test.support.documentos import gerar_cpf, gerar_placa

        assert self._client is not None  # noqa: S101

        # 1. criar cliente
        with self.log.passo("criar-cliente"):
            self._cliente = self._client.criar_cliente(
                nome=f"Cliente Atd {self._instance_id}",
                documento=gerar_cpf(self._rng),
                tipo_documento="cpf",
                contato="+55 11 911111111",
            )

        # 2. cadastrar 2 veiculos (duas marcas/modelos diferentes pra distinguir no log)
        assert self._cliente is not None  # noqa: S101
        for i in range(2):
            with self.log.passo(f"cadastrar-veiculo-{i}"):
                veiculo = self._client.adicionar_veiculo(
                    self._cliente.id,
                    placa=gerar_placa(self._rng),
                    marca="Fiat" if i == 0 else "Volkswagen",
                    modelo="Palio" if i == 0 else "Gol",
                    ano=2018 + i,
                )
                self._veiculos.append(veiculo)

        # 3. atualizar cliente (nome + contato)
        with self.log.passo("atualizar-cliente"):
            self._cliente = self._client.atualizar_cliente(
                self._cliente.id,
                nome=self._cliente.nome + " (atualizado)",
                contato="+55 11 922222222",
            )

        # 4. registrar consentimentos
        for tipo in ("marketing", "comunicacoes"):
            with self.log.passo(f"consentimento-registrar/{tipo}"):
                self._client.registrar_consentimento(self._cliente.id, tipo=tipo)

        # 5. exportar dados pessoais (LGPD). Validar shape minimo: nome atualizado
        #    precisa aparecer na exportacao — se nao aparecer, ou a atualizacao nao
        #    persistiu ou a exportacao nao le o dado corrente.
        with self.log.passo("lgpd-exportar-dados"):
            dados = self._client.exportar_dados_pessoais(self._cliente.id)
            assert self._cliente.nome in dados.nome, (  # noqa: S101
                f"dados exportados nao incluem nome atualizado: "
                f"esperado conter {self._cliente.nome!r}, veio {dados.nome!r}"
            )

        # 6. revogar consentimento marketing (o outro — comunicacoes — permanece)
        with self.log.passo("consentimento-revogar/marketing"):
            self._client.revogar_consentimento(self._cliente.id, tipo="marketing")

        # 7. remover o primeiro veiculo cadastrado
        veiculo_removido = self._veiculos[0]
        with self.log.passo("remover-veiculo"):
            self._client.remover_veiculo(self._cliente.id, veiculo_removido.id)

        # 8. listar veiculos -> esperar apenas o segundo
        with self.log.passo("listar-veiculos-apos-remocao"):
            restantes = self._client.listar_veiculos(self._cliente.id)
            assert len(restantes) == 1, (  # noqa: S101
                f"esperado 1 veiculo restante, veio {len(restantes)}"
            )
            assert restantes[0].id != veiculo_removido.id, (  # noqa: S101
                f"veiculo removido {veiculo_removido.id} ainda aparece na lista"
            )

        # 9. excluir dados pessoais (direito ao esquecimento)
        with self.log.passo("lgpd-excluir-dados"):
            self._client.excluir_dados_pessoais(self._cliente.id)

        # 10. apos exclusao, valida que a ANONIMIZACAO aconteceu. Contrato
        #     LGPD deste app: DELETE /dados-pessoais nao apaga a linha; ela
        #     sobrescreve nome/contato/documento com o literal ``ANONIMIZADO``
        #     e marca ``ativo=False`` (ver src/.../repository.anonimizar_dados).
        #     A journey confirma o novo estado via GET /clientes/{id}.
        with self.log.passo("lgpd-validar-anonimizacao"):
            cliente_apos = self._client.obter_cliente(self._cliente.id)
            assert cliente_apos.nome == "ANONIMIZADO", (  # noqa: S101
                f"esperado nome ANONIMIZADO apos exclusao LGPD, "
                f"veio {cliente_apos.nome!r}"
            )
            assert not cliente_apos.ativo, (  # noqa: S101
                "esperado ativo=False apos exclusao LGPD"
            )

    def teardown(self) -> None:
        if self._client is not None:
            with (
                self.log.passo("teardown/logout"),
                contextlib.suppress(Exception),
            ):
                self._client.logout()
            self._client.close()
