"""Helpers de formatacao compartilhados pelas paginas da UI."""

from __future__ import annotations

from typing import Any


def formatar_dinheiro_br(
    valor: Any,  # noqa: ANN401  # JSON do backend (float/int/str-Decimal/None)
    prefixo: str = "R$ ",
) -> str:
    """Formata valor em reais no padrao brasileiro: ``R$ 1.234,56``.

    Unifica a formatacao de dinheiro que estava triplicada (estoque, catalogo
    e ordens), cada copia com um bug latente de ``float(None)``. Aceita:
    - ``float``/``int`` (payloads comuns);
    - ``str`` (backend serializa ``Decimal`` como string JSON, ex. ``"280.00"``);
    - ``None``/``""`` (chave presente com valor nulo) — vira zero.

    String nao numerica propaga ``ValueError``: lixo do backend deve estourar
    pra ser investigado, nao ser adivinhado.
    """
    numero = float(valor or 0)
    # f-string produz "1,234.56"; troca em 3 passos pra nao colidir separadores.
    texto = f"{numero:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{prefixo}{texto}"
