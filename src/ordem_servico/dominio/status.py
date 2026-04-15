"""Enumeracao ``StatusOrdem``: estados do ciclo de vida da OrdemDeServico."""

from __future__ import annotations

from enum import StrEnum


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
