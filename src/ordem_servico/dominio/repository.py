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

    # Corpos `pass` (nao `...`): o CodeQL (py/ineffectual-statement) marca
    # `...` como statement sem efeito; `pass` e o stub equivalente
    # (no-op, zero custo) e nao dispara o alerta.
    def obter_por_id(self, ordem_id: UUID) -> OrdemDeServico | None:
        """Retorna a ordem pelo id, ou ``None`` se nao existir."""
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

    def obter_por_placa_e_documento(
        self, placa: str, documento: str
    ) -> list[OrdemDeServico]:
        """Lista ordens cujo veiculo bate com ``placa`` e cliente com ``documento``.

        ``documento`` pode ser CPF ou CNPJ.
        """
        pass

    def calcular_tempo_medio_execucao(self) -> float | None:
        """Tempo medio (segundos) entre ``aprovar_orcamento`` e ``finalizar_servico``.

        Retorna ``None`` se nao houver ordens finalizadas.
        """
        pass
