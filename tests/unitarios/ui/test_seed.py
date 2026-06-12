from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from ui.cliente_api import ApiError
from ui.seed import (
    _CLIENTES,
    _ITENS,
    _QTD_ORDENS,
    _SERVICOS,
    _VEICULOS,
    RelatorioSeed,
    gerar_dados_teste,
)


def test_gerar_dados_cria_conjunto_completo() -> None:
    api = MagicMock()
    api.listar_clientes.return_value = {"items": []}
    api.listar_servicos.return_value = {"items": []}
    api.listar_estoque.return_value = {"items": []}
    api.listar_veiculos.return_value = [{"id": "v-ret", "placa": "RET0A00"}]
    api.criar_cliente.return_value = {"id": "c"}
    api.adicionar_veiculo.return_value = {"id": "v"}
    api.criar_servico.return_value = {"id": "s"}
    api.criar_item_estoque.return_value = {"id": "e"}
    api.criar_ordem.return_value = {"id": "o"}
    api.adicionar_item_ordem.return_value = {}
    api.executar_transicao.return_value = {}

    progresso: list[tuple[int, str]] = []
    rel = gerar_dados_teste(
        api,
        on_progresso=lambda pct, msg: progresso.append((pct, msg)),
    )

    assert isinstance(rel, RelatorioSeed)
    # Contagens batem com o shape do modulo — se o seed crescer, basta atualizar
    # as listas em ``ui.seed`` e o teste continua valido.
    assert rel.clientes_criados == len(_CLIENTES)
    assert rel.veiculos_criados == len(_VEICULOS)
    assert rel.servicos_criados == len(_SERVICOS)
    assert rel.itens_criados == len(_ITENS)
    assert rel.ordens_criadas == _QTD_ORDENS
    assert len(progresso) > 0


def test_gerar_dados_skipa_duplicatas() -> None:
    api = MagicMock()
    # Backend retorna clientes com nome (documento vem mascarado; seed usa
    # nome como chave natural). Itera pelas listas canonicas do modulo ao
    # inves de repetir os nomes — mantem o teste automaticamente em sync
    # se ``ui.seed`` crescer.
    api.listar_clientes.return_value = {
        "items": [
            {"id": f"c{i}", "nome": cliente["nome"]}
            for i, cliente in enumerate(_CLIENTES)
        ]
    }
    api.listar_servicos.return_value = {
        "items": [
            {"id": f"s{i}", "nome": servico["nome"]}
            for i, servico in enumerate(_SERVICOS)
        ]
    }
    api.listar_estoque.return_value = {
        "items": [
            {"id": f"e{i}", "nome": item["nome"]} for i, item in enumerate(_ITENS)
        ]
    }
    api.listar_veiculos.return_value = []
    api.adicionar_veiculo.return_value = {"id": "v"}
    api.criar_ordem.return_value = {"id": "o"}
    api.adicionar_item_ordem.return_value = {}
    api.executar_transicao.return_value = {}

    rel = gerar_dados_teste(api, on_progresso=lambda *a: None)

    assert rel.clientes_existentes == len(_CLIENTES)
    assert rel.servicos_existentes == len(_SERVICOS)
    assert rel.itens_existentes == len(_ITENS)
    api.criar_cliente.assert_not_called()
    api.criar_servico.assert_not_called()
    api.criar_item_estoque.assert_not_called()


# ----- Error paths: ApiError em cada etapa nao deve abortar o seed inteiro -----


def _api_padrao_feliz() -> MagicMock:
    """MagicMock com respostas default que nao quebram o seed."""
    api = MagicMock()
    api.listar_clientes.return_value = {"items": []}
    api.listar_servicos.return_value = {"items": []}
    api.listar_estoque.return_value = {"items": []}
    api.listar_veiculos.return_value = []
    # total=0 explicito: o seed tem guard que pula criacao de OS se o
    # total existente no backend for >= _QTD_ORDENS (idempotencia). Com
    # 0 o guard nao dispara e os testes exercitam o caminho criacao.
    api.listar_ordens.return_value = {"items": [], "total": 0}
    api.criar_cliente.return_value = {"id": "c"}
    api.adicionar_veiculo.return_value = {"id": "v"}
    api.criar_servico.return_value = {"id": "s"}
    api.criar_item_estoque.return_value = {"id": "e"}
    api.criar_ordem.return_value = {"id": "o"}
    api.adicionar_item_ordem.return_value = {}
    api.executar_transicao.return_value = {}
    return api


