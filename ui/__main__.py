"""Entry point: ``python -m ui``.

Delega pra ``ui.app.executar()`` que faz wiring do storage + ui.run(). Ver
comentario em ``app.executar()`` sobre por que reload fica desligado.
"""

from __future__ import annotations

# Importar `executar` de `ui.app` tambem traz o modulo inteiro, o que registra
# as paginas decoradas com `@ui.page` antes de `ui.run()` ser invocado.
from ui.app import executar

if __name__ in {"__main__", "__mp_main__"}:
    executar()
