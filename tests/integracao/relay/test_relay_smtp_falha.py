"""Integracao do CAMINHO REAL de entrega do relay contra SMTP morto (TD-008).

Os demais testes de relay (``test_relay_fluxo.py``) injetam handlers FAKE
que ``raise`` — provam a maquina de retry/backoff/DLQ, mas NAO o handler de
producao. Este teste fecha exatamente o gap que escondeu o bug do TD-008:
fia o handler REAL de entrega (``construir_mapa_handlers`` ->
``NotificarMudancaDeStatus`` com ``SmtpEmailAdapter`` real) contra um
endpoint SMTP MORTO e afirma que a linha vai para a DLQ (``dead``), nao
``entregue``, e que NENHUM ``processed_events`` e gravado.

Antes da correcao do TD-008 o handler engolia a excecao do envio: o relay
via "handler retornou normalmente", marcava ``entregue`` + gravava
``processed_events``, e o e-mail era perdido sem retry. Este teste falharia
(status viria ``entregue``).

Falha RAPIDA: o SMTP aponta para uma porta local fechada
(``SMTP_HOST=127.0.0.1``, ``SMTP_PORT=9``), entao ``enviar()`` levanta
``ConnectionRefusedError`` na hora — sem esperar o timeout de 5s do adapter
em cada uma das 5 tentativas. As 5 tentativas sao dirigidas antecipando
``proxima_tentativa_em`` entre os ciclos (mesmo padrao de
``test_falha_sempre_acumula_retries_ate_dead``).

Usa um cliente/veiculo/OS REAIS, commitados, para que o handler passe dos
skips (ordem/cliente/e-mail presentes) e realmente tente o envio — e a
session propria que o relay abre (``construir_mapa_handlers``) enxergue os
dados.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session as SASession

from relay.handlers import NOME_HANDLER_EMAIL, construir_mapa_handlers
from relay.processador import processar_ciclo
from tests.integracao.outbox_helpers import (
    antecipar as _antecipa,
)
from tests.integracao.outbox_helpers import (
    contar_processed as _conta_processed,
)
from tests.integracao.outbox_helpers import (
    inserir_pendente,
)
from tests.integracao.outbox_helpers import (
    status_tentativas as _status_tentativas,
)
from tests.integracao.seed_helpers import (
    criar_cliente_com_veiculo,
    criar_ordem_recebida,
    placa_unica,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Engine

pytestmark = pytest.mark.integracao

_LEASE = timedelta(seconds=60)
# Porta 9 (discard) tipicamente fechada em loopback: connect recusa NA HORA,
# sem cair no timeout de 5s do adapter (que multiplicaria por 5 tentativas).
_SMTP_PORT_MORTA = "9"

# A limpeza da outbox e autouse no conftest do pacote (`_outbox_limpa`).


def _agora() -> datetime:
    return datetime.now(UTC)


def _seed_os_real(engine: Engine) -> tuple[UUID, UUID]:
    """Cria cliente + veiculo + OS REAIS e commitados; retorna ``(os_id, cliente_id)``.

    Commit (em vez do savepoint da fixture ``session``) e obrigatorio: o
    relay abre a PROPRIA session contra o ``engine`` para resolver o
    contato e o agregado — dados nao-commitados ficariam invisiveis. Os
    ids voltam para a limpeza ESCOPADA do teardown (um DELETE global das
    tabelas seria um acoplamento latente com os demais testes). CPF/placa
    unicos por chamada (factory compartilhada): residuo de uma execucao
    abortada nao colide com a proxima.
    """
    with SASession(bind=engine, expire_on_commit=False) as sess:
        cliente = criar_cliente_com_veiculo(
            sess,
            nome="Cliente DLQ",
            contato="cliente.dlq@exemplo.com",
            placa=placa_unica("DLQ"),
        )
        ordem = criar_ordem_recebida(
            sess, cliente_id=cliente.id, veiculo_id=cliente.veiculos[0].id
        )
        sess.commit()
        return ordem.id, cliente.id


def _limpar_seed(engine: Engine, *, os_id: UUID, cliente_id: UUID) -> None:
    """Remove APENAS as linhas commitadas por este teste (ordem, veiculo, cliente)."""
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM ordens_de_servico WHERE id = :id"), {"id": os_id}
        )
        conn.execute(
            text("DELETE FROM veiculos WHERE cliente_id = :cid"), {"cid": cliente_id}
        )
        conn.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": cliente_id})


def _inserir_outbox_pendente(engine: Engine, agregado_id: UUID) -> int:
    return inserir_pendente(engine, agregado_id=agregado_id)


def test_falha_de_smtp_no_handler_real_vai_para_dlq(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # SMTP morto -> o adapter REAL levanta ConnectionRefusedError no envio.
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", _SMTP_PORT_MORTA)

    os_id, cliente_id = _seed_os_real(engine)
    try:
        outbox_id = _inserir_outbox_pendente(engine, os_id)

        # Caminho de entrega REAL: construir_mapa_handlers monta o handler de
        # producao (NotificarMudancaDeStatus + SmtpEmailAdapter) por tipo.
        handlers = construir_mapa_handlers(engine)

        # 5 ciclos: cada falha de transporte propaga -> processar_linha conta
        # uma tentativa; na 5a a linha vira `dead`. Entre ciclos, antecipamos
        # a re-elegibilidade (em producao o backoff faz o tempo passar).
        for esperado in range(1, 6):
            processar_ciclo(
                engine,
                handlers=handlers,
                nome_handler=NOME_HANDLER_EMAIL,
                limite=10,
                lease=_LEASE,
                relogio=_agora,
            )
            status, tentativas = _status_tentativas(engine, outbox_id)
            if esperado < 5:
                assert status == "pendente", (
                    f"ciclo {esperado}: esperado ainda 'pendente' (em backoff), "
                    f"obtido '{status}' — handler engoliu a falha de SMTP?"
                )
                assert tentativas == esperado
                _antecipa(engine, outbox_id)
            else:
                assert status == "dead", (
                    "apos 5 falhas de SMTP a linha deve ir para a DLQ ('dead'), "
                    f"nunca 'entregue'; obtido '{status}'"
                )
                assert tentativas == 5

        # Linha morta NUNCA foi entregue: nenhum processed_events gravado.
        assert _conta_processed(engine, outbox_id) == 0, (
            "linha em DLQ nao pode ter processed_events — marcaria o evento como "
            "consumido e bloquearia um reenfileiramento futuro"
        )
    finally:
        _limpar_seed(engine, os_id=os_id, cliente_id=cliente_id)
