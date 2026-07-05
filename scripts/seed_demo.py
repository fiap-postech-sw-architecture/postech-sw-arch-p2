"""Popula o banco com dados de demo via API HTTP do backend.

Complementa ``seed_usuarios.py``: enquanto aquele cria admin/atendente/
mecanico escrevendo direto no DB, este usa o endpoint de login + CRUD do
backend pra popular clientes, veiculos, catalogo, estoque e OS em estados
variados. Idempotente por chave natural (nome/placa) — reexecucoes nao
duplicam.

Uso:
    # (1) usuario seed admin precisa existir; rode antes se ainda nao:
    python scripts/seed_usuarios.py
    # (2) popular dados de demo:
    python scripts/seed_demo.py

    # ou via make:
    make seed-demo                 # alvo standalone
    make reset-db                  # nuke + seed-users + seed-demo

Pre-requisitos:
- backend respondendo em ``http://localhost:8000`` (configuravel via
  ``BACKEND_URL`` no env).
- admin seed criado (``scripts/seed_usuarios.py`` ou
  ``make seed-users-docker``).

Saida: contadores por etapa (clientes criados/existentes, OS por estado,
etc.) e uma lista de avisos se algum item falhou (nao aborta o run).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Garante que ``ui.*`` e ``src.*`` sejam importaveis ao rodar
# ``python scripts/seed_demo.py`` sem precisar de ``pip install -e .``.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ui.cliente_api import ApiError, ClienteApi  # noqa: E402
from ui.config import _USUARIOS_SEED  # noqa: E402
from ui.estado import StateStore, configurar_store  # noqa: E402
from ui.seed import RelatorioSeed, gerar_dados_teste  # noqa: E402


def _print_progresso(percent: int, mensagem: str) -> None:
    """Callback simples de progresso pra CLI (substitui o da UI)."""
    print(f"[{percent:>3}%] {mensagem}")


def _imprimir_relatorio(rel: RelatorioSeed) -> None:
    """Formata o ``RelatorioSeed`` de forma humana."""
    print()
    print("=== Resumo do seed de demo ===")
    c_novo, c_old = rel.clientes_criados, rel.clientes_existentes
    s_novo, s_old = rel.servicos_criados, rel.servicos_existentes
    i_novo, i_old = rel.itens_criados, rel.itens_existentes
    print(f"Clientes criados:  {c_novo:>3}  (ja existiam: {c_old})")
    print(f"Veiculos criados:  {rel.veiculos_criados:>3}")
    print(f"Servicos criados:  {s_novo:>3}  (ja existiam: {s_old})")
    print(f"Itens de estoque:  {i_novo:>3}  (ja existiam: {i_old})")
    print(f"Ordens de Servico: {rel.ordens_criadas:>3}")
    if rel.avisos:
        print()
        print(f"Avisos ({len(rel.avisos)}):")
        for aviso in rel.avisos:
            print(f"  - {aviso}")


def _obter_backend_url() -> str:
    """Prioridade: ``BACKEND_URL`` > ``UI_BACKEND_URL`` > default localhost:8000.

    Dois nomes historicos (BACKEND_URL do docker-compose + UI_BACKEND_URL do
    CONFIG.backend_url) — aceitamos ambos pra nao obrigar o caller a
    conhecer a configuracao exata.
    """
    return (
        os.environ.get("BACKEND_URL")
        or os.environ.get("UI_BACKEND_URL")
        or "http://localhost:8000"
    )


def main() -> int:
    backend_url = _obter_backend_url()
    admin = _USUARIOS_SEED["admin"]
    # No cloud (ADR-025) o admin tem senha FORTE do Secret, nao a senha dev
    # fixa de ui/config.py: ADMIN_EMAIL/ADMIN_PASSWORD do ambiente tem
    # prioridade. Local/compose (sem env) cai para a credencial seed padrao.
    admin_email = os.environ.get("ADMIN_EMAIL") or admin.email
    admin_senha = os.environ.get("ADMIN_PASSWORD") or admin.senha

    print(f">> seed_demo alvo: {backend_url}")
    print(f">> logando como admin: {admin_email}")

    # Store in-memory standalone — nao precisamos do ``nicegui.app.storage``
    # pra rodar em CLI; o StateStore sem backend cai pra um dict in-memory.
    store = StateStore()
    configurar_store(store)

    api = ClienteApi(base_url=backend_url, store=store)

    try:
        api.login(email=admin_email, senha=admin_senha)
    except ApiError as exc:
        print(f"!! Login admin falhou: {exc}")
        print("   Rode 'make seed-users-docker' (ou seed_usuarios.py) antes.")
        return 1

    try:
        rel = gerar_dados_teste(api, on_progresso=_print_progresso)
    except ApiError as exc:
        print(f"!! Seed abortado por erro na API: {exc}")
        return 2

    _imprimir_relatorio(rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
