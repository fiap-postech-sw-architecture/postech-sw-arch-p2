"""Paginas de listagem e detalhe de ordens de servico."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from src.ordem_servico.dominio.status import StatusOrdem
from ui.auth_guard import exige_autenticacao
from ui.cliente_api import (
    ApiError,
    ConflitoEstadoError,
    NaoAutenticadoError,
    NaoEncontradoError,
)
from ui.componentes.botoes_transicao import BotoesTransicao
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.listagem import rodape_contagem
from ui.componentes.notificacoes import notificar_erro_api
from ui.componentes.picker_recurso import PickerRecurso
from ui.componentes.stepper_os import StepperOs
from ui.estado import obter_store
from ui.formatacao import formatar_dinheiro_br

if TYPE_CHECKING:
    from collections.abc import Callable

    from ui.componentes.maquina_estados import Transicao


def _centavos_para_reais_label(
    valor_centavos_raw: Any,  # noqa: ANN401  # JSON do backend
    prefixo: str = "R$ ",
) -> str:
    """Formata valor monetario em centavos (int) no padrao BR ``R$ 1.234,56``.

    Backend retorna valores monetarios em centavos sob chaves ``*_centavos``
    (int). Dividir por 100 produz reais. Um ``None``/``""`` vira zero.
    """
    return formatar_dinheiro_br(int(valor_centavos_raw or 0) / 100, prefixo)


def _campo_ou_placeholder(
    ordem: dict[str, Any],
    chave: str,
    placeholder: str = "",
) -> str:
    """Le ``ordem[chave]`` tratando chave ausente e ``None`` como placeholder.

    Backend retorna ``cliente_nome``/``veiculo_placa`` como ``str | None``:
    ``null`` no JSON quando o cliente/veiculo foi removido apos a OS ter
    sido criada (fallback graceful em ``EnriquecerOrdemDeServico``).
    ``dict.get(k, default)`` so usa o default quando a chave esta ausente,
    deixando ``None`` cair literal no f-string como ``"Cliente: None"`` —
    bug que a review do PR #140 pegou. Esse helper unifica os dois casos.
    """
    valor = ordem.get(chave)
    if valor is None or valor == "":
        return placeholder
    return str(valor)


def _total_orcamento_label(orcamento: dict[str, Any]) -> str:
    """Le ``total_centavos`` (chave canonica do backend) e formata em reais.

    Regressao pinada: o backend expoe APENAS ``total_centavos`` no response do
    orcamento. Se alguem trocar a chave lida para outro nome (ex.: ``total``)
    o total mostrado vai sempre para zero — foi exatamente esse o bug do PR
    original.
    """
    return _centavos_para_reais_label(
        orcamento.get("total_centavos"), prefixo="Total: R$ "
    )


_CORES_STATUS: dict[str, str] = {
    "recebida": "bg-gray-400",
    "em_diagnostico": "bg-yellow-500",
    "aguardando_aprovacao": "bg-orange-500",
    "em_execucao": "bg-blue-500",
    "aguardando_aprovacao_complementar": "bg-orange-600",
    "finalizada": "bg-green-500",
    "entregue": "bg-green-700",
    "cancelada": "bg-red-600",
}

# Espelho das regras de dominio do agregado ``OrdemDeServico`` (#80):
# - ADICAO: tambem em EM_EXECUCAO -> registra trabalho extra que vai pro
#   orcamento complementar (reaprovado pelo cliente).
# - REMOCAO: so antes do orcamento ser aprovado -> preserva o escopo aprovado.
# Em qualquer outro estado o backend retorna 409; a UI esconde cada botao
# conforme o estado. Drift-check casa estes conjuntos com os do dominio.
_ESTADOS_PERMITE_ADICAO: frozenset[str] = frozenset(
    {"recebida", "em_diagnostico", "em_execucao"}
)
_ESTADOS_PERMITE_REMOCAO: frozenset[str] = frozenset({"recebida", "em_diagnostico"})

# Espelho dos ``exigir_papel(...)`` do router do backend
# (``src/ordem_servico/interfaces/router.py``): criar OS e admin-only;
# adicionar/remover item e admin+mecanico. A UI desabilita o botao com
# tooltip (padrao BotoesTransicao) em vez de deixar o clique morrer em 403.
_PAPEIS_CRIAR_OS: frozenset[str] = frozenset({"admin"})
_PAPEIS_ALTERAR_ITENS: frozenset[str] = frozenset({"admin", "mecanico"})


def _papel_autorizado(papeis: frozenset[str]) -> bool:
    return (obter_store().papel_atual() or "") in papeis


def _bloquear_botao_por_papel(btn: ui.button, papeis: frozenset[str]) -> None:
    """Desabilita o botao com tooltip de papel (padrao BotoesTransicao)."""
    btn.props("disable")
    btn.classes("opacity-50")
    btn.tooltip(f"Exige papel: {' ou '.join(sorted(papeis))}")


def _situacao_para_exibir(ordem: dict[str, Any]) -> str:
    """Rotulo amigavel da OS para DISPLAY (RF-021).

    Le ``situacao`` (rotulo computado pelo backend: "Em diagnóstico", etc.)
    com fallback para o ``status`` snake_case cru caso o campo ainda nao venha
    no payload — a logica de transicao continua lendo ``status`` direto.
    """
    return _campo_ou_placeholder(ordem, "situacao") or str(ordem.get("status", "?"))


@ui.page("/ordens-servico")
@exige_autenticacao
def pagina_ordens() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Ordens de Servico").classes("text-2xl font-bold")

        container = ui.column().classes("w-full")

        # RF-023: toggle pra reexibir OS encerradas (FINALIZADA/ENTREGUE/
        # CANCELADA), escondidas por padrao pelo backend. Default off.
        mostrar_encerradas = ui.checkbox("Mostrar encerradas")

        def refresh() -> None:
            container.clear()
            with container:
                _renderizar_lista(incluir_encerradas=bool(mostrar_encerradas.value))

        # Re-renderiza reativamente ao alternar o checkbox.
        mostrar_encerradas.on_value_change(lambda _e: refresh())

        botao_nova_os = ui.button(
            "Nova OS",
            icon="add",
            on_click=lambda: _dialog_nova_ordem(refresh),
        ).classes("bg-blue-600 text-white")
        if not _papel_autorizado(_PAPEIS_CRIAR_OS):
            _bloquear_botao_por_papel(botao_nova_os, _PAPEIS_CRIAR_OS)
        refresh()


def _quantidade_valida(valor: Any) -> int | None:  # noqa: ANN401  # ui.number().value
    """Normaliza ``ui.number().value`` em int >= 1.

    NiceGUI deixa o input vazio (None ou "") quando o usuario apaga o campo,
    e ``int(None)`` levanta TypeError — isso quebrava o salvar() do dialog.
    Retorna ``None`` quando invalido pra caller decidir (notify + abort).
    """
    if valor is None or valor == "":
        return None
    try:
        n = int(valor)
    except TypeError, ValueError:
        return None
    if n < 1:
        return None
    return n


def _renderizar_lista(*, incluir_encerradas: bool = False) -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().listar_ordens(incluir_encerradas=incluir_encerradas)
    except NaoAutenticadoError:
        ui.navigate.to("/login")
        return
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600")
        return

    for ordem in dados.get("items", []):
        # Cor segue o status snake_case (mapa estavel); o texto do badge usa o
        # rotulo amigavel ``situacao`` (RF-021).
        status = ordem.get("status", "?")
        cor = _CORES_STATUS.get(status, "bg-gray-300")
        with (
            ui.card()
            .classes("w-full cursor-pointer")
            .on(
                "click",
                lambda o=ordem: ui.navigate.to(f"/ordens-servico/{o['id']}"),
            ),
            ui.row().classes("items-center gap-4"),
        ):
            ui.label(str(ordem["id"])[:8]).classes("font-mono text-xs")
            ui.badge(_situacao_para_exibir(ordem), color=None).classes(
                f"{cor} text-white"
            )
            ui.label(_campo_ou_placeholder(ordem, "cliente_nome")).classes("flex-1")
            ui.label(_campo_ou_placeholder(ordem, "veiculo_placa")).classes("font-mono")
    rodape_contagem(dados)


def _coletar_servicos_inline(
    linhas: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Monta a lista ``servicos`` (RF-020) das linhas dinamicas do dialog.

    Linha em branco (sem servico escolhido) e ignorada. Retorna
    ``(servicos, erro)``: ``erro`` != None aborta o salvar com a mensagem.
    Cada item segue o contrato ``{servico_catalogo_id, quantidade>0}``.
    """
    servicos: list[dict[str, Any]] = []
    for ld in linhas:
        servico_id = ld["servico_picker"].valor()
        if not servico_id:
            continue  # linha em branco, ignora
        qtd = _quantidade_valida(ld["quantidade"].value)
        if qtd is None:
            return [], "Quantidade do servico precisa ser >= 1."
        servicos.append({"servico_catalogo_id": servico_id, "quantidade": qtd})
    return servicos, None


