from __future__ import annotations

import re
from dataclasses import dataclass

from src.compartilhado.dominio.value_object import ValueObject

_PADRAO_ANTIGA = re.compile(r"^[A-Z]{3}\d{4}$")
_PADRAO_MERCOSUL = re.compile(r"^[A-Z]{3}\d[A-Z]\d{2}$")


@dataclass(frozen=True, slots=True)
class Placa(ValueObject):
    """Value Object de placa veicular brasileira.

    Aceita o padrao antigo `ABC1234` e o padrao Mercosul `ABC1D23`. Normaliza
    o valor para uppercase e remove hifens. Imutavel.
    """

    valor: str

    def __post_init__(self) -> None:
        valor = self.valor.upper().replace("-", "")
        if not (_PADRAO_ANTIGA.match(valor) or _PADRAO_MERCOSUL.match(valor)):
            # Sem ecoar o valor: placa e PII e o handler global de ValueError
            # devolve str(exc) no corpo do 422 (TD-033/issue #126).
            msg = "Placa invalida"
            raise ValueError(msg)
        object.__setattr__(self, "valor", valor)
