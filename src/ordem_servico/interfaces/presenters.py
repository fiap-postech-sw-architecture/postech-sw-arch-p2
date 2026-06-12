"""Presenters do contexto Ordem de Servico (vocabulario de apresentacao).

O challenge da fase 2 exige que a consulta de status informe a situacao
da OS no vocabulario dele (RF-021). Os valores persistidos de
``StatusOrdem`` continuam snake_case (``dominio/status.py`` — nenhuma
migracao, ver gap analysis §2); este modulo concentra a traducao
status tecnico -> rotulo de apresentacao usada pelos responses HTTP.

Os rotulos carregam acentos de proposito: sao texto user-facing, nao
identificadores — a regra de acentos do ADR-009 vale para identificadores.
"""

from __future__ import annotations

from src.ordem_servico.dominio.status import StatusOrdem

# Rotulo de apresentacao por status (RF-021, grafia do challenge).
# AGUARDANDO_APROVACAO_COMPLEMENTAR compartilha o rotulo de
# AGUARDANDO_APROVACAO: mesma semantica de espera de aprovacao do cliente
# (gap §2/RN-020). CANCELADA e estado extra mantido da fase 1 (gap §2).
_SITUACAO_POR_STATUS: dict[StatusOrdem, str] = {
    StatusOrdem.RECEBIDA: "Recebida",
    StatusOrdem.EM_DIAGNOSTICO: "Em diagnóstico",
    StatusOrdem.AGUARDANDO_APROVACAO: "Aguardando aprovação",
    StatusOrdem.EM_EXECUCAO: "Em execução",
    StatusOrdem.FINALIZADA: "Finalizada",
    StatusOrdem.ENTREGUE: "Entregue",
    StatusOrdem.CANCELADA: "Cancelada",
    StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: "Aguardando aprovação",
}


def situacao_de(status: StatusOrdem) -> str:
    """Traduz o status tecnico para a situacao do vocabulario do challenge.

    Funcao total sobre ``StatusOrdem``: todo membro tem rotulo (garantido
    pelo guard em ``tests/unitarios/ordem_servico/test_presenters.py``).
    """
    return _SITUACAO_POR_STATUS[status]