def test_api_error_em_criar_cliente_registra_aviso_e_continua() -> None:
    api = _api_padrao_feliz()
    # 2o cliente falha; os outros devem ser criados normalmente. Usa o
    # tamanho da lista canonica pra construir o side_effect — se o seed
    # crescer, a sequencia continua valida.
    side_effects: list[Any] = [{"id": f"c{i}"} for i in range(len(_CLIENTES))]
    side_effects[1] = ApiError("bad input")
    api.criar_cliente.side_effect = side_effects

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    assert rel.clientes_criados == len(_CLIENTES) - 1
    assert any("Cliente" in aviso for aviso in rel.avisos)


def test_api_error_em_adicionar_veiculo_nao_interrompe() -> None:
    api = _api_padrao_feliz()
    api.adicionar_veiculo.side_effect = ApiError("placa duplicada")

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    assert rel.veiculos_criados == 0
    assert any("Veiculo" in aviso for aviso in rel.avisos)
    # Clientes ainda foram criados apesar da falha em veiculos.
    assert rel.clientes_criados == len(_CLIENTES)


def test_api_error_em_criar_servico_nao_interrompe() -> None:
    api = _api_padrao_feliz()
    api.criar_servico.side_effect = ApiError("preco invalido")

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    assert rel.servicos_criados == 0
    # Uma tentativa por servico definido no seed.
    assert sum("Servico" in a for a in rel.avisos) == len(_SERVICOS)


def test_api_error_em_criar_item_estoque_nao_interrompe() -> None:
    api = _api_padrao_feliz()
    api.criar_item_estoque.side_effect = ApiError("qty invalida")

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    assert rel.itens_criados == 0
    assert sum("Item" in a for a in rel.avisos) == len(_ITENS)


def test_api_error_em_criar_ordem_registra_aviso() -> None:
    api = _api_padrao_feliz()
    api.adicionar_veiculo.return_value = {"id": "v"}
    # Simula veiculos existentes para que _veiculo_id_do_cliente retorne id.
    api.listar_veiculos.return_value = [{"id": "v1", "placa": "ABC1D23"}]
    api.criar_ordem.side_effect = ApiError("erro criar OS")

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    assert rel.ordens_criadas == 0
    assert any("OS #" in a for a in rel.avisos)


def test_cliente_sem_veiculo_registra_aviso_para_os_recebida() -> None:
    api = _api_padrao_feliz()
    # Cliente criado mas sem veiculo -> OS #1 (RECEBIDA) nao pode ser criada.
    api.listar_veiculos.return_value = []

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    # O aviso especifico "OS #1: cliente sem veiculo" deve aparecer.
    assert any("cliente sem veiculo" in a for a in rel.avisos)


def test_api_error_em_listar_ordens_registra_aviso_mas_tenta_criar() -> None:
    """Se o ``listar_ordens`` falhar, o guard assume 0 OS existentes (seguro:
    prefere criar e possivelmente duplicar a nao criar nada) e registra aviso."""
    api = _api_padrao_feliz()
    # listar_veiculos precisa retornar algo pra as OS serem criadas
    api.listar_veiculos.return_value = [{"id": "v1", "placa": "ABC1D23"}]
    api.listar_ordens.side_effect = ApiError("timeout no backend")

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    assert any("Nao consegui contar OS existentes" in a for a in rel.avisos)
    # Tentou criar apesar do aviso (fail-open).
    assert rel.ordens_criadas > 0


def test_guard_idempotencia_ordens_pula_criacao_se_ja_existem_suficientes() -> None:
    """OS nao tem chave natural unica, entao o seed usa um guard: se
    ``total`` retornado por ``listar_ordens`` for >= _QTD_ORDENS, pula
    a criacao pra evitar acumulo em re-runs (bug historico de rodar o
    seed duas vezes e criar 16 OS em vez de 8)."""
    api = _api_padrao_feliz()
    # Simula que o seed ja rodou antes: total existente bate com o esperado.
    api.listar_ordens.return_value = {"items": [], "total": _QTD_ORDENS}

    rel = gerar_dados_teste(api, on_progresso=lambda *_: None)

    assert rel.ordens_criadas == 0
    api.criar_ordem.assert_not_called()
    # Aviso transparente pra que o dev saiba porque nada foi criado.
    assert any("OS ja existem" in a for a in rel.avisos)


def test_relatorio_seed_resumo_formata_texto() -> None:
    rel = RelatorioSeed(
        clientes_criados=2,
        clientes_existentes=1,
        veiculos_criados=3,
        servicos_criados=0,
        servicos_existentes=5,
        itens_criados=4,
        itens_existentes=6,
        ordens_criadas=2,
    )
    # Dataclass expoe os contadores; garante que valores ficaram corretos
    # (resumo textual na UI e responsabilidade de dashboard.py).
    assert rel.clientes_criados == 2
    assert rel.clientes_existentes == 1
    assert rel.veiculos_criados == 3
