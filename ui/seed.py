"""Gerador de dados de demo via API do backend.

Popula um dataset realista pro dev experimentar a UI sem criar tudo na mao:
7 clientes (5 PF + 2 PJ), 10 veiculos, 8 servicos, 14 itens de estoque e 8
OS cobrindo 7 estados do ``StatusOrdem``. Idempotente por chave natural
(nome/placa); reexecutar nao duplica.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ui.cliente_api import ApiError

if TYPE_CHECKING:
    from collections.abc import Callable

    from ui.cliente_api import ClienteApi


@dataclass
class RelatorioSeed:
    clientes_criados: int = 0
    clientes_existentes: int = 0
    veiculos_criados: int = 0
    servicos_criados: int = 0
    servicos_existentes: int = 0
    itens_criados: int = 0
    itens_existentes: int = 0
    ordens_criadas: int = 0
    avisos: list[str] = field(default_factory=list)


# CPFs/CNPJs gerados deterministicamente via brutils (seed fixa); todos passam
# validacao. NAO sao documentos de pessoas reais — numeros matematicamente
# validos mas sinteticos.
_CLIENTES: list[dict[str, Any]] = [
    {
        "nome": "Joao Silva",
        "documento": "11144477735",
        "tipo_documento": "cpf",
        "contato": "joao.silva@example.com",
    },
    {
        "nome": "Maria Santos",
        "documento": "98765432100",
        "tipo_documento": "cpf",
        "contato": "maria.santos@example.com",
    },
    {
        "nome": "Carlos Mendes",
        "documento": "68657930480",
        "tipo_documento": "cpf",
        "contato": "carlos.mendes@example.com",
    },
    {
        "nome": "Ana Beatriz Oliveira",
        "documento": "11954083238",
        "tipo_documento": "cpf",
        "contato": "ana.oliveira@example.com",
    },
    {
        "nome": "Rafael Costa",
        "documento": "02685509305",
        "tipo_documento": "cpf",
        "contato": "rafael.costa@example.com",
    },
    {
        "nome": "Oficina Boa Vida LTDA",
        "documento": "11222333000181",
        "tipo_documento": "cnpj",
        "contato": "contato@boavida.com",
    },
    {
        "nome": "Transportadora Horizonte Ltda",
        "documento": "19551396000193",
        "tipo_documento": "cnpj",
        "contato": "frota@horizonte.com",
    },
]

# Placas Mercosul (formato AAA9A99) + antigas (AAA9999). Mix intencional pra
# provar que o backend aceita ambos os formatos (ver ``src/.../placa.py``).
_VEICULOS: list[tuple[int, dict[str, Any]]] = [
    (0, {"placa": "ABC1D23", "marca": "Volkswagen", "modelo": "Gol", "ano": 2015}),
    (0, {"placa": "DEF2E34", "marca": "Honda", "modelo": "Civic", "ano": 2020}),
    (1, {"placa": "GHI3F45", "marca": "Toyota", "modelo": "Corolla", "ano": 2018}),
    (2, {"placa": "JKL4G56", "marca": "Fiat", "modelo": "Strada", "ano": 2019}),
    (2, {"placa": "MNO5H67", "marca": "Hyundai", "modelo": "HR-V", "ano": 2022}),
    (3, {"placa": "PQR6I78", "marca": "Volkswagen", "modelo": "Jetta", "ano": 2021}),
    (4, {"placa": "STU7J89", "marca": "Ford", "modelo": "Fiesta", "ano": 2017}),
    (5, {"placa": "VWX8K90", "marca": "Fiat", "modelo": "Strada", "ano": 2020}),
    (5, {"placa": "YZA9L12", "marca": "Hyundai", "modelo": "HR", "ano": 2023}),
    (
        6,
        {
            "placa": "BCD0M23",
            "marca": "Mercedes-Benz",
            "modelo": "Sprinter",
            "ano": 2019,
        },
    ),
]

_SERVICOS: list[dict[str, Any]] = [
    {"nome": "Troca de oleo", "descricao": "Troca de oleo e filtro", "preco": 150.0},
    {"nome": "Alinhamento", "descricao": "Alinhamento 4 rodas", "preco": 120.0},
    {"nome": "Troca de pastilha", "descricao": "Pastilha dianteira", "preco": 280.0},
    {"nome": "Diagnostico eletronico", "descricao": "Scanner OBD-II", "preco": 200.0},
    {"nome": "Revisao completa", "descricao": "Revisao 10k km", "preco": 600.0},
    {
        "nome": "Troca de correia dentada",
        "descricao": "Correia + tensor + polia",
        "preco": 450.0,
    },
    {
        "nome": "Suspensao dianteira",
        "descricao": "Amortecedores + molas dianteiros",
        "preco": 380.0,
    },
    {"nome": "Bateria (troca + teste)", "descricao": "Troca com teste", "preco": 90.0},
]

# Backend exige descricao min_length=1 em CriarItemEstoqueRequest.
# 3 itens com quantidade baixa (<=5) ficam destacados na listagem — bom pra
# provar o alerta de estoque minimo na UI.
_ITENS: list[dict[str, Any]] = [
    {
        "nome": "Filtro de oleo",
        "descricao": "Universal",
        "quantidade": 20,
        "preco_unitario": 35.0,
    },
    {
        "nome": "Pastilha de freio dianteiro",
        "descricao": "Jogo dianteiro padrao",
        "quantidade": 15,
        "preco_unitario": 180.0,
    },
    {
        "nome": "Oleo 5W30",
        "descricao": "Litro",
        "quantidade": 50,
        "preco_unitario": 45.0,
    },
    {
        "nome": "Filtro de ar",
        "descricao": "Filtro de ar motor",
        "quantidade": 12,
        "preco_unitario": 28.0,
    },
    {
        "nome": "Vela de ignicao",
        "descricao": "Vela unitaria",
        "quantidade": 30,
        "preco_unitario": 18.0,
    },
    {
        "nome": "Correia dentada",
        "descricao": "Correia dentada universal",
        "quantidade": 5,
        "preco_unitario": 220.0,
    },
    {
        "nome": "Amortecedor",
        "descricao": "Par",
        "quantidade": 8,
        "preco_unitario": 350.0,
    },
    {
        "nome": "Lampada farol H7",
        "descricao": "Lampada H7 55W",
        "quantidade": 25,
        "preco_unitario": 22.0,
    },
    # Itens com qty baixa pra testar destaque amarelo:
    {
        "nome": "Junta de motor",
        "descricao": "Junta superior",
        "quantidade": 3,
        "preco_unitario": 140.0,
    },
    {
        "nome": "Fluido de freio",
        "descricao": "500ml",
        "quantidade": 18,
        "preco_unitario": 32.0,
    },
    {
        "nome": "Bateria 60Ah",
        "descricao": "Bateria selada",
        "quantidade": 6,
        "preco_unitario": 420.0,
    },
    {
        "nome": "Bateria 70Ah",
        "descricao": "Bateria selada",
        "quantidade": 4,
        "preco_unitario": 520.0,
    },
    {
        "nome": "Pastilha de freio traseiro",
        "descricao": "Jogo traseiro padrao",
        "quantidade": 10,
        "preco_unitario": 160.0,
    },
    {
        "nome": "Filtro de combustivel",
        "descricao": "Filtro linha",
        "quantidade": 22,
        "preco_unitario": 55.0,
    },
]


# Contagens esperadas em dataset "zerado" (sem dados pre-existentes).
# Expostas como constantes pra que os testes nao fiquem presos a literais
# repetidos toda vez que o seed for expandido.
_QTD_CLIENTES = len(_CLIENTES)
_QTD_VEICULOS = len(_VEICULOS)
_QTD_SERVICOS = len(_SERVICOS)
_QTD_ITENS = len(_ITENS)
_QTD_ORDENS = 8  # 7 estados + 1 repetido (RECEBIDA)


def gerar_dados_teste(
    api: ClienteApi,
    *,
    on_progresso: Callable[[int, str], None],
) -> RelatorioSeed:
    """Gera dados via API. Admin required. Idempotente por chave natural."""
    rel = RelatorioSeed()

    # 1. Clientes — idempotente por NOME (documento chega mascarado na listagem
    # por LGPD, entao nao da pra comparar com o documento cru do seed).
    on_progresso(0, "Carregando clientes existentes...")
    existentes_clientes = {
        c["nome"]: c for c in api.listar_clientes(limit=100).get("items", [])
    }
    ids_clientes: list[str] = []
    for i, cliente in enumerate(_CLIENTES):
        on_progresso(2 + i * 2, f"Cliente {cliente['nome']}")
        if cliente["nome"] in existentes_clientes:
            ids_clientes.append(existentes_clientes[cliente["nome"]]["id"])
            rel.clientes_existentes += 1
            continue
        try:
            resp = api.criar_cliente(cliente)
            ids_clientes.append(resp["id"])
            rel.clientes_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Cliente {cliente['nome']}: {exc}")

    # 2. Veiculos — idempotente por placa. Clientes ja existentes em
    # producao nao sao tocados porque suas placas nao batem com as do seed.
    on_progresso(16, "Adicionando veiculos...")
    for idx_cliente, veiculo in _VEICULOS:
        if idx_cliente >= len(ids_clientes):
            continue
        cid = ids_clientes[idx_cliente]
        try:
            veiculos_existentes = api.listar_veiculos(cid)
            if any(v.get("placa") == veiculo["placa"] for v in veiculos_existentes):
                continue
            api.adicionar_veiculo(cid, veiculo)
            rel.veiculos_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Veiculo {veiculo['placa']}: {exc}")

    # 3. Servicos
    on_progresso(30, "Catalogo de servicos...")
    existentes_servicos = {
        s["nome"]: s for s in api.listar_servicos(limit=100).get("items", [])
    }
    ids_servicos: list[str] = []
    for i, servico in enumerate(_SERVICOS):
        on_progresso(32 + i, f"Servico {servico['nome']}")
        if servico["nome"] in existentes_servicos:
            ids_servicos.append(existentes_servicos[servico["nome"]]["id"])
            rel.servicos_existentes += 1
            continue
        try:
            resp = api.criar_servico(servico)
            ids_servicos.append(resp["id"])
            rel.servicos_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Servico {servico['nome']}: {exc}")

    # 4. Itens de estoque
    on_progresso(45, "Itens de estoque...")
    existentes_itens = {
        i["nome"]: i for i in api.listar_estoque(limit=100).get("items", [])
    }
    ids_itens: list[str] = []
    for i, item in enumerate(_ITENS):
        on_progresso(47 + i, f"Item {item['nome']}")
        if item["nome"] in existentes_itens:
            ids_itens.append(existentes_itens[item["nome"]]["id"])
            rel.itens_existentes += 1
            continue
        try:
            resp = api.criar_item_estoque(item)
            ids_itens.append(resp["id"])
            rel.itens_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Item {item['nome']}: {exc}")

    # 5. Ordens em estados variados. Cada helper dirige a OS ate o estado
    # desejado via /diagnostico, /orcamento, /aprovacao, /finalizacao,
    # /entrega, /cancelamento (ver StatusOrdem.MaquinaDeStatus).
    # Guard de idempotencia: OS nao tem chave natural unica que a seed
    # possa checar (diferente de nome/placa). Se ja ha >= _QTD_ORDENS OS
    # no banco, assume que o seed ja rodou e pula criacao — evita que
    # re-run acumule OS (8, 16, 24, ...).
    on_progresso(65, "Criando OS em estados variados...")
    try:
        total_existente = int(api.listar_ordens(limit=1).get("total", 0))
    except ApiError as exc:
        rel.avisos.append(f"Nao consegui contar OS existentes: {exc}")
        total_existente = 0
    if total_existente >= _QTD_ORDENS:
        rel.avisos.append(
            f"{total_existente} OS ja existem (>= {_QTD_ORDENS} esperadas); pulando."
        )
    elif ids_clientes and ids_servicos:
        rel.ordens_criadas += _criar_os_recebida(api, ids_clientes[0], rel)
        on_progresso(70, "OS #2 — RECEBIDA (com item)")
        rel.ordens_criadas += _criar_os_recebida_com_item(
            api, ids_clientes[1 % len(ids_clientes)], ids_servicos[0], rel
        )
        on_progresso(74, "OS #3 — EM_DIAGNOSTICO")
        rel.ordens_criadas += _criar_os_em_diagnostico(
            api, ids_clientes[2 % len(ids_clientes)], ids_servicos[0], rel
        )
        on_progresso(78, "OS #4 — AGUARDANDO_APROVACAO")
        rel.ordens_criadas += _criar_os_aguardando_aprovacao(
            api,
            ids_clientes[3 % len(ids_clientes)],
            ids_servicos[0],
            ids_servicos[1],
            rel,
        )
        on_progresso(82, "OS #5 — EM_EXECUCAO")
        rel.ordens_criadas += _criar_os_em_execucao(
            api, ids_clientes[0], ids_servicos, ids_itens, rel
        )
        on_progresso(88, "OS #6 — FINALIZADA")
        rel.ordens_criadas += _criar_os_finalizada(
            api, ids_clientes[4 % len(ids_clientes)], ids_servicos, rel
        )
        on_progresso(92, "OS #7 — ENTREGUE")
        rel.ordens_criadas += _criar_os_entregue(
            api, ids_clientes[5 % len(ids_clientes)], ids_servicos, rel
        )
        on_progresso(96, "OS #8 — CANCELADA")
        rel.ordens_criadas += _criar_os_cancelada(
            api, ids_clientes[6 % len(ids_clientes)], rel
        )

    on_progresso(100, "Concluido")
    return rel


def _veiculo_id_do_cliente(
    api: ClienteApi, cliente_id: str, indice: int = 0
) -> str | None:
    """Pega o veiculo em ``indice`` do cliente; cai pro primeiro se idx > len."""
    veiculos = api.listar_veiculos(cliente_id)
    if not veiculos:
        return None
    return str(veiculos[min(indice, len(veiculos) - 1)]["id"])


def _criar_os_recebida(api: ClienteApi, cliente_id: str, rel: RelatorioSeed) -> int:
    """OS #1 — apenas aberta, sem item. Estado inicial da maquina."""
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        rel.avisos.append("OS #1: cliente sem veiculo")
        return 0
    try:
        api.criar_ordem(cliente_id, vid)
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #1: {exc}")
        return 0