def _coletar_pecas_inline(
    linhas: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Monta a lista ``pecas`` (RF-020) das linhas dinamicas do dialog.

    Cada peca exige servico (mao de obra que a consome) + item de estoque, por
    contrato (``{servico_catalogo_id, item_estoque_id, quantidade>0}``). Linha
    totalmente em branco e ignorada; linha parcial vira erro.
    """
    pecas: list[dict[str, Any]] = []
    for ld in linhas:
        servico_id = ld["servico_picker"].valor()
        item_id = ld["item_picker"].valor()
        if not servico_id and not item_id:
            continue  # linha em branco, ignora
        if not servico_id or not item_id:
            return [], "Cada peca precisa de servico e item de estoque."
        qtd = _quantidade_valida(ld["quantidade"].value)
        if qtd is None:
            return [], "Quantidade da peca precisa ser >= 1."
        pecas.append(
            {
                "servico_catalogo_id": servico_id,
                "item_estoque_id": item_id,
                "quantidade": qtd,
            }
        )
    return pecas, None


def _dialog_nova_ordem(on_sucesso: Callable[[], None]) -> None:  # noqa: PLR0915
    from ui.app import obter_api

    # Linhas dinamicas opcionais (RF-020): servicos (mao de obra) e pecas
    # (item de estoque consumido por um servico) ja na criacao da OS.
    linhas_servicos: list[dict[str, Any]] = []
    linhas_pecas: list[dict[str, Any]] = []

    with ui.dialog() as dialog, ui.card().classes("w-[40rem]"):
        ui.label("Nova OS").classes("text-lg font-bold")

        cliente_picker = PickerRecurso(
            rotulo="Cliente",
            fetcher=lambda: obter_api().listar_clientes(limit=100).get("items", []),
            campo_label="nome",
        )
        veiculo_picker_container = ui.column().classes("w-full")
        veiculo_picker_holder: dict[str, PickerRecurso] = {}

        def refresh_veiculos() -> None:
            veiculo_picker_container.clear()
            cid = cliente_picker.valor()
            if not cid:
                return
            with veiculo_picker_container:
                veiculo_picker_holder["v"] = PickerRecurso(
                    rotulo="Veiculo",
                    fetcher=lambda: obter_api().listar_veiculos(cid),
                    campo_label="placa",
                )

        cliente_picker.on_change(refresh_veiculos)

        ui.separator()
        ui.label("Servicos (opcional)").classes("font-medium")
        ui.label(
            "Mao de obra cobrada pelo preco do catalogo. Pode adicionar depois "
            "de criar a OS."
        ).classes("text-xs text-gray-500")
        container_servicos = ui.column().classes("gap-2 w-full")

        def adicionar_linha_servico() -> None:
            with (
                container_servicos,
                ui.row().classes("items-center gap-2 w-full") as linha,
            ):
                servico_picker = PickerRecurso(
                    rotulo="Servico",
                    fetcher=lambda: (
                        obter_api().listar_servicos(limit=100).get("items", [])
                    ),
                    campo_label="nome",
                )
                qtd = ui.number("Qtd", value=1, min=1, step=1).classes("w-24")
                linha_dict: dict[str, Any] = {
                    "row": linha,
                    "servico_picker": servico_picker,
                    "quantidade": qtd,
                }
                ui.button(
                    icon="close",
                    on_click=lambda ld=linha_dict: _remover_linha(ld, linhas_servicos),
                ).props("flat dense round")
                linhas_servicos.append(linha_dict)

        ui.button(
            "+ adicionar servico", icon="add", on_click=adicionar_linha_servico
        ).props("flat dense")

        ui.separator()
        ui.label("Pecas (opcional)").classes("font-medium")
        ui.label(
            "Item de estoque consumido por um servico (preco do estoque)."
        ).classes("text-xs text-gray-500")
        container_pecas = ui.column().classes("gap-2 w-full")

        def adicionar_linha_peca() -> None:
            with (
                container_pecas,
                ui.row().classes("items-center gap-2 w-full") as linha,
            ):
                servico_picker = PickerRecurso(
                    rotulo="Servico",
                    fetcher=lambda: (
                        obter_api().listar_servicos(limit=100).get("items", [])
                    ),
                    campo_label="nome",
                )
                item_picker = PickerRecurso(
                    rotulo="Item",
                    fetcher=lambda: (
                        obter_api().listar_estoque(limit=100).get("items", [])
                    ),
                    campo_label="nome",
                )
                qtd = ui.number("Qtd", value=1, min=1, step=1).classes("w-24")
                linha_dict = {
                    "row": linha,
                    "servico_picker": servico_picker,
                    "item_picker": item_picker,
                    "quantidade": qtd,
                }
                ui.button(
                    icon="close",
                    on_click=lambda ld=linha_dict: _remover_linha(ld, linhas_pecas),
                ).props("flat dense round")
                linhas_pecas.append(linha_dict)

        ui.button("+ adicionar peca", icon="add", on_click=adicionar_linha_peca).props(
            "flat dense"
        )

        def salvar() -> None:
            cid = cliente_picker.valor()
            vp = veiculo_picker_holder.get("v")
            vid = vp.valor() if vp else None
            if not cid or not vid:
                ui.notify("Escolha cliente e veiculo", type="warning")
                return

            servicos, erro_s = _coletar_servicos_inline(linhas_servicos)
            if erro_s:
                ui.notify(erro_s, type="warning")
                return
            pecas, erro_p = _coletar_pecas_inline(linhas_pecas)
            if erro_p:
                ui.notify(erro_p, type="warning")
                return

            # extra='forbid' no backend: so passa a lista quando ha itens —
            # criacao simples (fase 1) manda so cliente_id + veiculo_id.
            try:
                resposta = obter_api().criar_ordem(
                    cid,
                    vid,
                    servicos=servicos or None,
                    pecas=pecas or None,
                )
                dialog.close()
                ui.notify("OS criada", type="positive")
                ui.navigate.to(f"/ordens-servico/{resposta['id']}")
            except ApiError as exc:
                notificar_erro_api(exc)

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Criar", on_click=salvar).classes("bg-blue-600 text-white")
    # Sem delete o dialog acumula no layout a cada abertura.
    dialog.on("hide", dialog.delete)
    dialog.open()


@ui.page("/ordens-servico/{ordem_id}")
@exige_autenticacao
def pagina_detalhe_ordem(ordem_id: str) -> None:
    CabecalhoApp()

    container = ui.column().classes("p-8 gap-4 w-full")

    def render() -> None:
        container.clear()
        with container:
            _renderizar_detalhe(ordem_id, render)

    render()


def _renderizar_detalhe(  # noqa: C901, PLR0915  # render coeso de detalhe
    ordem_id: str,
    on_refresh: Callable[[], None],
) -> None:
    from ui.app import obter_api

    try:
        ordem = obter_api().obter_ordem(ordem_id)
    except NaoAutenticadoError:
        ui.navigate.to("/login")
        return
    except NaoEncontradoError:
        # 404: id inexistente/removido (ex.: link antigo) — mensagem amigavel
        # com caminho de volta em vez do "Status inesperado 404" generico.
        ui.label("OS nao encontrada.").classes("text-xl font-bold text-gray-700")
        ui.label("A ordem pode ter sido removida ou o link esta incorreto.").classes(
            "text-gray-500"
        )
        ui.button(
            "Voltar para a listagem",
            icon="arrow_back",
            on_click=lambda: ui.navigate.to("/ordens-servico"),
        ).props("flat")
        return
    except ApiError as exc:
        ui.label(f"Erro ao carregar OS: {exc}").classes("text-red-600")
        return

    ui.label(f"OS {ordem['id']}").classes("text-2xl font-bold font-mono")
    status_str = ordem["status"]
    try:
        status_enum = StatusOrdem(status_str)
    except ValueError:
        ui.label(f"Status invalido: {status_str}").classes("text-red-600")
        return

    # Cor + maquina de estados usam o status snake_case; o badge mostra o
    # rotulo amigavel ``situacao`` (RF-021).
    cor = _CORES_STATUS.get(status_str, "bg-gray-300")
    ui.badge(_situacao_para_exibir(ordem), color=None).classes(
        f"{cor} text-white text-lg px-3 py-1"
    )

    with ui.card().classes("w-full"):
        ui.label("Dados").classes("font-bold")
        ui.label(f"Cliente: {_campo_ou_placeholder(ordem, 'cliente_nome', '-')}")
        ui.label(f"Veiculo: {_campo_ou_placeholder(ordem, 'veiculo_placa', '-')}")
        ui.label(f"Criada em: {ordem.get('criado_em', '-')}")

    with ui.card().classes("w-full"):
        ui.label("Ciclo de vida").classes("font-bold")
        StepperOs(status_enum)

    with ui.card().classes("w-full"):
        ui.label("Acoes").classes("font-bold")

        def executar(transicao: Transicao, body: dict[str, str] | None) -> None:
            try:
                obter_api().executar_transicao(ordem_id, transicao.endpoint, body)
                ui.notify(f"Transicao {transicao.rotulo} executada", type="positive")
                on_refresh()
            except ApiError as exc:
                notificar_erro_api(exc)

        BotoesTransicao(status_enum, on_executar=executar)

    _renderizar_itens(ordem_id, ordem, status_str, on_refresh)

    orcamento = ordem.get("orcamento")
    if orcamento:
        with ui.card().classes("w-full"):
            ui.label("Orcamento").classes("font-bold")
            ui.label(_total_orcamento_label(orcamento)).classes(
                "text-lg font-bold text-green-700"
            )
            gerado = orcamento.get("gerado_em")
            if gerado:
                ui.label(f"Gerado em: {gerado}").classes("text-xs text-gray-500")
            # Itens do orcamento (preco unitario + subtotal por linha).
            if orcamento.get("itens"):
                for linha in orcamento["itens"]:
                    with ui.row().classes("items-center gap-4 w-full text-sm"):
                        ui.label(linha.get("descricao", "")).classes("flex-1")
                        ui.label(f"{linha.get('quantidade', 1)}x")
                        ui.label(
                            _centavos_para_reais_label(
                                linha.get("preco_unitario_centavos")
                            )
                        )
                        ui.label(
                            _centavos_para_reais_label(
                                linha.get("subtotal_centavos"), prefixo="= R$ "
                            )
                        ).classes("font-bold")


def _agrupar_itens_por_servico(
    itens: list[dict[str, Any]],
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """Agrupa itens da OS por ``servico_catalogo_id`` preservando ordem.

    Retorna lista de ``(servico_id, servico_nome, itens_do_grupo)``. O nome
    vem do response (``servico_nome`` resolvido pelo backend); cai pra
    ``"Servico desconhecido"`` se ausente.

    Ordem: pela primeira ocorrencia de cada servico_id na lista de input —
    espelha a ordem cronologica de adicao.
    """
    grupos: dict[str, list[dict[str, Any]]] = {}
    nomes: dict[str, str] = {}
    for item in itens:
        sid = str(item.get("servico_catalogo_id", ""))
        if not sid:
            continue
        if sid not in grupos:
            grupos[sid] = []
            nomes[sid] = item.get("servico_nome") or "Servico desconhecido"
        grupos[sid].append(item)
    return [(sid, nomes[sid], grupos[sid]) for sid in grupos]


def _subtotal_grupo_centavos(itens_grupo: list[dict[str, Any]]) -> int:
    """Soma os ``subtotal_centavos`` de um grupo de itens (mao-de-obra + itens)."""
    return sum(int(i.get("subtotal_centavos") or 0) for i in itens_grupo)


def _renderizar_itens(
    ordem_id: str,
    ordem: dict[str, Any],
    status: str,
    on_refresh: Callable[[], None],
) -> None:
    permite_adicao = status in _ESTADOS_PERMITE_ADICAO
    permite_remocao = status in _ESTADOS_PERMITE_REMOCAO
    itens_raw = ordem.get("itens", [])
    grupos = _agrupar_itens_por_servico(itens_raw)

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center w-full"):
            ui.label("Servicos").classes("font-bold flex-1")
            if permite_adicao:
                btn_add = ui.button(
                    "Adicionar servico",
                    icon="add",
                    on_click=lambda: _dialog_adicionar_servico(ordem_id, on_refresh),
                ).props("flat dense")
                if not _papel_autorizado(_PAPEIS_ALTERAR_ITENS):
                    _bloquear_botao_por_papel(btn_add, _PAPEIS_ALTERAR_ITENS)
        if status == "em_execucao":
            # Em EM_EXECUCAO adicionar item registra trabalho extra; gere o
            # orcamento complementar (transicao /orcamento-complementar) para
            # cobrar o cliente. Remocao de item ja aprovado fica travada.
            ui.label(
                "Itens adicionados aqui entram no orcamento complementar "
                "(reaprovado pelo cliente)."
            ).classes("text-xs text-gray-500 italic")
        elif not permite_adicao:
            # Estados pos-orcamento (ex.: aguardando_aprovacao): o backend bloqueia
            # mudanca de itens (409). Caminho oficial: aprovar e, em EM_EXECUCAO,
            # gerar orcamento complementar.
            ui.label(
                f"Itens travados em {status}. Para alterar, avance ate EM_EXECUCAO "
                "e gere orcamento complementar (transicao /orcamento-complementar)."
            ).classes("text-xs text-gray-500 italic")
        if not grupos:
            ui.label("Nenhum servico ainda.").classes("text-gray-500 italic")
            return
        for sid, servico_nome, itens_grupo in grupos:
            _renderizar_grupo_servico(
                ordem_id,
                sid,
                servico_nome,
                itens_grupo,
                on_refresh,
                permite_adicao=permite_adicao,
                permite_remocao=permite_remocao,
            )


def _renderizar_grupo_servico(  # noqa: PLR0913  # render coeso de grupo de OS
    ordem_id: str,
    servico_id: str,
    servico_nome: str,
    itens_grupo: list[dict[str, Any]],
    on_refresh: Callable[[], None],
    *,
    permite_adicao: bool,
    permite_remocao: bool,
) -> None:
    """Renderiza um grupo: header com nome do servico + subtotal, sublinhas
    com cada item de estoque consumido + botao opcional pra adicionar mais
    itens ao mesmo servico."""
    subtotal_grupo = _subtotal_grupo_centavos(itens_grupo)
    with ui.card().classes("w-full bg-gray-50 ml-2"):
        with ui.row().classes("items-center gap-3 w-full"):
            ui.icon("build").classes("text-blue-600")
            ui.label(servico_nome).classes("font-bold flex-1")
            ui.label(_centavos_para_reais_label(subtotal_grupo)).classes(
                "text-green-700 font-bold"
            )
            if permite_adicao:
                btn_mais = ui.button(
                    icon="add",
                    on_click=lambda sid=servico_id, snome=servico_nome: (
                        _dialog_adicionar_item_de_estoque(
                            ordem_id, sid, snome, on_refresh
                        )
                    ),
                ).props("flat dense round")
                if _papel_autorizado(_PAPEIS_ALTERAR_ITENS):
                    btn_mais.tooltip("Adicionar item ao servico")
                else:
                    _bloquear_botao_por_papel(btn_mais, _PAPEIS_ALTERAR_ITENS)
        for item in itens_grupo:
            _renderizar_linha_item(
                ordem_id, item, on_refresh, permite_remocao=permite_remocao
            )


def _renderizar_linha_item(
    ordem_id: str,
    item: dict[str, Any],
    on_refresh: Callable[[], None],
    *,
    permite_remocao: bool,
) -> None:
    """Renderiza uma linha de item dentro do grupo de servico.

    Layout: ``[icone tipo] [nome do recurso] - [descricao] [qty] [preco un]
    [= subtotal] [delete]``. ``nome do recurso`` e o servico (pra mao de
    obra) ou item de estoque (pra peca consumida). Sem nome (caso raro de
    catalogo limpo apos OS criada) cai pro placeholder.
    """
    is_peca = bool(item.get("item_estoque_id"))
    if is_peca:
        icone = "settings"
        nome_recurso = item.get("item_estoque_nome") or "Item de estoque"
    else:
        icone = "engineering"
        nome_recurso = item.get("servico_nome") or "Mao de obra"

    preco_un_centavos = int(item.get("preco_unitario_centavos") or 0)
    quantidade = item.get("quantidade", 1)

    with ui.row().classes("items-center gap-3 w-full pl-6 text-sm"):
        ui.icon(icone).classes("text-gray-500")
        ui.label(nome_recurso).classes("font-medium")
        descricao = item.get("descricao", "")
        if descricao and descricao != nome_recurso:
            ui.label(f"— {descricao}").classes("text-gray-600 flex-1")
        else:
            ui.element("div").classes("flex-1")
        ui.label(f"{quantidade}x")
        ui.label(_centavos_para_reais_label(preco_un_centavos))
        ui.label(
            _centavos_para_reais_label(item.get("subtotal_centavos"), prefixo="= R$ ")
        ).classes("font-bold")
        if permite_remocao:
            btn_del = ui.button(
                icon="delete",
                on_click=lambda i=item: _remover_item(ordem_id, i["id"], on_refresh),
            ).props("flat dense")
            if not _papel_autorizado(_PAPEIS_ALTERAR_ITENS):
                _bloquear_botao_por_papel(btn_del, _PAPEIS_ALTERAR_ITENS)


def _remover_item(ordem_id: str, item_id: str, on_refresh: Callable[[], None]) -> None:
    from ui.app import obter_api

    try:
        obter_api().remover_item_ordem(ordem_id, item_id)
        ui.notify("Item removido", type="positive")
        on_refresh()
    except ApiError as exc:
        notificar_erro_api(exc)


def _dialog_adicionar_servico(  # noqa: C901, PLR0915  # dialog multi-step coeso
    ordem_id: str,
    on_refresh: Callable[[], None],
) -> None:
    """Dialog "Adicionar servico": escolhe servico (mao-de-obra) e
    opcionalmente N itens de estoque consumidos. Salvar dispara N+1
    chamadas de backend (1 pra mao-de-obra, 1 por item) — todas com mesmo
    servico_catalogo_id pra agrupamento na exibicao.

    Cada chamada e independente: se uma falhar, as outras continuam. Mostra
    aviso por linha falha. Sem rollback (backend nao expoe endpoint atomico
    pra batch — aceitavel no contexto dev sandbox).
    """
    from ui.app import obter_api

    # Linhas dinamicas: cada uma representa um item de estoque consumido.
    # Lista de dict com pickers/inputs criados sob demanda na ui.column().
    linhas_itens: list[dict[str, Any]] = []

    with ui.dialog() as dialog, ui.card().classes("w-[40rem]"):
        ui.label("Adicionar servico").classes("text-lg font-bold")
        ui.label(
            "Servico = mao de obra (cobrada pelo preco do catalogo). "
            "Itens de estoque consumidos sao opcionais e somam ao orcamento."
        ).classes("text-sm text-gray-500")

        servico_picker = PickerRecurso(
            rotulo="Servico",
            fetcher=lambda: obter_api().listar_servicos(limit=100).get("items", []),
            campo_label="nome",
        )
        descricao_servico = ui.input(
            "Descricao da mao de obra", placeholder="ex.: Cliente relatou barulho"
        ).classes("w-full")
        quantidade_servico = ui.number(
            "Quantidade (mao de obra)", value=1, min=1, step=1
        ).classes("w-full")

        ui.separator()
        with ui.row().classes("items-center gap-3 w-full"):
            ui.label("Itens de estoque consumidos (opcional)").classes(
                "font-medium flex-1"
            )

        container_itens = ui.column().classes("gap-2 w-full")

        def adicionar_linha_item() -> None:
            with (
                container_itens,
                ui.row().classes("items-center gap-2 w-full") as linha,
            ):
                item_picker = PickerRecurso(
                    rotulo="Item",
                    fetcher=lambda: (
                        obter_api().listar_estoque(limit=100).get("items", [])
                    ),
                    campo_label="nome",
                )
                qtd_item = ui.number("Qtd", value=1, min=1, step=1).classes("w-24")
                desc_item = ui.input("Descricao do item").classes("flex-1")
                linha_dict = {
                    "row": linha,
                    "item_picker": item_picker,
                    "quantidade": qtd_item,
                    "descricao": desc_item,
                }
                ui.button(
                    icon="close",
                    on_click=lambda ld=linha_dict: _remover_linha(ld, linhas_itens),
                ).props("flat dense round")
                linhas_itens.append(linha_dict)

        ui.button("+ adicionar item", icon="add", on_click=adicionar_linha_item).props(
            "flat dense"
        )

        def salvar() -> None:  # noqa: C901, PLR0912  # cadeia de validacao
            servico_id = servico_picker.valor()
            if not servico_id:
                ui.notify("Escolha o servico.", type="warning")
                return
            descricao_servico_valor = (descricao_servico.value or "").strip()
            if not descricao_servico_valor:
                ui.notify("Descricao do servico e obrigatoria.", type="warning")
                return

            qtd_servico = _quantidade_valida(quantidade_servico.value)
            if qtd_servico is None:
                ui.notify("Quantidade do servico precisa ser >= 1.", type="warning")
                return

            # 1. Cria a linha de mao de obra (sem item_estoque_id).
            linhas_a_criar: list[dict[str, Any]] = [
                {
                    "servico_catalogo_id": servico_id,
                    "descricao": descricao_servico_valor,
                    "quantidade": qtd_servico,
                }
            ]
            # 2. Cria 1 linha por item de estoque selecionado, todas vinculadas
            #    ao mesmo servico_catalogo_id (agrupamento implicito).
            for ld in linhas_itens:
                # ``_remover_linha`` ja removeu da lista — nao precisa skip.
                item_id = ld["item_picker"].valor()
                if not item_id:
                    continue  # linha em branco, ignora
                desc_item_valor = (ld["descricao"].value or "").strip()
                if not desc_item_valor:
                    ui.notify("Cada item precisa de descricao.", type="warning")
                    return
                qtd_item = _quantidade_valida(ld["quantidade"].value)
                if qtd_item is None:
                    ui.notify(
                        f"Quantidade invalida para '{desc_item_valor}'.",
                        type="warning",
                    )
                    return
                linhas_a_criar.append(
                    {
                        "servico_catalogo_id": servico_id,
                        "item_estoque_id": item_id,
                        "descricao": desc_item_valor,
                        "quantidade": qtd_item,
                    }
                )

            api = obter_api()
            falhas: list[str] = []
            criadas = 0
            for body in linhas_a_criar:
                try:
                    api.adicionar_item_ordem(ordem_id, body)
                    criadas += 1
                except ConflitoEstadoError as exc:
                    falhas.append(f"{body['descricao']}: {exc.detail}")
                except ApiError as exc:
                    falhas.append(f"{body['descricao']}: {exc}")

            # So fecha o dialog quando tudo deu certo. Com falhas o dialog
            # fica aberto pra usuario ver as notificacoes lado-a-lado com o
            # form e re-tentar — antes ele fechava primeiro e a notify
            # aparecia "isolada" sobre a tela de OS, dando aparencia de
            # sucesso total.
            if criadas:
                ui.notify(
                    f"{criadas} linha(s) adicionada(s) ao servico.",
                    type="positive",
                )
            for falha in falhas:
                ui.notify(f"Falha: {falha}", type="warning")
            on_refresh()
            if not falhas:
                dialog.close()

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    # Sem delete o dialog acumula no layout a cada abertura.
    dialog.on("hide", dialog.delete)
    dialog.open()


def _remover_linha(linha: dict[str, Any], linhas_itens: list[dict[str, Any]]) -> None:
    """Remove a linha do container visual e da lista de pendentes.

    Estrategia: ``row.delete()`` desmonta os elementos NiceGUI in-place e o
    ``list.remove()`` garante que ``salvar()`` nao itere sobre essa entrada.
    Sem flags — quem nao esta na lista nao vira payload.
    """
    linha["row"].delete()
    if linha in linhas_itens:
        linhas_itens.remove(linha)


def _dialog_adicionar_item_de_estoque(
    ordem_id: str,
    servico_id: str,
    servico_nome: str,
    on_refresh: Callable[[], None],
) -> None:
    """Dialog menor pra adicionar UM item de estoque a um servico ja existente.

    Acionado pelo botao "+" dentro de cada grupo de servico no display. Mantem
    o servico_catalogo_id fixo (pre-selecionado), so escolhe o item, qtd e
    descricao.
    """
    from ui.app import obter_api

    with ui.dialog() as dialog, ui.card().classes("w-[32rem]"):
        ui.label(f"Adicionar item ao servico: {servico_nome}").classes(
            "text-lg font-bold"
        )
        ui.label(
            "O preco vem do estoque (preco_unitario do item) — soma ao subtotal "
            "do servico."
        ).classes("text-sm text-gray-500")

        item_picker = PickerRecurso(
            rotulo="Item de estoque",
            fetcher=lambda: obter_api().listar_estoque(limit=100).get("items", []),
            campo_label="nome",
        )
        descricao = ui.input("Descricao", placeholder="ex.: 1L oleo 5W30").classes(
            "w-full"
        )
        quantidade = ui.number("Quantidade", value=1, min=1, step=1).classes("w-full")

        def salvar() -> None:
            item_id = item_picker.valor()
            if not item_id:
                ui.notify("Escolha o item.", type="warning")
                return
            descricao_valor = (descricao.value or "").strip()
            if not descricao_valor:
                ui.notify("Descricao e obrigatoria.", type="warning")
                return
            qtd = _quantidade_valida(quantidade.value)
            if qtd is None:
                ui.notify("Quantidade precisa ser >= 1.", type="warning")
                return
            body: dict[str, Any] = {
                "servico_catalogo_id": servico_id,
                "item_estoque_id": item_id,
                "descricao": descricao_valor,
                "quantidade": qtd,
            }
            try:
                obter_api().adicionar_item_ordem(ordem_id, body)
                dialog.close()
                ui.notify("Item adicionado", type="positive")
                on_refresh()
            except ApiError as exc:
                notificar_erro_api(exc)

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    # Sem delete o dialog acumula no layout a cada abertura.
    dialog.on("hide", dialog.delete)
    dialog.open()
