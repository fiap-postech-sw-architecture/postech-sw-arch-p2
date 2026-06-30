"""Sanity check contra drift entre constantes da UI e do dominio do backend.

Cobre dois espelhos:
- ``TRANSICOES_POR_STATUS`` (UI) deve cobrir todos os ``StatusOrdem``.
- ``_ESTADOS_PERMITE_ADICAO``/``_REMOCAO`` (UI) devem casar valor-a-valor com
  os do dominio, porque a UI esconde os botoes "Adicionar"/"remover item"
  baseado neles. Sem drift-check, ampliar/restringir a regra no agregado faria
  a UI mostrar botoes que retornam 409 silenciosamente.
"""

from __future__ import annotations

from src.ordem_servico.dominio.ordem_de_servico import (
    _ESTADOS_PERMITE_ADICAO as ESTADOS_PERMITE_ADICAO_BACKEND,
)
from src.ordem_servico.dominio.ordem_de_servico import (
    _ESTADOS_PERMITE_REMOCAO as ESTADOS_PERMITE_REMOCAO_BACKEND,
)
from src.ordem_servico.dominio.status import StatusOrdem
from ui.componentes.maquina_estados import TRANSICOES_POR_STATUS
from ui.paginas.ordens_servico import (
    _ESTADOS_PERMITE_ADICAO as ESTADOS_PERMITE_ADICAO_UI,
)
from ui.paginas.ordens_servico import (
    _ESTADOS_PERMITE_REMOCAO as ESTADOS_PERMITE_REMOCAO_UI,
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
    """A UI espelha ``_ESTADOS_PERMITE_ADICAO``/``_REMOCAO`` do agregado (#80).

    A UI armazena strings (le do response API) e o backend usa o enum
    ``StatusOrdem``; comparamos pelos ``.value``. Adicao permite EM_EXECUCAO
    (trabalho extra -> orcamento complementar); remocao nao. Se o agregado
    ampliar/restringir e a UI nao acompanhar, este teste quebra antes do drift
    virar botao que retorna 409.
    """
    adicao_backend = {s.value for s in ESTADOS_PERMITE_ADICAO_BACKEND}
    assert adicao_backend == ESTADOS_PERMITE_ADICAO_UI, (
        f"Drift em _ESTADOS_PERMITE_ADICAO: backend {adicao_backend} != "
        f"ui {ESTADOS_PERMITE_ADICAO_UI}. Sincronize ui/paginas/ordens_servico.py."
    )
    remocao_backend = {s.value for s in ESTADOS_PERMITE_REMOCAO_BACKEND}
    assert remocao_backend == ESTADOS_PERMITE_REMOCAO_UI, (
        f"Drift em _ESTADOS_PERMITE_REMOCAO: backend {remocao_backend} != "
        f"ui {ESTADOS_PERMITE_REMOCAO_UI}. Sincronize ui/paginas/ordens_servico.py."
    )
