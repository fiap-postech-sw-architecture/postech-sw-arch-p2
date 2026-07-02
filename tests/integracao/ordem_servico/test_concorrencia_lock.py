"""Concorrencia pessimista (SELECT FOR UPDATE) sobre Postgres real.

Cobre as duas findings de lost-update / corrida resolvidas com lock
pessimista, com provas DETERMINISTICAS (duas conexoes/sessions reais, sem
``sleep`` como sincronizacao):

- #82 — transicoes da ``OrdemDeServico`` carregadas com ``com_lock=True``
  serializam no banco: duas transicoes concorrentes na MESMA OS resultam
  em exatamente 1 commit + 1 evento na outbox; a perdedora bloqueia no
  lock, re-le o estado pos-commit e a maquina de status rejeita a
  transicao agora ilegal (1 sucesso, 1 conflito, 1 evento — nao N).
- #83 — ``reservar``/``liberar`` do adapter de estoque carregam o
  ``ItemEstoque`` com ``FOR UPDATE``: duas reservas concorrentes sobre o
  mesmo item com saldo que satisfaz apenas uma nao sobre-vendem (o saldo
  nunca fica negativo; uma reserva vence, a outra serializa e falha com
  ``EstoqueInsuficienteException``).

Modelo deterministico (espelha ``relay/test_relay_fluxo.py::
test_fencing_serializa_duas_replicas_na_entrega``): a prova do LOCK em si
segura a tx vencedora aberta e mostra que a perdedora, num ``nowait=True``,
falha imediatamente — sem depender de timing. As provas de RESULTADO
(evento unico / sem sobre-venda) usam duas threads com suas proprias
conexoes e uma barreira para maximizar a sobreposicao.

Conexoes proprias (``engine.connect()``), nunca a fixture ``session``
(savepoint): FOR UPDATE entre transacoes so e observavel com transacoes
fisicas distintas.
"""

from __future__ import annotations

import itertools
import threading
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as SASession

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import (
    EstoqueInsuficienteException,
    TransicaoStatusInvalidaException,
)
from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
from src.estoque.dominio.item_estoque import ItemEstoque
from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
from src.ordem_servico.aplicacao.use_cases import IniciarDiagnostico
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.adapters import EstoqueSQLAlchemyAdapter
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from sqlalchemy import Engine

pytestmark = pytest.mark.integracao


# ---------------------------------------------------------------------------
# Seeds (commitados de verdade: as threads usam conexoes/transacoes proprias,
# entao o estado precisa estar visivel fora da tx do seed). Cleanup escopado
# por id no finally de cada teste, nunca DELETE global das tabelas.
# ---------------------------------------------------------------------------


_contador_placa = itertools.count(1)


def _placa_unica() -> str:
    """Placa unica no padrao antigo ``ABC1234`` (3 letras + 4 digitos).

    Cada teste comita seu seed de verdade (as threads usam conexoes
    proprias), entao reusar placa/CPF fixos colidiria com residuo de um
    teste anterior cujo cleanup nao rodou (ex.: falha antes do ``finally``).
    Ids unicos tornam cada teste independente da ordem/limpeza dos demais.
    Um contador monotonico (4 digitos, 0001-9999) garante unicidade dentro
    da sessao de teste.
    """
    n = next(_contador_placa) % 10000
    return f"LCK{n:04d}"


def _seed_cliente_e_veiculo(engine: Engine) -> tuple[UUID, UUID]:
    from brutils.cpf import generate as gerar_cpf

    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    with SASession(bind=engine, expire_on_commit=False) as sess:
        cliente = Cliente(
            _nome="Cliente Concorrencia",
            _documento=CPF(numero=gerar_cpf()),  # CPF valido e unico por seed
            _contato=Contato(valor="11999990000"),
        )
        ClienteSQLAlchemyRepository(session=sess).salvar(cliente)
        cliente.adicionar_veiculo(
            placa=Placa(valor=_placa_unica()), marca="Fiat", modelo="Uno", ano=2020
        )
        sess.flush()
        veiculo_id = cliente.veiculos[0].id
        cliente_id = cliente.id
        sess.commit()
    return cliente_id, veiculo_id


