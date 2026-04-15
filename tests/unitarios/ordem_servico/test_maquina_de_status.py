from __future__ import annotations

import pytest

from src.compartilhado.dominio.exceptions import (
    TransicaoStatusInvalidaException,
)
from src.ordem_servico.dominio.maquina_de_status import MaquinaDeStatus
from src.ordem_servico.dominio.status import StatusOrdem

S = StatusOrdem

_TRANSICOES_VALIDAS = [
    (S.RECEBIDA, S.EM_DIAGNOSTICO),
    (S.RECEBIDA, S.CANCELADA),
    (S.EM_DIAGNOSTICO, S.AGUARDANDO_APROVACAO),
    (S.EM_DIAGNOSTICO, S.CANCELADA),
    (S.AGUARDANDO_APROVACAO, S.EM_EXECUCAO),
    (S.AGUARDANDO_APROVACAO, S.CANCELADA),
    (S.EM_EXECUCAO, S.FINALIZADA),
    (S.EM_EXECUCAO, S.CANCELADA),
    (S.EM_EXECUCAO, S.AGUARDANDO_APROVACAO_COMPLEMENTAR),
    (S.AGUARDANDO_APROVACAO_COMPLEMENTAR, S.EM_EXECUCAO),
    (S.AGUARDANDO_APROVACAO_COMPLEMENTAR, S.CANCELADA),
    (S.FINALIZADA, S.ENTREGUE),
]

_VALIDAS_SET = set(_TRANSICOES_VALIDAS)


class TestMaquinaDeStatus:
    def test_total_transicoes_validas(self) -> None:
        assert len(_TRANSICOES_VALIDAS) == 12

    @pytest.mark.parametrize(("de", "para"), _TRANSICOES_VALIDAS)
    def test_transicao_valida(self, de: StatusOrdem, para: StatusOrdem) -> None:
        maquina = MaquinaDeStatus()
        maquina.validar_transicao(de, para)

    @pytest.mark.parametrize(
        ("de", "para"),
        [
            (de, para)
            for de in StatusOrdem
            for para in StatusOrdem
            if (de, para) not in _VALIDAS_SET
        ],
    )
    def test_transicao_invalida(self, de: StatusOrdem, para: StatusOrdem) -> None:
        maquina = MaquinaDeStatus()
        with pytest.raises(TransicaoStatusInvalidaException):
            maquina.validar_transicao(de, para)

    def test_estados_terminais_sem_transicoes(self) -> None:
        maquina = MaquinaDeStatus()
        assert maquina.transicoes_validas(S.ENTREGUE) == set()
        assert maquina.transicoes_validas(S.CANCELADA) == set()

    def test_transicoes_validas_recebida(self) -> None:
        maquina = MaquinaDeStatus()
        assert maquina.transicoes_validas(S.RECEBIDA) == {
            S.EM_DIAGNOSTICO,
            S.CANCELADA,
        }

    def test_transicoes_validas_em_execucao(self) -> None:
        maquina = MaquinaDeStatus()
        assert maquina.transicoes_validas(S.EM_EXECUCAO) == {
            S.FINALIZADA,
            S.CANCELADA,
            S.AGUARDANDO_APROVACAO_COMPLEMENTAR,
        }

    @pytest.mark.parametrize("status", list(StatusOrdem))
    def test_auto_transicao_invalida(self, status: StatusOrdem) -> None:
        maquina = MaquinaDeStatus()
        with pytest.raises(TransicaoStatusInvalidaException):
            maquina.validar_transicao(status, status)
