from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from src.compartilhado.dominio.value_object import ValueObject

_DUAS_CASAS = Decimal("0.01")
_TAMANHO_CODIGO_MOEDA = 3


@dataclass(frozen=True, slots=True)
class Dinheiro(ValueObject):
    """Value Object monetario com moeda e precisao de 2 casas decimais.

    Usa Decimal para aritmetica exata (nunca float). Impoe valores nao negativos,
    finitos, e codigo de moeda ISO 4217 com 3 letras maiusculas. Operacoes retornam
    novas instancias (imutabilidade) e exigem que as duas parcelas usem a mesma moeda.
    """

    valor: Decimal
    moeda: str = "BRL"

    def __post_init__(self) -> None:
        if not isinstance(self.valor, Decimal):
            object.__setattr__(self, "valor", Decimal(str(self.valor)))

        if not self.valor.is_finite():
            msg = "Valor monetario deve ser finito"
            raise ValueError(msg)

        quantizado = self.valor.quantize(_DUAS_CASAS, rounding=ROUND_HALF_UP)
        object.__setattr__(self, "valor", quantizado)

        if self.valor < 0:
            msg = f"Valor nao pode ser negativo: {self.valor}"
            raise ValueError(msg)

        moeda_valida = (
            len(self.moeda) == _TAMANHO_CODIGO_MOEDA
            and self.moeda.isalpha()
            and self.moeda.isupper()
        )
        if not moeda_valida:
            msg = f"Moeda deve ter 3 letras maiusculas: {self.moeda}"
            raise ValueError(msg)

    def __add__(self, outro: Dinheiro) -> Dinheiro:
        self._validar_mesma_moeda(outro)
        return Dinheiro(valor=self.valor + outro.valor, moeda=self.moeda)

    # codeql[py/unexpected-raise-in-special-method] -- invariante: nao fica negativo
    def __sub__(self, outro: Dinheiro) -> Dinheiro:
        self._validar_mesma_moeda(outro)
        resultado = self.valor - outro.valor
        if resultado < 0:
            msg = f"Subtracao resultaria em valor negativo: {resultado}"
            raise ValueError(msg)
        return Dinheiro(valor=resultado, moeda=self.moeda)

    def __mul__(self, fator: int) -> Dinheiro:
        if not isinstance(fator, int):
            return NotImplemented
        return Dinheiro(valor=self.valor * fator, moeda=self.moeda)

    def __rmul__(self, fator: int) -> Dinheiro:
        return self.__mul__(fator)

    def _validar_mesma_moeda(self, outro: Dinheiro) -> None:
        if self.moeda != outro.moeda:
            msg = f"Moedas diferentes: {self.moeda} e {outro.moeda}"
            raise ValueError(msg)