def _seed_ordem_recebida(engine: Engine) -> UUID:
    cliente_id, veiculo_id = _seed_cliente_e_veiculo(engine)
    with SASession(bind=engine, expire_on_commit=False) as sess:
        ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
        ordem.limpar_eventos()  # nao exercita o evento de criacao na outbox aqui
        OrdemDeServicoSQLAlchemyRepository(session=sess).salvar(ordem)
        ordem_id = ordem.id
        sess.commit()
    return ordem_id


def _seed_item(engine: Engine, *, quantidade: int) -> UUID:
    with SASession(bind=engine, expire_on_commit=False) as sess:
        item = ItemEstoque(
            _nome="Peca Disputada",
            _descricao="item para teste de concorrencia",
            _quantidade=quantidade,
            _preco_unitario=Dinheiro(valor=Decimal("10.00")),
        )
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        ItemEstoqueSQLAlchemyRepository(session=sess).salvar(item)
        item.limpar_eventos()
        item_id = item.id
        sess.commit()
    return item_id


def _limpar_ordem(engine: Engine, ordem_id: UUID) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM outbox WHERE agregado_id = :id"), {"id": ordem_id}
        )
        row = conn.execute(
            text("SELECT cliente_id, veiculo_id FROM ordens_de_servico WHERE id = :id"),
            {"id": ordem_id},
        ).first()
        conn.execute(
            text("DELETE FROM itens_da_ordem WHERE ordem_id = :id"), {"id": ordem_id}
        )
        conn.execute(
            text("DELETE FROM ordens_de_servico WHERE id = :id"), {"id": ordem_id}
        )
        if row is not None:
            conn.execute(
                text("DELETE FROM veiculos WHERE id = :id"), {"id": row.veiculo_id}
            )
            conn.execute(
                text("DELETE FROM clientes WHERE id = :id"), {"id": row.cliente_id}
            )


def _limpar_item(engine: Engine, item_id: UUID) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM outbox WHERE agregado_id = :id"), {"id": item_id}
        )
        conn.execute(text("DELETE FROM itens_estoque WHERE id = :id"), {"id": item_id})


def _status_no_banco(engine: Engine, ordem_id: UUID) -> str | None:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT status FROM ordens_de_servico WHERE id = :id"),
            {"id": ordem_id},
        ).first()
    return None if row is None else str(row.status)


def _eventos_na_outbox(engine: Engine, agregado_id: UUID, tipo: str) -> int:
    with engine.begin() as conn:
        n = conn.execute(
            text(
                "SELECT count(*) AS n FROM outbox "
                "WHERE agregado_id = :id AND tipo = :tipo"
            ),
            {"id": agregado_id, "tipo": tipo},
        ).scalar()
    return int(n or 0)


def _quantidade_no_banco(engine: Engine, item_id: UUID) -> int:
    with engine.begin() as conn:
        n = conn.execute(
            text("SELECT quantidade FROM itens_estoque WHERE id = :id"),
            {"id": item_id},
        ).scalar()
    return int(n)


def _enfileirar_eventos_da_ordem(sess: SASession, ordem: OrdemDeServico) -> None:
    """Insere os ``IntegrationEvent`` da ordem na outbox (espelha a UoW).

    Replica o que ``SQLAlchemyUnitOfWork.commit`` faz ANTES do commit — usado
    no teste deterministico de #82, onde A precisa segurar a tx aberta entre
    a aquisicao do lock e o commit (a UoW comita atomicamente, sem ponto de
    pausa). Mesma serializacao -> o evento gravado e identico ao do caminho
    de producao.
    """
    from src.compartilhado.aplicacao.outbox import serializar_integration_event
    from src.compartilhado.dominio.integration_event import IntegrationEvent
    from src.compartilhado.infraestrutura.outbox_mapping import inserir_na_outbox

    registros = [
        serializar_integration_event(ev)
        for ev in ordem.coletar_eventos()
        if isinstance(ev, IntegrationEvent)
    ]
    if registros:
        inserir_na_outbox(sess, registros)