def _criar_os_recebida_com_item(
    api: ClienteApi, cliente_id: str, servico_id: str, rel: RelatorioSeed
) -> int:
    """OS #2 — aberta com um item, ainda em RECEBIDA (pre-diagnostico)."""
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        rel.avisos.append("OS #2: cliente sem veiculo")
        return 0
    try:
        ordem = api.criar_ordem(cliente_id, vid)
        api.adicionar_item_ordem(
            ordem["id"],
            {
                "servico_catalogo_id": servico_id,
                "descricao": "Cliente relatou barulho no motor",
                "quantidade": 1,
            },
        )
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #2: {exc}")
        return 0


def _criar_os_em_diagnostico(
    api: ClienteApi, cliente_id: str, servico_id: str, rel: RelatorioSeed
) -> int:
    """OS #3 — com item, passou por /diagnostico."""
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        return 0
    try:
        ordem = api.criar_ordem(cliente_id, vid)
        api.adicionar_item_ordem(
            ordem["id"],
            {
                "servico_catalogo_id": servico_id,
                "descricao": "Servico solicitado pelo cliente",
                "quantidade": 1,
            },
        )
        api.executar_transicao(ordem["id"], "/diagnostico")
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #3: {exc}")
        return 0


def _criar_os_aguardando_aprovacao(
    api: ClienteApi,
    cliente_id: str,
    servico1_id: str,
    servico2_id: str,
    rel: RelatorioSeed,
) -> int:
    """OS #4 — dois itens + diagnostico + orcamento gerado (aguarda cliente)."""
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        return 0
    try:
        ordem = api.criar_ordem(cliente_id, vid)
        api.adicionar_item_ordem(
            ordem["id"],
            {
                "servico_catalogo_id": servico1_id,
                "descricao": "Servico principal",
                "quantidade": 1,
            },
        )
        api.adicionar_item_ordem(
            ordem["id"],
            {
                "servico_catalogo_id": servico2_id,
                "descricao": "Servico adicional",
                "quantidade": 1,
            },
        )
        api.executar_transicao(ordem["id"], "/diagnostico")
        api.executar_transicao(ordem["id"], "/orcamento")
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #4: {exc}")
        return 0


