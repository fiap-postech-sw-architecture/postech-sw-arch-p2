from __future__ import annotations

import re
from dataclasses import dataclass

from brutils.cpf import is_valid

from src.compartilhado.dominio.value_object import ValueObject

_NAO_DIGITO = re.compile(r"\D")


def _normalizar_e_validar(numero: str, rotulo: str) -> str:
    """Remove mascara e valida via brutils; levanta ValueError se invalido."""
    normalizado = _NAO_DIGITO.sub("", numero)
    if not is_valid(normalizado):
        msg = f"{rotulo} invalido"
        raise ValueError(msg)
    return normalizado


@dataclass(frozen=True, slots=True)
class CPF(ValueObject):
    """Value Object de CPF brasileiro.

    Valida via `brutils.cpf.is_valid`, normaliza removendo mascara, e expõe
    formatacao `XXX.XXX.XXX-XX` e mascaramento `***.***.***-XX` (LGPD).
    """

    numero: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "numero", _normalizar_e_validar(self.numero, "CPF"))

    def formatado(self) -> str:
        """Retorna o CPF no padrao `XXX.XXX.XXX-XX`."""
        n = self.numero
        return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"

    def mascarado(self) -> str:
        """Retorna o CPF com os 9 primeiros digitos ocultos (seguro para logs)."""
        n = self.numero
        return f"***.***.***-{n[9:]}"

    def __repr__(self) -> str:
        return f"CPF(numero='{self.mascarado()}')"