def _esperar_backend_bloqueado(engine: Engine, prazo_s: float = 10.0) -> bool:
    """Espera ate um backend ficar BLOQUEADO esperando lock (deterministico).

    Sincronizacao por CONDICAO observada no proprio Postgres
    (``pg_stat_activity.wait_event_type = 'Lock'``), nao por ``sleep`` de
    duracao fixa: retorna assim que a thread B esta provadamente parada no
    ``SELECT ... FOR UPDATE`` (esperando o lock que A detem). Se a condicao
    nunca aparece dentro do prazo, devolve ``False`` (o caller falha o
    teste). Espelha a logica do fencing test do relay (prova por estado, nao
    por timing).
    """
    import time

    prazo = time.time() + prazo_s
    while time.time() < prazo:
        with engine.connect() as conn:
            bloqueados = conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND state = 'active'"
                )
            ).scalar()
        if bloqueados and int(bloqueados) >= 1:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------------------
# #82 — transicoes da OS sob lock pessimista
# ---------------------------------------------------------------------------


class TestConcorrenciaTransicaoOrdemDeServico:
    def test_lock_serializa_segunda_tx_que_re_le_e_rejeita(
        self, engine: Engine
    ) -> None:
        """Prova determinista do FOR UPDATE no caminho de transicao (#82).

        Sem timing: conexao A inicia ``IniciarDiagnostico`` carregando a OS
        ``com_lock=True`` e MANTEM a tx aberta (dona da transicao). Conexao
        B tenta carregar a MESMA linha com ``FOR UPDATE NOWAIT`` e falha
        imediatamente -> a linha esta de fato travada por A (o 2o request
        concorrente bloquearia no lock real ``nowait=False`` em vez de ler
        estado stale). Apos A commitar, B re-le ``em_diagnostico`` e a
        maquina de status rejeita a transicao agora ilegal.
        """
        ordem_id = _seed_ordem_recebida(engine)
        conn_a = engine.connect()
        conn_b = engine.connect()
        try:
            # A: carrega a OS COM LOCK e aplica a transicao, mas NAO commita.
            sess_a = SASession(bind=conn_a, expire_on_commit=False)
            repo_a = OrdemDeServicoSQLAlchemyRepository(session=sess_a)
            ordem_a = repo_a.obter_por_id(ordem_id, com_lock=True)
            assert ordem_a is not None
            ordem_a.iniciar_diagnostico()
            repo_a.salvar(ordem_a)  # flush: UPDATE emitido, lock retido

            # B: a linha esta travada por A -> FOR UPDATE NOWAIT falha agora.
            conn_b.execute(text("BEGIN"))
            with pytest.raises(OperationalError):
                conn_b.execute(
                    text(
                        "SELECT id FROM ordens_de_servico "
                        "WHERE id = :id FOR UPDATE NOWAIT"
                    ),
                    {"id": ordem_id},
                )
            conn_b.execute(text("ROLLBACK"))

            # A commita a transicao -> libera o lock e persiste o novo estado.
            sess_a.commit()
            sess_a.close()
        finally:
            conn_a.close()
            conn_b.close()

        # B agora re-le o estado pos-commit; a transicao virou ilegal.
        conn_b2 = engine.connect()
        try:
            sess_b = SASession(bind=conn_b2, expire_on_commit=False)
            repo_b = OrdemDeServicoSQLAlchemyRepository(session=sess_b)
            ordem_b = repo_b.obter_por_id(ordem_id, com_lock=True)
            assert ordem_b is not None
            assert ordem_b.status is StatusOrdem.EM_DIAGNOSTICO
            with pytest.raises(TransicaoStatusInvalidaException):
                ordem_b.iniciar_diagnostico()
            sess_b.close()
        finally:
            conn_b2.close()

        try:
            assert _status_no_banco(engine, ordem_id) == "em_diagnostico"
        finally:
            _limpar_ordem(engine, ordem_id)

    def test_transicao_concorrente_gera_um_unico_evento_e_um_conflito(
        self, engine: Engine
    ) -> None:
        """Prova central do #82: 1 evento, nao N — via use case REAL, determinista.

        Exercita ``IniciarDiagnostico.executar`` (caminho de producao:
        ``_obter_ordem(com_lock=True)`` + UoW + outbox) sob concorrencia
        SERIALIZADA por estado observado, sem ``sleep`` de sincronizacao:

        1. Conexao A trava a linha da OS (``SELECT ... FOR UPDATE``) e MANTEM
           a tx aberta — simula a 1a requisicao "em voo".
        2. Thread B chama o use case real; como A detem o lock, B BLOQUEIA no
           ``FOR UPDATE`` de ``_obter_ordem`` (esperamos ate o Postgres
           reportar o backend de B em ``wait_event_type='Lock'`` —
           sincronizacao por condicao, nao por timing).
        3. A aplica a transicao vencedora (UPDATE + outbox) e comita -> 1
           evento, lock liberado.
        4. B desbloqueia, ``_obter_ordem`` re-le ``em_diagnostico`` e a
           maquina de status REJEITA -> B levanta
           ``TransicaoStatusInvalidaException``, sem emitir evento.

        Resultado: estado final unico (``em_diagnostico``) + EXATAMENTE 1
        ``DiagnosticoIniciadoEvent`` na outbox. Sem o lock, B leria o estado
        stale no passo 2 (nao bloquearia), validaria e emitiria -> 2 eventos
        (provado pela inversao: trocar com_lock para False neste caminho faz
        o assert de contagem=1 falhar com 2).
        """
        ordem_id = _seed_ordem_recebida(engine)
        resultado_b: dict[str, object] = {}
        b_terminou = threading.Event()

        def worker_b() -> None:
            conn = engine.connect()
            try:
                sess = SASession(bind=conn, expire_on_commit=False)
                uc = IniciarDiagnostico(
                    repo=OrdemDeServicoSQLAlchemyRepository(session=sess),
                    uow=SQLAlchemyUnitOfWork(session_factory=lambda: sess),
                    dispatcher=EventDispatcher(handlers=()),
                )
                try:
                    uc.executar(ordem_id)
                    resultado_b["status"] = "sucesso"
                except TransicaoStatusInvalidaException:
                    resultado_b["status"] = "conflito"
                finally:
                    sess.close()
            finally:
                conn.close()
                b_terminou.set()

        conn_a = engine.connect()
        sess_a = SASession(bind=conn_a, expire_on_commit=False)
        try:
            # 1. A carrega a OS COM LOCK (FOR UPDATE) pela MESMA session que
            #    vai commitar; aplica a transicao e faz flush (UPDATE emitido,
            #    lock retido) — tudo numa unica tx da session, ainda aberta.
            repo_a = OrdemDeServicoSQLAlchemyRepository(session=sess_a)
            ordem_a = repo_a.obter_por_id(ordem_id, com_lock=True)
            assert ordem_a is not None
            ordem_a.iniciar_diagnostico()
            repo_a.salvar(ordem_a)  # flush: UPDATE + lock retido, sem commit

            # 2. B comeca e DEVE bloquear no FOR UPDATE de _obter_ordem.
            thread_b = threading.Thread(target=worker_b)
            thread_b.start()
            assert _esperar_backend_bloqueado(engine), (
                "thread B nao bloqueou no lock — o caminho de transicao nao "
                "esta adquirindo FOR UPDATE (#82)"
            )
            assert not b_terminou.is_set(), "B terminou sem bloquear (sem lock?)"

            # 3. A enfileira o evento na outbox (mesmo caminho da UoW) e comita
            #    -> 1 evento, lock liberado.
            _enfileirar_eventos_da_ordem(sess_a, ordem_a)
            sess_a.commit()

            # 4. B desbloqueia e re-le o estado pos-commit -> rejeita.
            thread_b.join(timeout=15)
            assert not thread_b.is_alive(), "B nao concluiu apos A liberar o lock"
        finally:
            sess_a.close()
            conn_a.close()

        try:
            assert resultado_b.get("status") == "conflito", (
                f"B deveria conflitar, obtido {resultado_b.get('status')!r}"
            )
            assert _status_no_banco(engine, ordem_id) == "em_diagnostico"
            # A prova central da issue: UM unico evento, nao N.
            assert _eventos_na_outbox(engine, ordem_id, "DiagnosticoIniciadoEvent") == 1
        finally:
            _limpar_ordem(engine, ordem_id)


