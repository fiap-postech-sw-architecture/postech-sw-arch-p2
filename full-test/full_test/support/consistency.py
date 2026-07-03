"""ConsistencyChecker: valida invariantes do sistema apos mutacoes.

Cada metodo ``assert_*`` leva ``SystemClient`` + contexto pre-mutacao (snapshot)
+ contexto pos-mutacao (re-fetch da API). Falha -> ``AssertionError`` com mensagem
descritiva contendo os valores observados vs esperados.

Invariantes cobertas:
  1. Maquina de status da OS: transicoes seguem ``MAQUINA_DE_STATUS``
  2. Totais do orcamento: ``orcamento.total == sum(itens.subtotal)``
  3. Metricas monotonicas: ``total`` e ``por_status[...]`` nao decrescem
  4. Status publico: ``/acompanhamento`` devolve o mesmo status do detalhe admin

Thread-safety: ``ConsistencyChecker`` usa ``SystemClient``, que NAO e
thread-safe. Cada journey deve instanciar seu proprio checker (uma instancia
por thread, ver ``orchestrator-full-e2e-test.md`` — "Run model").

A tabela ``_TRANSICOES_VALIDAS`` e uma copia manual de
``src/ordem_servico/dominio/maquina_de_status.py`` deliberadamente nao
importada — o harness mantem-se desacoplado dos internals da aplicacao para
que mudancas acidentais no dominio sejam detectadas (o teste quebra).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from full_test.client.errors import NaoEncontradoError

if TYPE_CHECKING:
    from full_test.client import models
    from full_test.client.system_client import SystemClient


_TRANSICOES_VALIDAS: dict[str, frozenset[str]] = {
    "recebida": frozenset({"em_diagnostico", "cancelada"}),
    "em_diagnostico": frozenset({"aguardando_aprovacao", "cancelada"}),
    "aguardando_aprovacao": frozenset({"em_execucao", "cancelada"}),
    "em_execucao": frozenset(
        {"finalizada", "cancelada", "aguardando_aprovacao_complementar"}
    ),
    "aguardando_aprovacao_complementar": frozenset({"em_execucao", "cancelada"}),
    "finalizada": frozenset({"entregue"}),
    "entregue": frozenset(),
    "cancelada": frozenset(),
}


class ConsistencyChecker:
    """Conjunto de validacoes que as journeys invocam apos operacoes relevantes."""

    def __init__(self, client: SystemClient) -> None:
        self._client = client

    # ---------------- state machine ----------------

    def assert_transicao_valida(self, *, de: str, para: str) -> None:
        """Verifica que ``de -> para`` esta permitido pela maquina de status.

        Uso: antes de chamar ``aprovar_orcamento(...)``, a journey sabe o estado
        atual (``de``) e o alvo esperado (``para``). Depois da chamada, re-busca
        a ordem e compara com ``para``. Esse metodo cobre a primeira metade:
        checa que a transicao e legal segundo o contrato do dominio.
        """
        permitidas = _TRANSICOES_VALIDAS.get(de)
        if permitidas is None:
            raise AssertionError(f"Estado inicial desconhecido: {de!r}")
        if para not in permitidas:
            raise AssertionError(
                f"Transicao invalida {de} -> {para}. "
                f"Permitidas a partir de {de}: {sorted(permitidas)}"
            )

    # ---------------- orcamento ----------------

    def assert_total_orcamento(self, ordem: models.OrdemDeServicoResponse) -> None:
        """Total do orcamento == soma dos subtotais dos itens da ordem (centavos)."""
        if ordem.orcamento is None:
            return
        esperado = sum(item.subtotal_centavos for item in ordem.itens)
        if ordem.orcamento.total_centavos != esperado:
            raise AssertionError(
                f"Total do orcamento {ordem.orcamento.total_centavos}c "
                f"diverge da soma dos itens {esperado}c na ordem {ordem.id}"
            )

    def assert_subtotais_dos_itens(self, ordem: models.OrdemDeServicoResponse) -> None:
        """Cada ``subtotal_centavos = preco_unitario_centavos * quantidade``."""
        for item in ordem.itens:
            esperado = item.preco_unitario_centavos * item.quantidade
            if item.subtotal_centavos != esperado:
                raise AssertionError(
                    f"Item {item.id} na ordem {ordem.id}: subtotal "
                    f"{item.subtotal_centavos}c != preco*qty {esperado}c "
                    f"({item.preco_unitario_centavos} * {item.quantidade})"
                )

    # ---------------- metricas ----------------

    def assert_metricas_monotonicas(
        self,
        *,
        anterior: models.MetricasResponse,
        atual: models.MetricasResponse,
    ) -> None:
        """``total`` e ``por_status[x]`` de ordens finalizadas/entregues so crescem.

        Observacao: ``por_status`` de estados intermediarios (EM_DIAGNOSTICO, etc.)
        pode decrescer conforme ordens avancam; essa verificacao cobre apenas
        os estados terminais (FINALIZADA, ENTREGUE, CANCELADA) e o ``total``
        global.
        """
        if atual.total < anterior.total:
            raise AssertionError(
                f"Total de ordens regrediu: {anterior.total} -> {atual.total}"
            )
        for terminal in ("finalizada", "entregue", "cancelada"):
            prev = anterior.por_status.get(terminal, 0)
            cur = atual.por_status.get(terminal, 0)
            if cur < prev:
                raise AssertionError(
                    f"por_status[{terminal}] regrediu: {prev} -> {cur}"
                )

    # ---------------- acompanhamento publico ----------------

    def assert_status_publico(
        self,
        *,
        placa: str,
        documento: str,
        status_esperado: str,
    ) -> None:
        """Consulta o endpoint publico e compara com ``status_esperado``.

        NAO requer autenticacao — usa ``SystemClient.sem_autenticacao()``
        (step 2.4). E o helper oficial que step 6 chama apos cada transicao
        da ordem.
        """
        publico = self._client.sem_autenticacao()
        try:
            resposta = publico.consultar_acompanhamento(
                placa=placa, documento=documento
            )
        finally:
            publico.close()
        if resposta.status != status_esperado:
            raise AssertionError(
                f"/acompanhamento(placa={placa}, doc={documento}) retornou "
                f"status={resposta.status!r}, esperado={status_esperado!r}"
            )

    def assert_acompanhamento_404(
        self,
        *,
        placa: str,
        documento: str,
    ) -> None:
        """Variante do acompanhamento: afirma que NAO existe ordem pro par.

        Usado por RbacMatrixJourney (step 12) para verificar o shape constante
        do 404 (placa-errada e doc-errado retornam a MESMA resposta).
        """
        publico = self._client.sem_autenticacao()
        try:
            try:
                resposta = publico.consultar_acompanhamento(
                    placa=placa, documento=documento
                )
            except NaoEncontradoError:
                return
            raise AssertionError(
                f"Esperado 404 para (placa={placa}, doc={documento}), "
                f"mas veio {resposta!r}"
            )
        finally:
            publico.close()
