from __future__ import annotations

from dataclasses import dataclass

from src.compartilhado.dominio.value_object import ValueObject

_TAMANHO_MAXIMO = 255


@dataclass(frozen=True, slots=True)
class Contato(ValueObject):
    """Value Object de contato do cliente (texto livre).

    O contato e deliberadamente livre: pode ser e-mail, telefone ou uma
    combinacao de nome + e-mail + telefone ("Maria - maria@x.com / (11) 9...").
    Por isso o VO faz apenas validacao leve — nao-vazio e ate 255 caracteres
    (o tamanho da coluna ``contato``) — sem impor formato de e-mail/telefone.

    Imutavel. Como o valor e PII, o ``__repr__`` nao vaza o conteudo (mesma
    politica do ``__repr__`` mascarado do ``CPF``).
    """

    valor: str

    def __post_init__(self) -> None:
        valor = self.valor.strip()
        if not valor:
            msg = "contato nao pode ser vazio"
            raise ValueError(msg)
        if len(valor) > _TAMANHO_MAXIMO:
            msg = f"contato nao pode exceder {_TAMANHO_MAXIMO} caracteres"
            raise ValueError(msg)
        object.__setattr__(self, "valor", valor)

    def __repr__(self) -> str:
        # PII-safe: nao expoe o conteudo (e-mail/telefone/nome). Apenas o
        # tamanho, suficiente para debugar sem vazar dado pessoal em logs.
        return f"Contato(len={len(self.valor)})"
