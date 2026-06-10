"""Maquina de transicoes do ``StatusOrdem`` para a Ordem de Servico."""

from __future__ import annotations

from typing import ClassVar

from src.compartilhado.dominio.exceptions import TransicaoStatusInvalidaException
from src.ordem_servico.dominio.status import StatusOrdem


class MaquinaDeStatus:
    """Define e valida o conjunto de transicoes legais do ``StatusOrdem``.

    A tabela ``_TRANSICOES`` e uma allow-list (whitelist) por estado de
    origem com valores ``frozenset``, garantindo imutabilidade da
    configuracao. Estados terminais (``ENTREGUE``, ``CANCELADA``) mapeiam
    para ``frozenset()`` vazio.
    """

    _TRANSICOES: ClassVar[dict[StatusOrdem, frozenset[StatusOrdem]]] = {
        StatusOrdem.RECEBIDA: frozenset(
            {
                StatusOrdem.EM_DIAGNOSTICO,
                StatusOrdem.CANCELADA,
            }
        ),
        StatusOrdem.EM_DIAGNOSTICO: frozenset(
            {
                StatusOrdem.AGUARDANDO_APROVACAO,
                StatusOrdem.CANCELADA,
            }
        ),
        StatusOrdem.AGUARDANDO_APROVACAO: frozenset(
            {
                StatusOrdem.EM_EXECUCAO,
                StatusOrdem.CANCELADA,
            }
        ),
        StatusOrdem.EM_EXECUCAO: frozenset(
            {
                StatusOrdem.FINALIZADA,
                StatusOrdem.CANCELADA,
                StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR,
            }
        ),
        StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: frozenset(
            {
                StatusOrdem.EM_EXECUCAO,
                StatusOrdem.CANCELADA,
            }
        ),
        StatusOrdem.FINALIZADA: frozenset(
            {
                StatusOrdem.ENTREGUE,
            }
        ),
        StatusOrdem.ENTREGUE: frozenset(),
        StatusOrdem.CANCELADA: frozenset(),
    }

    def transicoes_validas(self, status: StatusOrdem) -> frozenset[StatusOrdem]:
        """Retorna as transicoes legais a partir do estado informado.

        O retorno e ``frozenset`` para que callers nao consigam mutar
        acidentalmente a tabela global de transicoes.
        """
        return self._TRANSICOES.get(status, frozenset())

    def validar_transicao(self, de: StatusOrdem, para: StatusOrdem) -> None:
        """Levanta ``TransicaoStatusInvalidaException`` se a transicao nao for legal.

        A mensagem inclui as transicoes validas a partir de ``de`` para
        que o caller saiba quais alternativas existem.
        """
        if para not in self.transicoes_validas(de):
            validas = sorted(s.value for s in self.transicoes_validas(de))
            raise TransicaoStatusInvalidaException(
                mensagem=(
                    f"Transicao invalida de {de.value} para {para.value}; "
                    f"transicoes validas a partir de {de.value}: {validas}"
                )
            )
