"""Porta de persistencia da ``OrdemDeServico`` (Protocol)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico


class OrdemDeServicoRepository(Protocol):
    """Contrato de persistencia para o agregado ``OrdemDeServico``.

    Implementacoes (em ``infraestrutura/``) devem ser transacionais sob
    a Unit of Work compartilhada. Metodos de leitura podem ser servidos
    por views/read-models em PRs futuros sem alterar o contrato.
    """

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def obter_por_id(
        self, ordem_id: UUID, *, com_lock: bool = False
    ) -> OrdemDeServico | None:
        """Retorna a ordem pelo id, ou ``None`` se nao existir.

        ``com_lock=True`` carrega a linha com ``SELECT ... FOR UPDATE``
        (lock pessimista) para serializar transicoes concorrentes da mesma
        ordem (issue #82). Opcao de infraestrutura exposta no contrato sem
        vazar SQL para o dominio: o helper ``_obter_ordem`` da aplicacao a
        repassa apenas no caminho de MUTACAO/transicao; os caminhos de
        leitura usam o default ``False`` (sem lock).
        """
        pass

    def salvar(self, ordem: OrdemDeServico) -> None:
        """Persiste a ordem (insert ou update conforme a identidade)."""
        pass

    def listar(
        self,
        offset: int = 0,
        limit: int = 20,
        *,
        incluir_encerradas: bool = False,
    ) -> list[OrdemDeServico]:
        """Pagina ordens por prioridade de status + antiguidade (RF-023).

        Prioridade RN-018/RN-020: EM_EXECUCAO > AGUARDANDO_APROVACAO (junto
        com AGUARDANDO_APROVACAO_COMPLEMENTAR) > EM_DIAGNOSTICO > RECEBIDA;
        dentro do grupo, ``criado_em ASC`` com desempate por ``id``. Por
        padrao exclui estados encerrados (FINALIZADA/ENTREGUE/CANCELADA,
        RN-019/RN-020); ``incluir_encerradas=True`` devolve a visao completa
        com encerradas ao final da ordenacao.
        """
        pass

    def contar(self, *, incluir_encerradas: bool = True) -> int:
        """Total de ordens persistidas.

        Com ``incluir_encerradas=False`` conta apenas o universo da
        listagem padrao (exclui FINALIZADA/ENTREGUE/CANCELADA), mantendo a
        paginacao consistente com ``listar``. O default ``True`` preserva a
        semantica historica de "total persistido" (ex.: metricas).
        """
        pass

    def contar_por_status(self) -> dict[str, int]:
        """Mapa ``status.value -> contagem`` para todas as ordens."""
        pass

    def existe_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        """Indica se o cliente possui alguma ordem em estado nao terminal."""
        pass

    def existe_ativa_para_veiculo(self, veiculo_id: UUID) -> bool:
        """Indica se o veiculo possui alguma ordem em estado nao terminal."""
        pass

    def existe_ativa_com_item_estoque(self, item_estoque_id: UUID) -> bool:
        """Indica se algum item de estoque referenciado esta em uso por ordem ativa."""
        pass

    def obter_mais_recente_por_placa_e_documento(
        self, placa: str, documento: str
    ) -> OrdemDeServico | None:
        """Ordem mais recente cujo veiculo bate com ``placa`` e cliente com
        ``documento`` (CPF ou CNPJ), ou ``None`` se nenhuma casar.

        A selecao da mais recente (``criado_em``) acontece no banco
        (``ORDER BY ... LIMIT 1``): a consulta publica de acompanhamento
        nao precisa hidratar o historico completo do par.
        """
        pass

    def calcular_tempo_medio_execucao(self) -> float | None:
        """Tempo medio (MINUTOS) entre ``criado_em`` e ``atualizado_em``.

        Media sobre ordens FINALIZADA/ENTREGUE (proxy do ciclo completo da
        OS; o DTO downstream se chama ``tempo_medio_execucao_minutos``).
        Retorna ``None`` se nao houver ordens nesses estados.
        """
        pass