def _criar_os_em_execucao(
    api: ClienteApi,
    cliente_id: str,
    servicos: list[str],
    itens: list[str],
    rel: RelatorioSeed,
) -> int:
    """OS #5 — orcamento aprovado, em execucao. Inclui uma peca de estoque."""
    vid = _veiculo_id_do_cliente(api, cliente_id, indice=1)
    if not vid:
        return 0
    try:
        ordem = api.criar_ordem(cliente_id, vid)
        for idx, sid in enumerate(servicos[:2]):
            api.adicionar_item_ordem(
                ordem["id"],
                {
                    "servico_catalogo_id": sid,
                    "descricao": f"Servico #{idx + 1} em execucao",
                    "quantidade": 1,
                },
            )
        if itens and servicos:
            api.adicionar_item_ordem(
                ordem["id"],
                {
                    "servico_catalogo_id": servicos[0],
                    "item_estoque_id": itens[0],
                    "descricao": "Peca consumida",
                    "quantidade": 1,
                },
            )
        api.executar_transicao(ordem["id"], "/diagnostico")
        api.executar_transicao(ordem["id"], "/orcamento")
        api.executar_transicao(ordem["id"], "/aprovacao")
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #5: {exc}")
        return 0


def _criar_os_finalizada(
    api: ClienteApi,
    cliente_id: str,
    servicos: list[str],
    rel: RelatorioSeed,
) -> int:
    """OS #6 — percorreu todo o fluxo ate FINALIZADA (servico pronto)."""
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        return 0
    try:
        ordem = api.criar_ordem(cliente_id, vid)
        api.adicionar_item_ordem(
            ordem["id"],
            {
                "servico_catalogo_id": servicos[0],
                "descricao": "Servico concluido no prazo",
                "quantidade": 1,
            },
        )
        for endpoint in ("/diagnostico", "/orcamento", "/aprovacao", "/finalizacao"):
            api.executar_transicao(ordem["id"], endpoint)
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #6: {exc}")
        return 0


