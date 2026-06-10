from __future__ import annotations

import pytest

from src.ordem_servico.dominio.status import StatusOrdem
from ui.componentes.maquina_estados import (
    TRANSICOES_POR_STATUS,
    obter_transicoes_validas,
)


def test_estado_recebida_admin_ve_diagnostico_e_cancelar() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.RECEBIDA, "admin")
    acoes = {b.acao for b in botoes}
    assert acoes == {"diagnostico", "cancelar"}
    for b in botoes:
        assert b.habilitado is True


def test_estado_recebida_mecanico_nao_pode_cancelar() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.RECEBIDA, "mecanico")
    por_acao = {b.acao: b for b in botoes}
    assert por_acao["diagnostico"].habilitado is True
    assert por_acao["cancelar"].habilitado is False


def test_estado_recebida_atendente_so_ve_tudo_desabilitado() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.RECEBIDA, "atendente")
    assert all(b.habilitado is False for b in botoes)


def test_estado_entregue_nao_tem_transicoes() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.ENTREGUE, "admin")
    assert botoes == []


def test_estado_cancelada_nao_tem_transicoes() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.CANCELADA, "admin")
    assert botoes == []


def test_todos_os_estados_do_status_ordem_estao_mapeados() -> None:
    assert set(TRANSICOES_POR_STATUS.keys()) == set(StatusOrdem)


@pytest.mark.parametrize("papel", ["admin", "atendente", "mecanico"])
@pytest.mark.parametrize("status", list(StatusOrdem))
def test_matriz_completa_nao_lanca_excecao(status: StatusOrdem, papel: str) -> None:
    obter_transicoes_validas(status, papel)
