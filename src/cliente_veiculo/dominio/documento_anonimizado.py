from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.compartilhado.dominio.value_object import ValueObject

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentoAnonimizado(ValueObject):
    """Value Object que marca o documento de um Cliente anonimizado via LGPD.

    Substitui o patch tatico do PR #78 (literal ``"ANONIMIZADO"`` em CPF)
    por um tipo proprio. Apos ``ClienteRepository.anonimizar_dados`` correr,
    o ``Cliente`` e reidratado com este VO em vez de um CPF/CNPJ — assim
    ``isinstance(doc, CPF)`` e ``isinstance(doc, CNPJ)`` voltam a ser
    coerentes (nunca True para clientes anonimizados).

    O ``cliente_id`` permite reconstruir o tombstone unico
    ``"ANONIMIZADO:{cliente_id}"`` que preserva a constraint UNIQUE de
    ``documento_hash`` quando varios clientes sao anonimizados.
    """

    cliente_id: UUID

    @property
    def numero(self) -> str:
        """Retorna o sentinela ``"ANONIMIZADO"`` para satisfazer ``Documento``."""
        return "ANONIMIZADO"

    def formatado(self) -> str:
        """Retorna ``"ANONIMIZADO"`` — sem PII para vazar em respostas da API."""
        return "ANONIMIZADO"

    def mascarado(self) -> str:
        """Retorna ``"ANONIMIZADO"`` — seguro para logs."""
        return "ANONIMIZADO"

    def __repr__(self) -> str:
        return f"DocumentoAnonimizado(cliente_id={self.cliente_id})"
