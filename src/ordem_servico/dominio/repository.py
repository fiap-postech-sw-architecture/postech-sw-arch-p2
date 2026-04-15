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

    def obter_por_id(self, ordem_id: UUID) -> OrdemDeServico | None:
        """Retorna a ordem pelo id, ou ``None`` se nao existir."""
        ...

    def salvar(self, ordem: OrdemDeServico) -> None:
        """Persiste a ordem (insert ou update conforme a identidade)."""
        ...

    def listar(self, offset: int = 0, limit: int = 20) -> list[OrdemDeServico]:
        """Pagina ordens em ordem deterministica (por id)."""
        ...

    def contar(self) -> int:
        """Total de ordens persistidas."""
        ...

    def contar_por_status(self) -> dict[str, int]:
        """Mapa ``status.value -> contagem`` para todas as ordens."""
        ...

    def existe_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        """Indica se o cliente possui alguma ordem em estado nao terminal."""
        ...

    def existe_ativa_para_veiculo(self, veiculo_id: UUID) -> bool:
        """Indica se o veiculo possui alguma ordem em estado nao terminal."""
        ...

    def existe_ativa_com_item_estoque(self, item_estoque_id: UUID) -> bool:
        """Indica se algum item de estoque referenciado esta em uso por ordem ativa."""
        ...

    def obter_por_placa_e_documento(
        self, placa: str, documento: str
    ) -> list[OrdemDeServico]:
        """Lista ordens cujo veiculo bate com ``placa`` e cliente com ``documento``.

        ``documento`` pode ser CPF ou CNPJ.
        """
        ...

    def calcular_tempo_medio_execucao(self) -> float | None:
        """Tempo medio (segundos) entre ``aprovar_orcamento`` e ``finalizar_servico``.

        Retorna ``None`` se nao houver ordens finalizadas.
        """
        ...
