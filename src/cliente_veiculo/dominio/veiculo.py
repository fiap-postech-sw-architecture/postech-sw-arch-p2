from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.compartilhado.dominio.entity import Entity

if TYPE_CHECKING:
    from src.cliente_veiculo.dominio.placa import Placa
    from src.cliente_veiculo.dominio.placa_anonimizada import PlacaAnonimizada

ANO_PRIMEIRO_CARRO = 1886
_ANOS_FUTURO_PERMITIDO = 1  # veiculo pode ser de ate o proximo ano-modelo


def ano_maximo_permitido() -> int:
    """Indirecao para permitir que testes congelem a data sem patchar `datetime`."""
    return datetime.now(UTC).year + _ANOS_FUTURO_PERMITIDO


@dataclass(eq=False)
class Veiculo(Entity):
    """Entidade Veiculo. Faz parte do agregado Cliente.

    Invariantes: `placa` obrigatoria; `marca` e `modelo` nao vazios (valores
    sao aparados com `strip()` antes de validar/persistir); `ano` entre 1887 e
    o proximo ano-modelo. Validacoes sao aplicadas em `__post_init__`.
    Identidade via UUID herdado de `Entity` (igualdade por id, nao por valor).
    """

    # Defaults sentinels: None/0 ficam nos campos apenas para permitir que o
    # dataclass aceite kwargs opcionais; `__post_init__` rejeita esses valores.
    _placa: Placa | PlacaAnonimizada | None = None  # validated in __post_init__
    _marca: str = ""
    _modelo: str = ""
    _ano: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self._placa is None:
            msg = "Placa do veiculo e obrigatoria"
            raise ValueError(msg)
        self._marca = self._marca.strip()
        if not self._marca:
            msg = "Marca do veiculo nao pode ser vazia"
            raise ValueError(msg)
        self._modelo = self._modelo.strip()
        if not self._modelo:
            msg = "Modelo do veiculo nao pode ser vazio"
            raise ValueError(msg)
        ano_maximo = ano_maximo_permitido()
        if self._ano <= ANO_PRIMEIRO_CARRO or self._ano > ano_maximo:
            msg = (
                f"Ano deve ser entre {ANO_PRIMEIRO_CARRO + 1} e {ano_maximo}: "
                f"{self._ano}"
            )
            raise ValueError(msg)

    @property
    def placa(self) -> Placa | PlacaAnonimizada:
        if self._placa is None:
            msg = "Placa do veiculo nao pode ser nula"
            raise ValueError(msg)
        return self._placa

    @property
    def marca(self) -> str:
        return self._marca

    @property
    def modelo(self) -> str:
        return self._modelo

    @property
    def ano(self) -> int:
        return self._ano
