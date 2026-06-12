from __future__ import annotations

import pytest

from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.interfaces.presenters import situacao_de


class TestSituacaoDe:
    @pytest.mark.parametrize(
        ("status", "rotulo"),
        [
            (StatusOrdem.RECEBIDA, "Recebida"),
            (StatusOrdem.EM_DIAGNOSTICO, "Em diagnóstico"),
            (StatusOrdem.AGUARDANDO_APROVACAO, "Aguardando aprovação"),
            (StatusOrdem.EM_EXECUCAO, "Em execução"),
            (StatusOrdem.FINALIZADA, "Finalizada"),
            (StatusOrdem.ENTREGUE, "Entregue"),
            (StatusOrdem.CANCELADA, "Cancelada"),
            (StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR, "Aguardando aprovação"),
        ],
    )
    def test_rotulo_por_status(self, status: StatusOrdem, rotulo: str) -> None:
        assert situacao_de(status) == rotulo

    def test_complementar_compartilha_rotulo_da_aprovacao(self) -> None:
        # Gap §2/RN-020: a espera complementar tem a mesma semantica de
        # aguardar aprovacao do cliente — o vocabulario do challenge nao
        # distingue os dois estados.
        assert situacao_de(
            StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR
        ) == situacao_de(StatusOrdem.AGUARDANDO_APROVACAO)

    def test_situacao_cobre_todos_os_status(self) -> None:
        # Guard de drift (RF-021): um novo membro em StatusOrdem precisa
        # de rotulo de apresentacao. Sem ele, situacao_de levantaria
        # KeyError no meio da serializacao do response — este teste
        # quebra primeiro, em build time.
        from src.ordem_servico.interfaces.presenters import _SITUACAO_POR_STATUS

        assert set(_SITUACAO_POR_STATUS) == set(StatusOrdem)
