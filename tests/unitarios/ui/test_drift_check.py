"""Sanity check contra drift entre constantes da UI e do dominio do backend.

Cobre dois espelhos:
- ``TRANSICOES_POR_STATUS`` (UI) deve cobrir todos os ``StatusOrdem``.
- ``_ESTADOS_PERMITE_ITENS`` (UI) deve casar valor-a-valor com o do dominio,
  porque a UI esconde botoes "Adicionar item" baseado nessa lista. Sem
  drift-check, ampliar a regra no agregado faria a UI mostrar botoes que
  retornam 409 silenciosamente.
"""

from __future__ import annotations

from src.ordem_servico.dominio.ordem_de_servico import (
    _ESTADOS_PERMITE_ITENS as ESTADOS_PERMITE_ITENS_BACKEND,
)
from src.ordem_servico.dominio.status import StatusOrdem
from ui.componentes.maquina_estados import TRANSICOES_POR_STATUS
from ui.paginas.ordens_servico import (
    _ESTADOS_PERMITE_ITENS as ESTADOS_PERMITE_ITENS_UI,
)


def test_todos_estados_do_backend_tem_mapeamento_no_ui() -> None:
    estados_backend = set(StatusOrdem)
    estados_ui = set(TRANSICOES_POR_STATUS.keys())
    faltando_no_ui = estados_backend - estados_ui
    assert not faltando_no_ui, (
        f"Estados adicionados ao backend sem mapeamento no UI: {faltando_no_ui}. "
        f"Adicione entradas em ui/componentes/maquina_estados.py"
        f"::TRANSICOES_POR_STATUS."
    )


def test_ui_nao_tem_estados_que_o_backend_nao_conhece() -> None:
    estados_backend = set(StatusOrdem)
    estados_ui = set(TRANSICOES_POR_STATUS.keys())
    fantasma_no_ui = estados_ui - estados_backend
    assert not fantasma_no_ui, (
        f"UI referencia estados inexistentes no backend: {fantasma_no_ui}"
    )


def test_estados_permite_itens_ui_casa_com_backend() -> None:
    """``ui.paginas.ordens_servico._ESTADOS_PERMITE_ITENS`` espelha a regra
    em ``src.ordem_servico.dominio.ordem_de_servico._ESTADOS_PERMITE_ITENS``.

    A UI armazena strings (porque le do response API) e o backend usa o
    enum ``StatusOrdem``; comparamos pelos ``.value``. Se o agregado
    ampliar a regra (ex.: permitir item em ``aguardando_aprovacao``) e a
    UI nao acompanhar, este teste quebra antes do drift virar bug 409.
    """
    valores_backend = {s.value for s in ESTADOS_PERMITE_ITENS_BACKEND}
    assert valores_backend == ESTADOS_PERMITE_ITENS_UI, (
        f"Drift detectado em _ESTADOS_PERMITE_ITENS:\n"
        f"  backend ({ESTADOS_PERMITE_ITENS_BACKEND}): {valores_backend}\n"
        f"  ui:      {ESTADOS_PERMITE_ITENS_UI}\n"
        f"Sincronize ui/paginas/ordens_servico.py."
    )