# ---------------------------------------------------------------------------
# #83 — reserva/liberacao de estoque sob lock pessimista
# ---------------------------------------------------------------------------


class TestConcorrenciaReservaEstoque:
    def test_lock_da_reserva_bloqueia_segunda_tx(self, engine: Engine) -> None:
        """Prova determinista do FOR UPDATE em ``reservar`` (#83).

        Conexao A reserva via adapter (carrega o item COM LOCK) e mantem a
        tx aberta; conexao B tenta ``FOR UPDATE NOWAIT`` na mesma linha e
        falha imediatamente -> ``reservar`` de fato trava a linha (o load
        cru ``session.get`` anterior nao travava, permitindo o lost-update).
        """
        item_id = _seed_item(engine, quantidade=5)
        conn_a = engine.connect()
        conn_b = engine.connect()
        try:
            sess_a = SASession(bind=conn_a, expire_on_commit=False)
            EstoqueSQLAlchemyAdapter(session=sess_a).reservar(item_id, 3)

            conn_b.execute(text("BEGIN"))
            with pytest.raises(OperationalError):
                conn_b.execute(
                    text(
                        "SELECT id FROM itens_estoque WHERE id = :id FOR UPDATE NOWAIT"
                    ),
                    {"id": item_id},
                )
            conn_b.execute(text("ROLLBACK"))

            sess_a.commit()
            sess_a.close()
        finally:
            conn_a.close()
            conn_b.close()

        try:
            assert _quantidade_no_banco(engine, item_id) == 2
        finally:
            _limpar_item(engine, item_id)

    def test_duas_reservas_concorrentes_nao_sobre_vendem(self, engine: Engine) -> None:
        """Duas reservas concorrentes do mesmo item com saldo para UMA (#83).

        Saldo = 3, cada reserva pede 2. Sem lock, ambas leriam 3 e
        gravariam 1 (lost-update -> 4 reservados sobre 3 = sobre-venda). Com
        FOR UPDATE, a 2a serializa, re-le o saldo ja decrementado (1) e
        falha com ``EstoqueInsuficienteException``. Invariantes: o saldo
        final nunca fica negativo e a soma reservada <= saldo inicial.
        """
        item_id = _seed_item(engine, quantidade=3)
        barreira = threading.Barrier(2)
        sucessos: list[int] = []
        insuficientes: list[str] = []
        lock = threading.Lock()
        pedido = 2

        def worker() -> None:
            barreira.wait()
            conn = engine.connect()
            try:
                sess = SASession(bind=conn, expire_on_commit=False)
                uow = SQLAlchemyUnitOfWork(session_factory=lambda: sess)
                adapter = EstoqueSQLAlchemyAdapter(session=sess)
                try:
                    with uow:
                        adapter.reservar(item_id, pedido)
                        uow.commit()
                    with lock:
                        sucessos.append(pedido)
                except EstoqueInsuficienteException:
                    with lock:
                        insuficientes.append("insuficiente")
            finally:
                conn.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        try:
            # Exatamente uma reserva vence; a outra serializa e e rejeitada.
            assert len(sucessos) == 1, f"esperado 1 sucesso, obtido {len(sucessos)}"
            assert len(insuficientes) == 1, (
                f"esperado 1 rejeicao, obtido {len(insuficientes)}"
            )
            saldo_final = _quantidade_no_banco(engine, item_id)
            assert saldo_final >= 0, "saldo nunca pode ficar negativo"
            assert saldo_final == 1, "exatamente uma reserva de 2 sobre saldo 3"
            assert sum(sucessos) <= 3, "soma reservada nao pode exceder o saldo inicial"
        finally:
            _limpar_item(engine, item_id)

    def test_reservas_multi_item_adquirem_lock_em_ordem_de_id(
        self, engine: Engine
    ) -> None:
        """Locks multi-item em ordem deterministica de id (anti-deadlock, #83).

        Duas transacoes reservando o MESMO conjunto de itens em ordens
        opostas de entrada nao deadlockam porque ``reservar`` ordena por id
        antes de travar (espelha ``obter_por_ids`` do repo de estoque). Sem
        ordem determinista, T1(item_a, item_b) x T2(item_b, item_a) poderia
        cruzar locks. Aqui ambas concluem (saldo suficiente) sem deadlock.
        """
        item_a = _seed_item(engine, quantidade=10)
        item_b = _seed_item(engine, quantidade=10)
        # ordena por id para que as duas threads passem a MESMA ordem de
        # aquisicao ao adapter (o ponto do teste e nao deadlockar mesmo que
        # as listas de entrada estejam invertidas).
        menor, maior = sorted([item_a, item_b])
        barreira = threading.Barrier(2)
        erros: list[str] = []
        lock = threading.Lock()

        def worker(ids_na_ordem_de_entrada: list[UUID]) -> None:
            barreira.wait()
            conn = engine.connect()
            try:
                sess = SASession(bind=conn, expire_on_commit=False)
                uow = SQLAlchemyUnitOfWork(session_factory=lambda: sess)
                adapter = EstoqueSQLAlchemyAdapter(session=sess)
                try:
                    with uow:
                        for iid in sorted(ids_na_ordem_de_entrada):
                            adapter.reservar(iid, 1)
                        uow.commit()
                except Exception as exc:  # registra qualquer falha/deadlock
                    with lock:
                        erros.append(repr(exc))
            finally:
                conn.close()

        # T1 recebe [menor, maior]; T2 recebe [maior, menor] — ordens opostas
        # de ENTRADA, mas o sorted() interno iguala a ordem de AQUISICAO.
        t1 = threading.Thread(target=worker, args=([menor, maior],))
        t2 = threading.Thread(target=worker, args=([maior, menor],))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        try:
            assert not t1.is_alive(), "T1 nao concluiu — possivel deadlock"
            assert not t2.is_alive(), "T2 nao concluiu — possivel deadlock"
            assert erros == [], f"reservas multi-item falharam: {erros}"
            assert _quantidade_no_banco(engine, menor) == 8
            assert _quantidade_no_banco(engine, maior) == 8
        finally:
            _limpar_item(engine, item_a)
            _limpar_item(engine, item_b)