def _criar_os_entregue(
    api: ClienteApi,
    cliente_id: str,
    servicos: list[str],
    rel: RelatorioSeed,
) -> int:
    """OS #7 — FINALIZADA -> ENTREGUE. Estado terminal do fluxo feliz."""
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        return 0
    try:
        ordem = api.criar_ordem(cliente_id, vid)
        api.adicionar_item_ordem(
            ordem["id"],
            {
                "servico_catalogo_id": servicos[0],
                "descricao": "Entregue ao cliente",
                "quantidade": 1,
            },
        )
        for endpoint in (
            "/diagnostico",
            "/orcamento",
            "/aprovacao",
            "/finalizacao",
            "/entrega",
        ):
            api.executar_transicao(ordem["id"], endpoint)
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #7: {exc}")
        return 0


def _criar_os_cancelada(api: ClienteApi, cliente_id: str, rel: RelatorioSeed) -> int:
    """OS #8 — aberta e cancelada com motivo. Estado terminal do fluxo nao-feliz.

    O endpoint /cancelamento exige ``{"motivo": str}`` no body (min_length=1,
    max_length=500; ver CancelarOrdemRequest).
    """
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        return 0
    try:
        ordem = api.criar_ordem(cliente_id, vid)
        api.executar_transicao(
            ordem["id"],
            "/cancelamento",
            body={"motivo": "Cliente desistiu do servico"},
        )
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #8: {exc}")
        return 0
