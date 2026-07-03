"""Testes do calculo de etapa concluida do stepper de OS (bug 7 do #170).

AGUARDANDO_APROVACAO_COMPLEMENTAR nao pertence ao happy path; antes do fix,
``list.index`` levantava ValueError e NENHUMA etapa aparecia como concluida
nesse estado. Agora o estado herda o indice de EM_EXECUCAO (de onde o desvio
parte), entao as etapas ja percorridas continuam marcadas.
"""

from __future__ import annotations

import pytest

from src.ordem_servico.dominio.status import StatusOrdem
from ui.componentes.stepper_os import _HAPPY_PATH, _eh_passado


def test_complementar_marca_etapas_anteriores_a_em_execucao_como_passadas() -> None:
    atual = StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR
    assert _eh_passado(StatusOrdem.RECEBIDA, atual) is True
    assert _eh_passado(StatusOrdem.EM_DIAGNOSTICO, atual) is True
    assert _eh_passado(StatusOrdem.AGUARDANDO_APROVACAO, atual) is True


def test_complementar_nao_marca_em_execucao_nem_etapas_futuras() -> None:
    """EM_EXECUCAO sera retomada apos a aprovacao complementar — aparece como
    pendente, nao concluida; FINALIZADA/ENTREGUE idem."""
    atual = StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR
    assert _eh_passado(StatusOrdem.EM_EXECUCAO, atual) is False
    assert _eh_passado(StatusOrdem.FINALIZADA, atual) is False
    assert _eh_passado(StatusOrdem.ENTREGUE, atual) is False


def test_happy_path_continua_com_progressao_normal() -> None:
    """Regressao: o mapeamento do complementar nao pode afetar o happy path."""
    atual = StatusOrdem.EM_EXECUCAO
    assert _eh_passado(StatusOrdem.RECEBIDA, atual) is True
    assert _eh_passado(StatusOrdem.AGUARDANDO_APROVACAO, atual) is True
    assert _eh_passado(StatusOrdem.EM_EXECUCAO, atual) is False
    assert _eh_passado(StatusOrdem.FINALIZADA, atual) is False


def test_cancelada_nao_marca_nenhuma_etapa() -> None:
    """CANCELADA segue fora do happy path: nada aparece como concluido."""
    for estado in _HAPPY_PATH:
        assert _eh_passado(estado, StatusOrdem.CANCELADA) is False


@pytest.mark.parametrize("atual", list(StatusOrdem))
def test_eh_passado_nunca_levanta_para_nenhum_status(atual: StatusOrdem) -> None:
    """Era exatamente o ValueError engolido que causava o bug — nenhum par
    (estado, atual) pode explodir."""
    for estado in StatusOrdem:
        _eh_passado(estado, atual)
