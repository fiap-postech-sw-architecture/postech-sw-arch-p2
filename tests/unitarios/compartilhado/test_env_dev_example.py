"""Trava o conteudo critico de ``.env.dev.example``.

Regressao pinada: o dev que roda o projeto pela primeira vez copia
``.env.dev.example`` para ``.env.dev`` (ver ``Makefile`` / ``run.sh``). Se
esse exemplo nao tiver ``ENCRYPTION_KEY`` com valor valido, o backend gera
uma chave Fernet efemera em memoria a cada startup — e dados cifrados no DB
(CPF/CNPJ) ficam ilegiveis apos o primeiro restart, o que resulta em
``ValueError: CPF invalido`` no listar e surface como HTTP 500.

Esse foi o bug 2 da validacao manual. Teste estatico para garantir que o
arquivo de exemplo nunca mais volte sem ``ENCRYPTION_KEY`` valida.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_EXAMPLE = _REPO_ROOT / ".env.dev.example"


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parser minimalista de arquivo ``.env``: ignora comentarios e linhas vazias."""
    variaveis: dict[str, str] = {}
    for linha in path.read_text(encoding="utf-8").splitlines():
        stripped = linha.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        chave, valor = stripped.split("=", 1)
        variaveis[chave.strip()] = valor.strip()
    return variaveis


def test_arquivo_existe() -> None:
    assert _ENV_EXAMPLE.exists(), f"{_ENV_EXAMPLE} nao encontrado"


def test_encryption_key_presente_e_nao_vazia() -> None:
    """Bug 2: ausencia dessa chave no example causa 500 em /clientes apos
    restart do container em dev."""
    variaveis = _parse_env_file(_ENV_EXAMPLE)
    assert "ENCRYPTION_KEY" in variaveis, (
        "ENCRYPTION_KEY deve estar definida em .env.dev.example. "
        "Sem ela, o backend gera chave Fernet efemera a cada startup e "
        "corrompe dados cifrados entre restarts."
    )
    assert variaveis["ENCRYPTION_KEY"], (
        "ENCRYPTION_KEY nao pode ter valor vazio em .env.dev.example. "
        "Deve conter uma chave Fernet valida (base64 url-safe 32 bytes)."
    )


def test_encryption_key_e_fernet_valida() -> None:
    """Apenas ter um valor nao basta: precisa ser uma chave Fernet parseavel.
    ``Fernet(key)`` rejeita chaves com tamanho ou codificacao errados."""
    variaveis = _parse_env_file(_ENV_EXAMPLE)
    valor = variaveis.get("ENCRYPTION_KEY", "")
    try:
        Fernet(valor.encode())
    except (ValueError, TypeError) as exc:
        pytest.fail(
            f"ENCRYPTION_KEY em {_ENV_EXAMPLE.name} nao e Fernet valida: {exc}. "
            "Gere uma nova com: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )


def test_encryption_key_aparece_apenas_uma_vez() -> None:
    """Evita que merges/rebases futuros deixem duas declaracoes (uma vazia,
    uma preenchida) — a ordem de carga dos dotenv resolve pela ultima, que
    silenciosamente pode virar a vazia."""
    linhas_encryption = [
        linha
        for linha in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if linha.startswith("ENCRYPTION_KEY=")
    ]
    assert len(linhas_encryption) == 1, (
        f"Esperava exatamente 1 declaracao ENCRYPTION_KEY=, achei "
        f"{len(linhas_encryption)}: {linhas_encryption!r}. "
        "Conflito de merge resolvido a toa?"
    )


def test_orcamento_webhook_token_presente_e_nao_vazio() -> None:
    """RF-022 (ADR-021): sem ``ORCAMENTO_WEBHOOK_TOKEN`` no example, o dev
    que copia o arquivo sobe o backend com o canal externo de decisao de
    orcamento desabilitado (503) sem perceber."""
    variaveis = _parse_env_file(_ENV_EXAMPLE)
    assert "ORCAMENTO_WEBHOOK_TOKEN" in variaveis, (
        "ORCAMENTO_WEBHOOK_TOKEN deve estar definida em .env.dev.example. "
        "Sem ela o endpoint externo de decisao de orcamento responde 503 "
        "(canal desabilitado) em dev."
    )
    assert variaveis["ORCAMENTO_WEBHOOK_TOKEN"], (
        "ORCAMENTO_WEBHOOK_TOKEN nao pode ser vazia em .env.dev.example: "
        "vazio significa canal externo desabilitado (503)."
    )
