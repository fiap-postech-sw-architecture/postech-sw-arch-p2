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
        pass

    def bloquear_veiculo_para_remocao(self, veiculo_id: UUID) -> bool:
        pass

    def salvar(self, cliente: Cliente) -> None:
        pass

    def listar(self, offset: int = 0, limit: int = 20) -> list[Cliente]:
        pass

    def contar(self) -> int:
        pass

    def obter_por_documento(self, documento: Documento) -> Cliente | None:
        pass

    def placa_existe(
        self, placa: Placa, excluir_cliente_id: UUID | None = None
    ) -> bool:
        pass

    def obter_dados_pessoais(self, cliente_id: UUID) -> Cliente | None:
        pass

    def anonimizar_dados(self, cliente_id: UUID) -> None:
        pass

    def salvar_consentimento(self, consentimento: ConsentimentoCliente) -> None:
        pass

    def obter_consentimento(
        self, cliente_id: UUID, tipo: str
    ) -> ConsentimentoCliente | None:
        pass

    def revogar_consentimento(self, cliente_id: UUID, tipo: str) -> None:
        pass
