"""Presenters do contexto Ordem de Servico (vocabulario de apresentacao).

A fonte unica do rotulo de situacao (RF-021) mudou para
``src/ordem_servico/aplicacao/situacoes.py`` quando a notificacao por
e-mail (RF-024) passou a consumir o mesmo vocabulario — ``aplicacao``
nao pode importar ``interfaces`` (contrato de camadas, ADR-015). Este
modulo reexporta para preservar os imports existentes de
``interfaces/schemas.py`` e dos testes; o sentido interfaces ->
aplicacao e permitido pelo contrato.
"""

from __future__ import annotations

from src.ordem_servico.aplicacao.situacoes import (
    _SITUACAO_POR_STATUS as _SITUACAO_POR_STATUS,
)
from src.ordem_servico.aplicacao.situacoes import (
    situacao_de as situacao_de,
)
