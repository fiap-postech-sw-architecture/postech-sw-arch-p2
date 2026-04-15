# TODO(PR 12): replace stub with real JWT-backed authentication middleware
from __future__ import annotations

import os
from typing import Any


def _impedir_uso_em_producao() -> None:
    """Falha explicitamente se o stub for carregado em ambiente de producao.

    O stub retorna sempre um usuario fictício com papel admin, o que e aceitavel
    em testes e ambientes locais mas seria uma falha critica de seguranca em
    producao. A variavel de ambiente `ENVIRONMENT=production` bloqueia o stub
    e forca o deploy a carregar o middleware real (PR 12).
    """
    if os.environ.get("ENVIRONMENT") == "production":
        msg = (
            "autenticacao middleware stub invocado em producao. "
            "Substitua pelo middleware JWT real do PR 12."
        )
        raise RuntimeError(msg)


def obter_usuario_atual() -> dict[str, object]:
    """Stub temporario ate o contexto Autenticacao (PR 12) prover o middleware real.

    Retorna um usuario fixo com papel admin para permitir que os routers das
    fatias anteriores (Cliente+Veiculo, Catalogo, Estoque) executem em testes e
    em ambientes locais. Substitui-lo no PR 12 pela validacao JWT completa.
    Levanta `RuntimeError` se `ENVIRONMENT=production`, impedindo uso acidental.
    """
    _impedir_uso_em_producao()
    return {"sub": "stub", "papel": "admin"}


def exigir_papel(*_papeis: str) -> Any:
    """Stub temporario de guard de papel. Retorna sempre o usuario stub.

    Sera substituido no PR 12 por uma verificacao real contra os papeis
    contidos no token JWT validado. Levanta `RuntimeError` em producao.
    """

    def _dependency() -> dict[str, object]:
        return obter_usuario_atual()

    return _dependency
