from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.cliente_veiculo.dominio.cliente import Cliente
    from src.cliente_veiculo.dominio.consentimento import ConsentimentoCliente
    from src.cliente_veiculo.dominio.documento import Documento
    from src.cliente_veiculo.dominio.placa import Placa


class ClienteRepository(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def obter_por_id(self, cliente_id: UUID) -> Cliente | None:
        """Busca o cliente pelo id; None se nao existir."""
        pass

    def bloquear_veiculo_para_remocao(self, veiculo_id: UUID) -> bool:
        """Trava a linha do veiculo (FOR UPDATE); False se ela ja nao existe."""
        pass

    def salvar(self, cliente: Cliente) -> None:
        """Adiciona o cliente a sessao e faz flush imediato."""
        pass

    def listar(self, offset: int = 0, limit: int = 20) -> list[Cliente]:
        """Lista paginada ordenada por nome, com id como desempate deterministico."""
        pass

    def contar(self) -> int:
        """Total de clientes cadastrados (para a paginacao de ``listar``)."""
        pass

    def obter_por_documento(self, documento: Documento) -> Cliente | None:
        """Busca pelo hash deterministico do documento; None se nao existir."""
        pass

    def placa_existe(
        self, placa: Placa, excluir_cliente_id: UUID | None = None
    ) -> bool:
        """True se a placa ja existe; excluir_cliente_id ignora o proprio cliente."""
        pass

    def anonimizar_dados(self, cliente_id: UUID) -> None:
        """Apaga PII de cliente e veiculos com tombstones, na mesma transacao (LGPD)."""
        pass

    def salvar_consentimento(self, consentimento: ConsentimentoCliente) -> None:
        """Registra o consentimento na sessao e faz flush imediato."""
        pass

    def obter_consentimento(
        self, cliente_id: UUID, tipo: str
    ) -> ConsentimentoCliente | None:
        """Consentimento mais recente do cliente no tipo; None se nunca concedido."""
        pass
