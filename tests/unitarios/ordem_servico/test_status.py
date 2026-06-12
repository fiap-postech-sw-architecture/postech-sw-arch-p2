from __future__ import annotations

from src.ordem_servico.dominio.status import StatusOrdem


class TestStatusOrdem:
    def test_possui_8_membros(self) -> None:
        assert len(StatusOrdem) == 8

    def test_valores_string(self) -> None:
        assert StatusOrdem.RECEBIDA == "recebida"
        assert StatusOrdem.EM_DIAGNOSTICO == "em_diagnostico"
        assert StatusOrdem.AGUARDANDO_APROVACAO == "aguardando_aprovacao"
        assert StatusOrdem.EM_EXECUCAO == "em_execucao"
        assert StatusOrdem.FINALIZADA == "finalizada"
        assert StatusOrdem.ENTREGUE == "entregue"
        assert StatusOrdem.CANCELADA == "cancelada"
        assert (
            StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR
            == "aguardando_aprovacao_complementar"
        )

    def test_iteravel(self) -> None:
        membros = list(StatusOrdem)
        assert len(membros) == 8

    def test_comparavel_com_string(self) -> None:
        assert StatusOrdem.RECEBIDA == "recebida"
        assert StatusOrdem("recebida") is StatusOrdem.RECEBIDA
