from __future__ import annotations

from typing import Protocol


class Documento(Protocol):
    """Contrato para documentos de identificacao fiscal (CPF, CNPJ).

    Define a interface comum exigida pelo agregado Cliente e pelos repositorios.
    Implementacoes (CPF, CNPJ) satisfazem este Protocol estruturalmente: basta
    expor `numero` (read-only), `formatado()` e `mascarado()`.
    """

    @property
    def numero(self) -> str:
        """Numero puro do documento (sem mascara), usado para busca por hash."""
        ...

    def formatado(self) -> str:
        """Retorna o documento formatado por extenso para exibicao ao usuario."""
        ...

    def mascarado(self) -> str:
        """Retorna o documento com os digitos centrais ocultos (seguro para logs)."""
        ...
