"""Configuracao carregada do ambiente/.env do full-test."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Nao e segredo: espelha o default de DEMO do app no docker-compose.yml. O
# proprio valor declara "nao-usar-em-producao". S105 e falso-positivo aqui.
_WEBHOOK_TOKEN_DEMO_DEFAULT = "demo-webhook-orcamento-nao-usar-em-producao"  # noqa: S105


@dataclass(frozen=True, slots=True)
class FullTestConfig:
    base_url: str
    database_url: str
    admin_email: str
    admin_password: str
    n_clientes: int
    n_operadores: int
    n_admins: int
    http_timeout: float
    seed: int | None
    # RF-022: token do canal externo de decisao de orcamento. O default espelha
    # o default de demo do app no docker-compose.yml (chave ORCAMENTO_WEBHOOK_TOKEN),
    # garantindo paridade harness<->container em runs locais e CI sem env explicito.
    webhook_token: str


def carregar_config() -> FullTestConfig:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment]

    if load_dotenv is not None:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            load_dotenv(env_path)

    def _required(nome: str) -> str:
        valor = os.environ.get(nome, "").strip()
        if not valor:
            msg = f"{nome} obrigatoria no ambiente ou no full-test/.env"
            raise RuntimeError(msg)
        return valor

    seed_raw = os.environ.get("FULL_TEST_SEED", "").strip()
    seed: int | None = (
        None if not seed_raw or seed_raw.lower() == "none" else int(seed_raw)
    )

    return FullTestConfig(
        base_url=os.environ.get("FULL_TEST_BASE_URL", "http://localhost:8000"),
        database_url=_required("FULL_TEST_DATABASE_URL"),
        admin_email=_required("FULL_TEST_ADMIN_EMAIL"),
        admin_password=_required("FULL_TEST_ADMIN_PASSWORD"),
        n_clientes=int(os.environ.get("FULL_TEST_N_CLIENTES", "4")),
        n_operadores=int(os.environ.get("FULL_TEST_N_OPERADORES", "2")),
        n_admins=int(os.environ.get("FULL_TEST_N_ADMINS", "1")),
        http_timeout=float(os.environ.get("FULL_TEST_HTTP_TIMEOUT", "30")),
        seed=seed,
        webhook_token=os.environ.get(
            "ORCAMENTO_WEBHOOK_TOKEN", _WEBHOOK_TOKEN_DEMO_DEFAULT
        ),
    )
