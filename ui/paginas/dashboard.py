"""Dashboard — pagina root apos login."""

from __future__ import annotations

from nicegui import ui

from src.ordem_servico.dominio.status import StatusOrdem
from ui.auth_guard import exige_autenticacao
from ui.cliente_api import AcessoNegadoError, ApiError, NaoAutenticadoError
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.stepper_os import _ROTULOS
from ui.estado import obter_store


@ui.page("/")
@exige_autenticacao
def pagina_dashboard() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Dashboard").classes("text-2xl font-bold")

        _renderizar_metricas()

        with ui.row().classes("gap-4"):
            papel = obter_store().papel_atual()
            botao_seed = ui.button(
                "🎲 Gerar dados de teste",
                on_click=_dialog_seed,
            ).classes("bg-purple-600 text-white")
            if papel != "admin":
                botao_seed.props("disable")
                botao_seed.tooltip("Seed requer papel admin")
            ui.button(
                "Nova OS",
                icon="add",
                on_click=lambda: ui.navigate.to("/ordens-servico"),
            ).classes("bg-blue-600 text-white")


def _renderizar_metricas() -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().metricas_ordens()
    except AcessoNegadoError:
        ui.label("Metricas disponiveis apenas para admin.").classes("text-gray-500")
        return
    except NaoAutenticadoError:
        ui.navigate.to("/login")
        return
    except ApiError as exc:
        ui.label(f"Erro ao carregar metricas: {exc}").classes("text-red-600")
        return

    with ui.row().classes("gap-4 w-full flex-wrap"):
        _card_metrica("Total de OS", str(dados.get("total", 0)), "bg-blue-500")
        _card_metrica(
            "Tempo medio (min)",
            str(dados.get("tempo_medio_execucao_minutos", 0)),
            "bg-green-500",
        )
        por_status = dados.get("por_status", {})
        for status, qtd in por_status.items():
            _card_metrica(_rotulo_status(str(status)), str(qtd), "bg-gray-500")


def _rotulo_status(status: str) -> str:
    """Rotulo amigavel do status (mesmo vocabulario do stepper da OS).

    Cai no snake_case cru se o backend emitir um status desconhecido.
    """
    try:
        return _ROTULOS.get(StatusOrdem(status), status)
    except ValueError:
        return status


def _card_metrica(titulo: str, valor: str, cor: str) -> None:
    with ui.card().classes(f"{cor} text-white min-w-40"):
        ui.label(titulo).classes("text-sm")
        ui.label(valor).classes("text-3xl font-bold")


async def _dialog_seed() -> None:
    """Roda o seed com o dialog de progresso JA aberto.

    Handler async + ``run.io_bound`` (issue #169, fix parcial restrito ao
    seed): a versao sincrona so abria o dialog DEPOIS do seed inteiro rodar
    no event loop — a UI congelava por varios segundos sem nenhum progresso
    visivel. O callback de progresso apenas muta elementos existentes
    (thread-safe no NiceGUI); a conversao async das demais paginas fica na
    issue #169.
    """
    from nicegui import run

    from ui.app import obter_api
    from ui.seed import gerar_dados_teste

    with ui.dialog() as dialog, ui.card().classes("w-[36rem]"):
        ui.label("Gerando dados de teste").classes("text-lg font-bold")
        progress = ui.linear_progress(value=0).classes("w-full")
        status_label = ui.label("Iniciando...").classes("text-sm")
        relatorio_container = ui.column().classes("w-full")
        fechar_btn = ui.button("Fechar", on_click=dialog.close).props("flat")
        fechar_btn.set_visibility(False)

    def atualizar_progresso(pct: int, msg: str) -> None:
        progress.value = pct / 100
        status_label.set_text(msg)

    dialog.open()
    try:
        rel = await run.io_bound(
            gerar_dados_teste, obter_api(), on_progresso=atualizar_progresso
        )
        if rel is None:
            # run.io_bound devolve None quando o app entra em shutdown no
            # meio da tarefa — nao ha relatorio pra mostrar.
            return
        with relatorio_container:
            ui.label(
                f"✓ {rel.clientes_criados} clientes criados "
                f"({rel.clientes_existentes} existiam)"
            )
            ui.label(f"✓ {rel.veiculos_criados} veiculos adicionados")
            ui.label(
                f"✓ {rel.servicos_criados} servicos criados "
                f"({rel.servicos_existentes} existiam)"
            )
            ui.label(
                f"✓ {rel.itens_criados} itens de estoque criados "
                f"({rel.itens_existentes} existiam)"
            )
            ui.label(f"✓ {rel.ordens_criadas} OS criadas")
            for aviso in rel.avisos:
                ui.label(f"⚠ {aviso}").classes("text-orange-600")
    except NaoAutenticadoError:
        ui.navigate.to("/login")
        return
    except ApiError as exc:
        with relatorio_container:
            ui.label(f"Erro fatal: {exc}").classes("text-red-600")
    fechar_btn.set_visibility(True)