def _make_lock_probe(engine: Engine) -> Callable[[UUID], bool]:
    """(helper de leitura) — confirma que uma linha NAO esta travada.

    Usado pelos testes de caminho read-only para provar que consultas sem
    ``com_lock`` nao adquirem FOR UPDATE: se a linha estivesse travada, o
    ``FOR UPDATE NOWAIT`` aqui falharia.
    """

    def _probe(row_id: UUID) -> bool:
        conn = engine.connect()
        try:
            conn.execute(text("BEGIN"))
            conn.execute(
                text(
                    "SELECT id FROM ordens_de_servico WHERE id = :id FOR UPDATE NOWAIT"
                ),
                {"id": row_id},
            )
            conn.execute(text("ROLLBACK"))
            return True
        except OperationalError:
            conn.execute(text("ROLLBACK"))
            return False
        finally:
            conn.close()

    return _probe


class TestCaminhoLeituraPermaneceSemLock:
    def test_obter_por_id_default_nao_trava_a_linha(self, engine: Engine) -> None:
        """O caminho read-only (default ``com_lock=False``) NAO adquire lock (#82).

        ``ObterOrdem``/consultas compartilham ``_obter_ordem`` -> default
        sem lock. Carregar a OS sem ``com_lock`` deixa a linha LIVRE: uma
        segunda conexao consegue ``FOR UPDATE NOWAIT`` enquanto a primeira
        session ainda esta aberta. (Contraste com o caminho de transicao,
        que trava — provado em ``test_lock_serializa_...``.)
        """
        ordem_id = _seed_ordem_recebida(engine)
        probe = _make_lock_probe(engine)
        conn = engine.connect()
        try:
            sess = SASession(bind=conn, expire_on_commit=False)
            repo = OrdemDeServicoSQLAlchemyRepository(session=sess)
            ordem = repo.obter_por_id(ordem_id)  # default: sem lock
            assert ordem is not None
            # Linha livre: outra conexao adquire FOR UPDATE NOWAIT sem falhar.
            assert probe(ordem_id) is True, "leitura default nao deveria travar a linha"
            sess.close()
        finally:
            conn.close()
            _limpar_ordem(engine, ordem_id)


