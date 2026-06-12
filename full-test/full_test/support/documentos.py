"""Geradores de CPF e placa sinteticos. Uso: apenas em testes.

CPF: algoritmo oficial dos digitos verificadores (modulo 11) — o API usa
``brutils`` para validar, entao entregar um CPF com digito correto e
obrigatorio. Placa: padrao antigo ``AAA0000`` (7 chars sem hifen), aceito
pelo ``Placa`` VO tanto quanto Mercosul ``AAA0A00``.

Ambos os geradores aceitam um ``random.Random`` proprio da journey para
reproducibilidade — quando o ``FULL_TEST_SEED`` e fixo, o dataset gerado
e deterministico entre runs.
"""

from __future__ import annotations

import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random
    from collections.abc import Iterable


def gerar_cpf(rng: random.Random) -> str:
    """Gera um CPF valido (11 digitos, sem mascara).

    Algoritmo oficial: os dois digitos verificadores sao calculados via
    modulo 11 sobre os 9 primeiros digitos aleatorios. A string retornada
    nao tem pontuacao — o API aceita esse formato (o VO ``CPF`` normaliza
    removendo caracteres nao-numericos antes de validar).
    """
    base = [rng.randint(0, 9) for _ in range(9)]
    d1 = _digito_cpf(base, pesos=range(10, 1, -1))
    d2 = _digito_cpf([*base, d1], pesos=range(11, 1, -1))
    return "".join(str(x) for x in [*base, d1, d2])


def _digito_cpf(digitos: list[int], pesos: Iterable[int]) -> int:
    soma = sum(d * p for d, p in zip(digitos, pesos, strict=True))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def gerar_placa(rng: random.Random) -> str:
    """Gera uma placa no padrao antigo ``AAA0000`` (7 chars, sem hifen).

    O VO ``Placa`` normaliza maiusculas e remove hifen, entao o formato
    compactado funciona em ambos os padroes aceitos pelo dominio.
    """
    letras = "".join(rng.choices(string.ascii_uppercase, k=3))
    numeros = "".join(rng.choices(string.digits, k=4))
    return f"{letras}{numeros}"
