"""Pagina de listagem e gestao de clientes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from nicegui import context, ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import ApiError, ValidacaoError
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.dialogo_confirmacao import confirmar

if TYPE_CHECKING:
    from collections.abc import Callable


@ui.page("/clientes")
@exige_autenticacao
def pagina_clientes() -> None:
    CabecalhoApp()
    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Clientes").classes("text-2xl font-bold")

        tabela_container = ui.column().classes("w-full")

        # `refresh` fica no escopo de `pagina_clientes` (executada por sessao
        # NiceGUI), entao cada client/aba tem o seu — sem global compartilhado
        # entre conexoes.
        def refresh() -> None:
            tabela_container.clear()
            with tabela_container:
                _renderizar_tabela(refresh)

        with ui.row().classes("gap-2"):
            ui.button(
                "Novo cliente",
                icon="add",
                on_click=lambda: _dialog_criar(refresh),
            ).classes("bg-blue-600 text-white")

        refresh()


def _renderizar_tabela(on_refresh: Callable[[], None]) -> None:
    from ui.app import obter_api

    api = obter_api()
    try:
        dados = api.listar_clientes()
    except ApiError as exc:
        ui.label(f"Erro ao listar: {exc}").classes("text-red-600")
        return

    for cliente in dados.get("items", []):
        with ui.expansion(cliente["nome"], icon="person").classes("w-full"):
            with ui.row().classes("gap-4 items-start"):
                with ui.column().classes("gap-1"):
                    # Backend retorna `documento_mascarado` por LGPD. O documento
                    # integral fica disponivel apenas via "Exportar dados pessoais".
                    documento = cliente.get(
                        "documento_mascarado",
                        cliente.get("documento", "-"),
                    )
                    ui.label(f"Documento: {documento}")
                    ui.label(f"Tipo: {cliente.get('tipo_documento', '-')}")
                    ui.label(f"Contato: {cliente.get('contato', '-')}")
                ui.space()
                ui.button(
                    icon="edit",
                    on_click=lambda c=cliente: _dialog_editar(c, on_refresh),
                ).props("flat dense")
                ui.button(
                    icon="delete",
                    on_click=lambda c=cliente: _confirmar_desativar(c, on_refresh),
                ).props("flat dense")
                with (
                    ui.button(icon="more_vert").props("flat dense"),
                    ui.menu(),
                ):
                    ui.menu_item(
                        "Registrar consentimento",
                        on_click=lambda c=cliente: _dialog_consentimento(
                            c, registrar=True
                        ),
                    )
                    ui.menu_item(
                        "Revogar consentimento",
                        on_click=lambda c=cliente: _dialog_consentimento(
                            c, registrar=False
                        ),
                    )
                    ui.menu_item(
                        "Exportar dados pessoais",
                        on_click=lambda c=cliente: _exportar_dados(c),
                    )
                    ui.menu_item(
                        "Excluir dados pessoais",
                        on_click=lambda c=cliente: _confirmar_excluir_dados(
                            c, on_refresh
                        ),
                    )
            _renderizar_veiculos(cliente["id"], on_refresh)


def _dialog_editar(cliente: dict[str, Any], on_sucesso: Callable[[], None]) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(f"Editar {cliente['nome']}").classes("text-lg font-bold")
        nome = ui.input("Nome", value=cliente.get("nome", "")).classes("w-full")
        contato = ui.input("Contato", value=cliente.get("contato", "")).classes(
            "w-full"
        )

        def salvar() -> None:
            from ui.app import obter_api

            try:
                obter_api().atualizar_cliente(
                    cliente["id"], {"nome": nome.value, "contato": contato.value}
                )
                dialog.close()
                ui.notify("Cliente atualizado", type="positive")
                on_sucesso()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


def _confirmar_desativar(
    cliente: dict[str, Any], on_sucesso: Callable[[], None]
) -> None:
    cliente_id = str(cliente["id"])
    confirmar(
        titulo="Desativar cliente",
        mensagem=f"Desativar {cliente['nome']}?",
        perigoso=True,
        on_confirmar=lambda: _desativar(cliente_id, on_sucesso),
    )


def _desativar(cliente_id: str, on_sucesso: Callable[[], None]) -> None:
    from ui.app import obter_api

    try:
        obter_api().desativar_cliente(cliente_id)
        ui.notify("Cliente desativado", type="positive")
        on_sucesso()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")


def _renderizar_veiculos(cliente_id: str, on_refresh: Callable[[], None]) -> None:
    from ui.app import obter_api

    api = obter_api()
    try:
        veiculos = api.listar_veiculos(cliente_id)
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600 text-sm")
        return
    ui.label("Veiculos").classes("font-bold mt-2")
    for v in veiculos:
        with ui.row().classes("gap-2 items-center"):
            ui.label(f"{v['marca']} {v['modelo']} {v['ano']} — {v['placa']}")
            ui.button(
                icon="delete",
                on_click=lambda cid=cliente_id, vid=v["id"]: _remover_veiculo(
                    cid, vid, on_refresh
                ),
            ).props("flat dense")
    ui.button(
        "Adicionar veiculo",
        icon="add",
        on_click=lambda cid=cliente_id: _dialog_adicionar_veiculo(cid, on_refresh),
    ).props("flat dense")


def _remover_veiculo(
    cliente_id: str, veiculo_id: str, on_sucesso: Callable[[], None]
) -> None:
    from ui.app import obter_api

    try:
        obter_api().remover_veiculo(cliente_id, veiculo_id)
        ui.notify("Veiculo removido", type="positive")
        on_sucesso()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")


def _dialog_adicionar_veiculo(cliente_id: str, on_sucesso: Callable[[], None]) -> None:
    from datetime import UTC, datetime

    # Backend permite ate proximo ano-modelo; alinhar o input pra evitar
    # submissoes que serao rejeitadas com 422 por `_ano_maximo_permitido()`.
    ano_maximo = datetime.now(UTC).year + 1
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Novo veiculo").classes("text-lg font-bold")
        placa = ui.input("Placa").classes("w-full")
        marca = ui.input("Marca").classes("w-full")
        modelo = ui.input("Modelo").classes("w-full")
        ano = ui.number("Ano", value=ano_maximo - 5, min=1950, max=ano_maximo).classes(
            "w-full"
        )

        def salvar() -> None:
            from ui.app import obter_api

            try:
                obter_api().adicionar_veiculo(
                    cliente_id,
                    {
                        "placa": placa.value,
                        "marca": marca.value,
                        "modelo": modelo.value,
                        "ano": int(ano.value),
                    },
                )
                dialog.close()
                ui.notify("Veiculo adicionado", type="positive")
                on_sucesso()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


def _dialog_criar(on_sucesso: Callable[[], None]) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Novo cliente").classes("text-lg font-bold")
        nome = ui.input("Nome").classes("w-full")
        documento = ui.input("Documento (CPF/CNPJ)").classes("w-full")
        tipo = ui.select(["cpf", "cnpj"], label="Tipo", value="cpf").classes("w-full")
        contato = ui.input("Contato").classes("w-full")

        erros = ui.column().classes("text-red-600 text-sm")

        def salvar() -> None:
            from ui.app import obter_api

            erros.clear()
            try:
                obter_api().criar_cliente(
                    {
                        "nome": nome.value,
                        "documento": documento.value,
                        "tipo_documento": tipo.value,
                        "contato": contato.value,
                    }
                )
                dialog.close()
                ui.notify("Cliente criado", type="positive")
                on_sucesso()
            except ValidacaoError as exc:
                with erros:
                    for d in exc.detalhes:
                        ui.label(f"- {d.get('loc', [])}: {d.get('msg', '')}")
            except ApiError as exc:
                with erros:
                    ui.label(f"Erro: {exc}")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")

    dialog.open()


def _dialog_consentimento(cliente: dict[str, Any], *, registrar: bool) -> None:
    from ui.app import obter_api

    acao = "Registrar" if registrar else "Revogar"
    # Disparado de ui.menu_item: o slot ativo no handler e o do q-menu, e o
    # auto_close fecha o menu no mesmo evento — sem escapar pro layout o dialog
    # vira filho do menu e desmonta junto, so aparecendo na proxima abertura.
    with context.client.layout:
        with ui.dialog() as dialog, ui.card().classes("w-80"):
            ui.label(f"{acao} consentimento").classes("text-lg font-bold")
            tipo = ui.select(
                ["marketing", "comunicacao", "compartilhamento"],
                label="Tipo",
                value="marketing",
            ).classes("w-full")

            def salvar() -> None:
                try:
                    if registrar:
                        obter_api().registrar_consentimento(cliente["id"], tipo.value)
                    else:
                        obter_api().revogar_consentimento(cliente["id"], tipo.value)
                    dialog.close()
                    ui.notify(f"{acao} com sucesso", type="positive")
                except ApiError as exc:
                    ui.notify(f"Erro: {exc}", type="negative")

            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button("Cancelar", on_click=dialog.close).props("flat")
                ui.button("Confirmar", on_click=salvar).classes(
                    "bg-blue-600 text-white"
                )
        # Sem delete o dialog fica acumulando no layout a cada nova abertura.
        dialog.on("hide", dialog.delete)
        dialog.open()


def _exportar_dados(cliente: dict[str, Any]) -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().exportar_dados_cliente(cliente["id"])
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")
        return

    # Ver nota em _dialog_consentimento: precisa escapar do slot do q-menu.
    with context.client.layout:
        with ui.dialog() as dialog, ui.card().classes("w-[36rem]"):
            ui.label(f"Dados pessoais de {cliente['nome']}").classes(
                "text-lg font-bold"
            )
            ui.code(
                json.dumps(dados, indent=2, ensure_ascii=False), language="json"
            ).classes("text-xs")
            ui.button("Fechar", on_click=dialog.close)
        # Sem delete o dialog fica acumulando no layout a cada nova abertura.
        dialog.on("hide", dialog.delete)
        dialog.open()


def _confirmar_excluir_dados(
    cliente: dict[str, Any], on_sucesso: Callable[[], None]
) -> None:
    cliente_id = str(cliente["id"])
    confirmar(
        titulo="Excluir dados pessoais",
        mensagem=f"ATENCAO: remove dados de {cliente['nome']} (LGPD).",
        perigoso=True,
        on_confirmar=lambda: _excluir_dados(cliente_id, on_sucesso),
    )


def _excluir_dados(cliente_id: str, on_sucesso: Callable[[], None]) -> None:
    from ui.app import obter_api

    try:
        obter_api().excluir_dados_cliente(cliente_id)
        ui.notify("Dados excluidos", type="positive")
        on_sucesso()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")
