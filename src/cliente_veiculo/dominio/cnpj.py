from __future__ import annotations

import re
from dataclasses import dataclass

from brutils.cnpj import is_valid

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
class CNPJ(ValueObject):
    """Value Object de CNPJ brasileiro.

    Valida via `brutils.cnpj.is_valid`, normaliza removendo mascara, e expõe
    formatacao `XX.XXX.XXX/XXXX-XX` e mascaramento (LGPD). Imutavel.
    """

    numero: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "numero", _normalizar_e_validar(self.numero, "CNPJ"))

    def formatado(self) -> str:
        """Retorna o CNPJ no padrao `XX.XXX.XXX/XXXX-XX`."""
        n = self.numero
        return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"

    def mascarado(self) -> str:
        """Retorna o CNPJ com os digitos iniciais ocultos (seguro para logs)."""
        n = self.numero
        return f"**.***.***/**{n[10:12]}-{n[12:]}"

    def __repr__(self) -> str:
        return f"CNPJ(numero='{self.mascarado()}')"
