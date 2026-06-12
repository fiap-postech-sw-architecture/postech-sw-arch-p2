from __future__ import annotations

from unittest.mock import MagicMock

from src.ordem_servico.aplicacao.queries import EnriquecerOrdemDeServico
from src.ordem_servico.aplicacao.use_cases import (
    AdicionarItem,
    AprovarOrcamento,
    AprovarOrcamentoComplementar,
    CancelarOrdem,
    ConsultarAcompanhamento,
    CriarOrdem,
    DecidirOrcamento,
    FinalizarServico,
    GerarOrcamento,
    GerarOrcamentoComplementar,
    IniciarDiagnostico,
    ListarOrdens,
    ObterMetricas,
    ObterOrdem,
    RegistrarEntrega,
    RejeitarOrcamentoComplementar,
    RemoverItem,
)
from src.ordem_servico.interfaces.dependencies import (
    obter_adicionar_item,
    obter_aprovar_complementar,
    obter_aprovar_orcamento,
    obter_cancelar_ordem,
    obter_consultar_acompanhamento,
    obter_criar_ordem,
    obter_decidir_orcamento,
    obter_enriquecer_ordem,
    obter_finalizar_servico,
    obter_gerar_complementar,
    obter_gerar_orcamento,
    obter_iniciar_diagnostico,
    obter_listar_ordens,
    obter_metricas,
    obter_obter_ordem,
    obter_registrar_entrega,
    obter_rejeitar_complementar,
    obter_remover_item,
)


class TestDependenciesOS:
    """Verifica que cada factory retorna uma instancia da use case correta.

    Assertivas usam ``isinstance`` (nao ``is not None``) para detectar
    regressao se alguma factory passar a devolver o tipo errado (e.g.,
    copiar-colar entre helpers).
    """

    def test_obter_criar_ordem(self) -> None:
        uc = obter_criar_ordem(MagicMock())
        assert isinstance(uc, CriarOrdem)

    def test_obter_adicionar_item(self) -> None:
        uc = obter_adicionar_item(MagicMock())
        assert isinstance(uc, AdicionarItem)

    def test_obter_remover_item(self) -> None:
        uc = obter_remover_item(MagicMock())
        assert isinstance(uc, RemoverItem)

    def test_obter_iniciar_diagnostico(self) -> None:
        uc = obter_iniciar_diagnostico(MagicMock())
        assert isinstance(uc, IniciarDiagnostico)

    def test_obter_gerar_orcamento(self) -> None:
        uc = obter_gerar_orcamento(MagicMock())
        assert isinstance(uc, GerarOrcamento)

    def test_obter_aprovar_orcamento(self) -> None:
        uc = obter_aprovar_orcamento(MagicMock())
        assert isinstance(uc, AprovarOrcamento)

    def test_obter_finalizar_servico(self) -> None:
        uc = obter_finalizar_servico(MagicMock())
        assert isinstance(uc, FinalizarServico)

    def test_obter_registrar_entrega(self) -> None:
        uc = obter_registrar_entrega(MagicMock())
        assert isinstance(uc, RegistrarEntrega)

    def test_obter_cancelar_ordem(self) -> None:
        uc = obter_cancelar_ordem(MagicMock())
        assert isinstance(uc, CancelarOrdem)

    def test_obter_gerar_complementar(self) -> None:
        uc = obter_gerar_complementar(MagicMock())
        assert isinstance(uc, GerarOrcamentoComplementar)

    def test_obter_aprovar_complementar(self) -> None:
        uc = obter_aprovar_complementar(MagicMock())
        assert isinstance(uc, AprovarOrcamentoComplementar)

    def test_obter_rejeitar_complementar(self) -> None:
        uc = obter_rejeitar_complementar(MagicMock())
        assert isinstance(uc, RejeitarOrcamentoComplementar)

    def test_obter_listar_ordens(self) -> None:
        uc = obter_listar_ordens(MagicMock())
        assert isinstance(uc, ListarOrdens)

    def test_obter_obter_ordem(self) -> None:
        uc = obter_obter_ordem(MagicMock())
        assert isinstance(uc, ObterOrdem)

    def test_obter_metricas(self) -> None:
        uc = obter_metricas(MagicMock())
        assert isinstance(uc, ObterMetricas)

    def test_obter_consultar_acompanhamento(self) -> None:
        uc = obter_consultar_acompanhamento(MagicMock())
        assert isinstance(uc, ConsultarAcompanhamento)

    def test_obter_enriquecer_ordem(self) -> None:
        query = obter_enriquecer_ordem(MagicMock())
        assert isinstance(query, EnriquecerOrdemDeServico)

    def test_obter_decidir_orcamento(self) -> None:
        uc = obter_decidir_orcamento(MagicMock())
        assert isinstance(uc, DecidirOrcamento)
        # Composicao correta: os tres caminhos delegados (RF-022).
        assert isinstance(uc._aprovar_orcamento, AprovarOrcamento)
        assert isinstance(uc._aprovar_complementar, AprovarOrcamentoComplementar)
        assert isinstance(uc._cancelar_ordem, CancelarOrdem)
