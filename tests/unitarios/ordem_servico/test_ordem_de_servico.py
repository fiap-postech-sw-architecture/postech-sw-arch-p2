from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import (
    TransicaoStatusInvalidaException,
    ViolacaoRegraDeNegocioException,
)
from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    EntregaRegistradaEvent,
    OrcamentoAprovadoEvent,
    OrcamentoComplementarAprovadoEvent,
    OrcamentoComplementarGeradoEvent,
    OrcamentoComplementarRejeitadoEvent,
    OrcamentoGeradoEvent,
    OrdemCanceladaEvent,
    OrdemCriadaEvent,
    ServicoFinalizadoEvent,
)
from src.ordem_servico.dominio.exceptions import (
    ItemDaOrdemNaoEncontradoException,
    OrdemNaoEncontradaException,
)
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem


def _criar_item() -> ItemDaOrdem:
    return ItemDaOrdem(
        _servico_catalogo_id=uuid4(),
        _descricao="Troca de oleo",
        _quantidade=1,
        _preco_unitario=Dinheiro(valor=Decimal("100.00")),
    )


def _criar_os_com_item() -> OrdemDeServico:
    os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
    os.adicionar_item(_criar_item())
    os.limpar_eventos()
    return os


class TestOrdemDeServicoCriar:
    def test_criar_status_recebida(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        assert os.status == StatusOrdem.RECEBIDA

    def test_criar_registra_evento(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        eventos = os.coletar_eventos()
        assert len(eventos) == 1
        assert isinstance(eventos[0], OrdemCriadaEvent)

    def test_criar_expoe_propriedades(self) -> None:
        cliente_id = uuid4()
        veiculo_id = uuid4()
        os = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
        assert os.cliente_id == cliente_id
        assert os.veiculo_id == veiculo_id
        assert os.criado_em is not None
        assert os.atualizado_em is not None

    def test_construcao_direta_rejeita_cliente_id_none(self) -> None:
        with pytest.raises(ValueError, match="cliente_id e obrigatorio"):
            OrdemDeServico(
                _cliente_id=None,  # type: ignore[arg-type]
                _veiculo_id=uuid4(),
            )

    def test_construcao_direta_rejeita_veiculo_id_none(self) -> None:
        with pytest.raises(ValueError, match="veiculo_id e obrigatorio"):
            OrdemDeServico(
                _cliente_id=uuid4(),
                _veiculo_id=None,  # type: ignore[arg-type]
            )


class TestExceptions:
    def test_ordem_nao_encontrada_default(self) -> None:
        exc = OrdemNaoEncontradaException()
        assert "Ordem de servico nao encontrada" in str(exc)

    def test_ordem_nao_encontrada_com_id(self) -> None:
        ordem_id = uuid4()
        exc = OrdemNaoEncontradaException(ordem_id=ordem_id)
        assert str(ordem_id) in str(exc)

    def test_ordem_nao_encontrada_custom(self) -> None:
        exc = OrdemNaoEncontradaException(mensagem="Ordem 123 nao existe")
        assert "Ordem 123 nao existe" in str(exc)

    def test_item_da_ordem_nao_encontrado_default(self) -> None:
        exc = ItemDaOrdemNaoEncontradoException()
        assert "Item da ordem nao encontrado" in str(exc)

    def test_item_da_ordem_nao_encontrado_com_ids(self) -> None:
        ordem_id = uuid4()
        item_id = uuid4()
        exc = ItemDaOrdemNaoEncontradoException(ordem_id=ordem_id, item_id=item_id)
        assert str(item_id) in str(exc)
        assert str(ordem_id) in str(exc)

    def test_item_da_ordem_nao_encontrado_custom(self) -> None:
        exc = ItemDaOrdemNaoEncontradoException(mensagem="Item abc nao existe")
        assert "Item abc nao existe" in str(exc)


class TestCicloCompleto:
    def test_lifecycle_completo(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        assert os.status == StatusOrdem.EM_DIAGNOSTICO
        os.gerar_orcamento()
        assert os.status == StatusOrdem.AGUARDANDO_APROVACAO
        assert os.orcamento is not None
        os.aprovar_orcamento()
        assert os.status == StatusOrdem.EM_EXECUCAO
        os.finalizar_servico()
        assert os.status == StatusOrdem.FINALIZADA
        os.registrar_entrega()
        assert os.status == StatusOrdem.ENTREGUE


class TestCancelamento:
    @pytest.mark.parametrize(
        "preparar",
        [
            "recebida",
            "em_diagnostico",
            "aguardando_aprovacao",
            "em_execucao",
        ],
    )
    def test_cancelar_de_estados_validos(self, preparar: str) -> None:
        os = _criar_os_com_item()
        if preparar in {
            "em_diagnostico",
            "aguardando_aprovacao",
            "em_execucao",
        }:
            os.iniciar_diagnostico()
        if preparar in {"aguardando_aprovacao", "em_execucao"}:
            os.gerar_orcamento()
        if preparar == "em_execucao":
            os.aprovar_orcamento()
        os.limpar_eventos()
        os.cancelar(motivo="Teste")
        assert os.status == StatusOrdem.CANCELADA
        eventos = os.coletar_eventos()
        assert isinstance(eventos[0], OrdemCanceladaEvent)

    def test_cancelar_de_finalizada_invalido(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.finalizar_servico()
        with pytest.raises(TransicaoStatusInvalidaException):
            os.cancelar(motivo="Tarde demais")

    def test_cancelar_motivo_vazio_invalido(self) -> None:
        os = _criar_os_com_item()
        with pytest.raises(
            ViolacaoRegraDeNegocioException,
            match="motivo de cancelamento e obrigatorio",
        ):
            os.cancelar(motivo="")

    def test_cancelar_motivo_whitespace_invalido(self) -> None:
        os = _criar_os_com_item()
        with pytest.raises(
            ViolacaoRegraDeNegocioException,
            match="motivo de cancelamento e obrigatorio",
        ):
            os.cancelar(motivo="   ")


class TestItens:
    def test_adicionar_item_recebida(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        os.adicionar_item(_criar_item())
        assert len(os.itens) == 1

    def test_adicionar_item_em_diagnostico(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.adicionar_item(_criar_item())
        assert len(os.itens) == 2

    def test_adicionar_item_em_execucao_permitido(self) -> None:
        """#80: trabalho extra na execucao -> adicionar item em EM_EXECUCAO."""
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        assert os.status == StatusOrdem.EM_EXECUCAO
        os.adicionar_item(_criar_item())
        assert len(os.itens) == 2

    def test_orcamento_complementar_reflete_item_novo(self) -> None:
        """#80: o complementar cobra o item extra (total > original, nao identico)."""
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        total_original = os.orcamento.total.valor  # type: ignore[union-attr]
        os.aprovar_orcamento()
        os.adicionar_item(_criar_item())
        os.gerar_orcamento_complementar()
        assert os.status == StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR
        assert os.orcamento.total.valor > total_original  # type: ignore[union-attr]

    def test_remover_item(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        item = _criar_item()
        os.adicionar_item(item)
        os.remover_item(item.id)
        assert len(os.itens) == 0

    def test_remover_item_nao_encontrado(self) -> None:
        os = _criar_os_com_item()
        with pytest.raises(ViolacaoRegraDeNegocioException):
            os.remover_item(uuid4())

    def test_adicionar_item_none_invalido(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        with pytest.raises(ValueError, match="item e obrigatorio"):
            os.adicionar_item(None)  # type: ignore[arg-type]

    def test_remover_item_none_invalido(self) -> None:
        os = _criar_os_com_item()
        with pytest.raises(ValueError, match="item_id e obrigatorio"):
            os.remover_item(None)  # type: ignore[arg-type]

    def test_remover_item_em_execucao_bloqueado(self) -> None:
        os = _criar_os_com_item()
        item_id = os.itens[0].id
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        with pytest.raises(ViolacaoRegraDeNegocioException):
            os.remover_item(item_id)


class TestGerarOrcamento:
    def test_sem_itens_invalido(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        os.iniciar_diagnostico()
        with pytest.raises(ViolacaoRegraDeNegocioException):
            os.gerar_orcamento()

    def test_gera_orcamento_corretamente(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        assert os.orcamento is not None
        assert os.orcamento.total == Dinheiro(valor=Decimal("100.00"))


class TestComplementar:
    def test_fluxo_aprovar(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.gerar_orcamento_complementar()
        assert os.status == StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR
        os.aprovar_orcamento_complementar()
        assert os.status == StatusOrdem.EM_EXECUCAO

    def test_fluxo_rejeitar(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.gerar_orcamento_complementar()
        os.rejeitar_orcamento_complementar()
        assert os.status == StatusOrdem.EM_EXECUCAO

    def test_gerar_complementar_sem_itens_invalido(self) -> None:
        """Defesa: aggregate construido diretamente sem itens em EM_EXECUCAO
        nao deve permitir gerar orcamento complementar."""
        os = OrdemDeServico(
            _cliente_id=uuid4(),
            _veiculo_id=uuid4(),
            _status=StatusOrdem.EM_EXECUCAO,
        )
        with pytest.raises(
            ViolacaoRegraDeNegocioException,
            match="pelo menos um item para gerar orcamento complementar",
        ):
            os.gerar_orcamento_complementar()


class TestEventos:
    def test_diagnostico_evento(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        eventos = os.coletar_eventos()
        assert any(isinstance(e, DiagnosticoIniciadoEvent) for e in eventos)

    def test_orcamento_gerado_evento(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        eventos = os.coletar_eventos()
        assert any(isinstance(e, OrcamentoGeradoEvent) for e in eventos)

    def test_orcamento_aprovado_evento(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        eventos = os.coletar_eventos()
        assert any(isinstance(e, OrcamentoAprovadoEvent) for e in eventos)

    def test_servico_finalizado_evento(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.finalizar_servico()
        eventos = os.coletar_eventos()
        assert any(isinstance(e, ServicoFinalizadoEvent) for e in eventos)

    def test_entrega_registrada_evento(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.finalizar_servico()
        os.registrar_entrega()
        eventos = os.coletar_eventos()
        assert any(isinstance(e, EntregaRegistradaEvent) for e in eventos)

    def test_complementar_eventos(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.gerar_orcamento_complementar()
        os.aprovar_orcamento_complementar()
        eventos = os.coletar_eventos()
        tipos = [type(e) for e in eventos]
        assert OrcamentoComplementarGeradoEvent in tipos
        assert OrcamentoComplementarAprovadoEvent in tipos

    def test_rejeitar_complementar_evento(self) -> None:
        os = _criar_os_com_item()
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.gerar_orcamento_complementar()
        os.rejeitar_orcamento_complementar()
        eventos = os.coletar_eventos()
        tipos = [type(e) for e in eventos]
        assert OrcamentoComplementarRejeitadoEvent in tipos

    def test_lifecycle_event_sequence(self) -> None:
        """A sequencia de eventos do ciclo completo deve ser deterministica."""
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        os.adicionar_item(_criar_item())
        os.iniciar_diagnostico()
        os.gerar_orcamento()
        os.aprovar_orcamento()
        os.finalizar_servico()
        os.registrar_entrega()
        eventos = os.coletar_eventos()
        tipos_emitidos = [type(e) for e in eventos]
        assert tipos_emitidos == [
            OrdemCriadaEvent,
            DiagnosticoIniciadoEvent,
            OrcamentoGeradoEvent,
            OrcamentoAprovadoEvent,
            ServicoFinalizadoEvent,
            EntregaRegistradaEvent,
        ]


class TestAtualizadoEm:
    def test_bump_em_iniciar_diagnostico(self) -> None:
        os = _criar_os_com_item()
        antes = os.atualizado_em
        os.iniciar_diagnostico()
        assert os.atualizado_em >= antes
        assert os.atualizado_em != antes or os.status == StatusOrdem.EM_DIAGNOSTICO

    def test_bump_em_adicionar_item(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        antes = os.atualizado_em
        os.adicionar_item(_criar_item())
        assert os.atualizado_em >= antes

    def test_bump_em_remover_item(self) -> None:
        os = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        item = _criar_item()
        os.adicionar_item(item)
        antes = os.atualizado_em
        os.remover_item(item.id)
        assert os.atualizado_em >= antes


def _avancar_para(os: OrdemDeServico, status_alvo: StatusOrdem) -> None:
    passos = {
        StatusOrdem.RECEBIDA: [],
        StatusOrdem.EM_DIAGNOSTICO: ["iniciar_diagnostico"],
        StatusOrdem.AGUARDANDO_APROVACAO: ["iniciar_diagnostico", "gerar_orcamento"],
        StatusOrdem.EM_EXECUCAO: [
            "iniciar_diagnostico",
            "gerar_orcamento",
            "aprovar_orcamento",
        ],
        StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: [
            "iniciar_diagnostico",
            "gerar_orcamento",
            "aprovar_orcamento",
            "gerar_orcamento_complementar",
        ],
        StatusOrdem.FINALIZADA: [
            "iniciar_diagnostico",
            "gerar_orcamento",
            "aprovar_orcamento",
            "finalizar_servico",
        ],
        StatusOrdem.ENTREGUE: [
            "iniciar_diagnostico",
            "gerar_orcamento",
            "aprovar_orcamento",
            "finalizar_servico",
            "registrar_entrega",
        ],
        StatusOrdem.CANCELADA: ["cancelar"],
    }
    for metodo in passos[status_alvo]:
        if metodo == "cancelar":
            os.cancelar(motivo="Teste")
        else:
            getattr(os, metodo)()
    os.limpar_eventos()


_TRANSICOES_INVALIDAS = [
    (StatusOrdem.RECEBIDA, "gerar_orcamento"),
    (StatusOrdem.RECEBIDA, "aprovar_orcamento"),
    (StatusOrdem.RECEBIDA, "finalizar_servico"),
    (StatusOrdem.RECEBIDA, "registrar_entrega"),
    (StatusOrdem.RECEBIDA, "gerar_orcamento_complementar"),
    (StatusOrdem.EM_DIAGNOSTICO, "aprovar_orcamento"),
    (StatusOrdem.EM_DIAGNOSTICO, "finalizar_servico"),
    (StatusOrdem.EM_DIAGNOSTICO, "registrar_entrega"),
    (StatusOrdem.AGUARDANDO_APROVACAO, "iniciar_diagnostico"),
    (StatusOrdem.AGUARDANDO_APROVACAO, "gerar_orcamento"),
    (StatusOrdem.AGUARDANDO_APROVACAO, "finalizar_servico"),
    (StatusOrdem.AGUARDANDO_APROVACAO, "registrar_entrega"),
    (StatusOrdem.EM_EXECUCAO, "iniciar_diagnostico"),
    (StatusOrdem.EM_EXECUCAO, "gerar_orcamento"),
    (StatusOrdem.EM_EXECUCAO, "aprovar_orcamento"),
    (StatusOrdem.EM_EXECUCAO, "registrar_entrega"),
    (StatusOrdem.FINALIZADA, "iniciar_diagnostico"),
    (StatusOrdem.FINALIZADA, "aprovar_orcamento"),
    (StatusOrdem.FINALIZADA, "finalizar_servico"),
    (StatusOrdem.FINALIZADA, "cancelar"),
    (StatusOrdem.ENTREGUE, "iniciar_diagnostico"),
    (StatusOrdem.ENTREGUE, "finalizar_servico"),
    (StatusOrdem.ENTREGUE, "cancelar"),
    (StatusOrdem.CANCELADA, "iniciar_diagnostico"),
    (StatusOrdem.CANCELADA, "aprovar_orcamento"),
    (StatusOrdem.CANCELADA, "cancelar"),
    (StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR, "iniciar_diagnostico"),
    (StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR, "gerar_orcamento"),
    (StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR, "finalizar_servico"),
    (StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR, "registrar_entrega"),
]


class TestTransicoesInvalidas:
    @pytest.mark.parametrize(
        ("status_origem", "metodo"),
        _TRANSICOES_INVALIDAS,
        ids=[f"{s.value}->{m}" for s, m in _TRANSICOES_INVALIDAS],
    )
    def test_transicao_invalida_levanta_excecao(
        self, status_origem: StatusOrdem, metodo: str
    ) -> None:
        os = _criar_os_com_item()
        _avancar_para(os, status_origem)
        with pytest.raises(TransicaoStatusInvalidaException):
            if metodo == "cancelar":
                os.cancelar(motivo="Teste")
            elif metodo == "gerar_orcamento" and not os.itens:
                os.adicionar_item(_criar_item())
                getattr(os, metodo)()
            else:
                getattr(os, metodo)()

    def test_cancelar_de_aguardando_complementar_valido(self) -> None:
        os = _criar_os_com_item()
        _avancar_para(os, StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR)
        os.cancelar(motivo="Teste")
        assert os.status == StatusOrdem.CANCELADA
