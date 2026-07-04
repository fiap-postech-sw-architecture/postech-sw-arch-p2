"""CLI de administracao da DLQ da outbox (RF-018).

Uso:
    python scripts/outbox_dlq.py list
    python scripts/outbox_dlq.py requeue <outbox_id>

Le ``DATABASE_URL`` do ambiente (mesma do app/relay). Imprime JSON para
ser consumido por humanos ou pipes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Garante que ``src.*`` seja importavel ao rodar ``python scripts/outbox_dlq.py``
# sem ``pip install -e .``. Idempotente: no-op se o projeto ja estiver no path.
# Mesmo idioma de scripts/seed_admin.py.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.compartilhado.infraestrutura.database import criar_engine  # noqa: E402
from src.compartilhado.infraestrutura.outbox_dlq import (  # noqa: E402
    listar_dead,
    reenfileirar,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.stderr.write("DATABASE_URL obrigatoria.\n")
        raise SystemExit(2)
    return criar_engine(url)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"list", "requeue"}:  # noqa: PLR2004
        sys.stderr.write("uso: outbox_dlq.py [list|requeue <id>]\n")
        return 2
    engine = _engine()
    try:
        if argv[1] == "list":
            print(json.dumps(listar_dead(engine), indent=2, ensure_ascii=False))
            return 0
        if len(argv) < 3:  # noqa: PLR2004
            sys.stderr.write("requeue exige <outbox_id>.\n")
            return 2
        ok = reenfileirar(engine, int(argv[2]))
        print(json.dumps({"reenfileirado": ok, "id": int(argv[2])}))
        return 0 if ok else 1
    finally:
        if hasattr(engine, "dispose"):
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