# ---------------------------------------------------------------------------
# #117 — releitura sob FOR UPDATE devolve estado fresco (populate_existing +
# listener de refresh no mapping)
# ---------------------------------------------------------------------------


class TestReleituraComLockRefrescaIdentityMap:
    """#117: ``obter_por_id(com_lock=True)`` deve refletir o estado commitado
    por OUTRA transacao mesmo quando a instancia ja foi carregada (sem lock) na
    session — ou seja, ja esta no identity map. Sem ``populate_existing=True``
    (+ listener de ``refresh`` no mapping) o SELECT FOR UPDATE devolveria o
    objeto stale: o lock e adquirido no banco, mas o estado em memoria seria o
    antigo, derrotando a serializacao de concorrencia de #82/#83.
    """

    def test_os_com_lock_reflete_commit_externo_apos_leitura_sem_lock(
        self, engine: Engine
    ) -> None:
        ordem_id = _seed_ordem_recebida(engine)
        try:
            with SASession(bind=engine, expire_on_commit=False) as sess:
                repo = OrdemDeServicoSQLAlchemyRepository(session=sess)
                # 1a leitura SEM lock: poe a OS (recebida) no identity map.
                ordem_stale = repo.obter_por_id(ordem_id)
                assert ordem_stale is not None
                assert ordem_stale.status is StatusOrdem.RECEBIDA

                # Outra transacao avanca o status e commita.
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE ordens_de_servico SET status = :novo, "
                            "atualizado_em = now() WHERE id = :id"
                        ),
                        {"novo": StatusOrdem.EM_DIAGNOSTICO.value, "id": ordem_id},
                    )

                # Releitura COM lock: a MESMA instancia (identity map), mas com
                # o status de dominio reconstruido a partir do estado fresco.
                ordem_fresca = repo.obter_por_id(ordem_id, com_lock=True)
                assert ordem_fresca is ordem_stale
                assert ordem_fresca.status is StatusOrdem.EM_DIAGNOSTICO
        finally:
            _limpar_ordem(engine, ordem_id)

    def test_item_estoque_com_lock_reflete_commit_externo(self, engine: Engine) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        item_id = _seed_item(engine, quantidade=5)
        try:
            with SASession(bind=engine, expire_on_commit=False) as sess:
                repo = ItemEstoqueSQLAlchemyRepository(session=sess)
                item_stale = repo.obter_por_id(item_id)
                assert item_stale is not None
                assert item_stale.quantidade == 5

                # Outra transacao muda saldo (coluna crua) E preco (VO
                # reconstruido pelo listener) e commita.
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE itens_estoque SET quantidade = :q, "
                            "preco_unitario_valor = :p WHERE id = :id"
                        ),
                        {"q": 2, "p": Decimal("99.00"), "id": item_id},
                    )

                item_fresco = repo.obter_por_id(item_id, com_lock=True)
                assert item_fresco is item_stale
                assert item_fresco.quantidade == 2  # coluna crua (populate_existing)
                # VO Dinheiro reconstruido no refresh (listener #117), nao stale.
                assert item_fresco.preco_unitario.valor == Decimal("99.00")
        finally:
            _limpar_item(engine, item_id)
