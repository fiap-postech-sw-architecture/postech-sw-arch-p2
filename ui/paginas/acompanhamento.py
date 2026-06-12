"""Pagina publica de acompanhamento de OS (simula visao do cliente final)."""

from __future__ import annotations

from nicegui import ui

from ui.cliente_api import (
    ApiError,
    BackendInacessivelError,
    RateLimitExcedidoError,
    ValidacaoError,
)


@ui.page("/acompanhamento")
def pagina_acompanhamento() -> None:
    """Pagina sem auth (simula endpoint publico do backend)."""
    with ui.column().classes("absolute-center items-center gap-4 w-[32rem]"):
        ui.label("Acompanhamento de OS").classes("text-3xl font-bold")
        ui.label("Consulte o andamento do seu servico").classes("text-gray-500")

        placa = ui.input("Placa", placeholder="ABC1D23").classes("w-full")
        documento = ui.input("CPF ou CNPJ", placeholder="apenas numeros").classes(
            "w-full"
        )

        resultado = ui.column().classes("w-full")

        def consultar() -> None:
            from ui.app import obter_api

            resultado.clear()
            try:
                dados = obter_api().acompanhamento_publico(
                    placa=placa.value, documento=documento.value
                )
            except ValidacaoError:
                with resultado:
                    ui.label("Placa ou documento em formato invalido.").classes(
                        "text-red-600"
                    )
                return
            except RateLimitExcedidoError as exc:
                with resultado:
                    ui.label(f"Muitas consultas. Aguarde {exc.retry_after}s.").classes(
                        "text-orange-600"
                    )
                return
            except BackendInacessivelError as exc:
                with resultado:
                    ui.label(f"Backend inacessivel: {exc}").classes("text-red-600")
                return
            except ApiError as exc:
                with resultado:
                    ui.label(f"Nenhuma OS encontrada ({exc}).").classes("text-gray-600")
                return

            # AcompanhamentoResponse do backend expoe apenas status + timestamps
            # por privacidade (LGPD); nao existe `id` no payload publico.
            with resultado, ui.card().classes("w-full bg-green-50"):
                ui.label(f"Status: {dados.get('status', '?')}").classes(
                    "text-lg font-bold"
                )
                ui.label(f"Criada em: {dados.get('criado_em', '-')}")
                ui.label(f"Atualizado em: {dados.get('atualizado_em', '-')}")

        ui.button("Consultar", on_click=consultar).classes(
            "bg-blue-600 text-white w-full"
        )
