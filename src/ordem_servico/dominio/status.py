"""Enumeracao ``StatusOrdem``: estados do ciclo de vida da OrdemDeServico."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class StatusOrdem(StrEnum):
    """Estados validos do ciclo de vida de uma OrdemDeServico.

    A maquina de transicoes (``MaquinaDeStatus``) define quais transicoes
    sao legais. Os valores sao snake_case para facilitar persistencia.
    """

    RECEBIDA = "recebida"
    EM_DIAGNOSTICO = "em_diagnostico"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    EM_EXECUCAO = "em_execucao"
    FINALIZADA = "finalizada"
    ENTREGUE = "entregue"
    CANCELADA = "cancelada"
    AGUARDANDO_APROVACAO_COMPLEMENTAR = "aguardando_aprovacao_complementar"


# Estados sem transicao de saida na ``MaquinaDeStatus``: uma OS neles esta
# encerrada e nao segura mais reservas de estoque nem aparece como "ativa"
# para os contextos vizinhos. Fonte unica -- os tres consumidores (o repo de
# OS e os adapters reversos de cliente_veiculo e estoque) importam daqui em
# vez de manter copias sincronizadas por comentario. Um teste em
# ``test_maquina_de_status`` valida este conjunto contra a maquina.
ESTADOS_TERMINAIS: Final[frozenset[StatusOrdem]] = frozenset(
    {StatusOrdem.ENTREGUE, StatusOrdem.CANCELADA}
)
