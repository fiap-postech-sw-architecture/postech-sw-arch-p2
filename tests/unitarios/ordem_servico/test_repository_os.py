from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

# Registra `clientes` e `veiculos` no metadata para as FKs da OS resolverem.
from src.cliente_veiculo.infraestrutura import mapping  # noqa: F401
from src.compartilhado.infraestrutura.database import metadata
from src.compartilhado.infraestrutura.encryption import EncryptionService
from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.mapping import (
    iniciar_mapeamentos,
    ordens_de_servico_table,
)
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)


class TestRepositoryOS:
    def test_init(self) -> None:
        session = MagicMock()
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo._session is session

    def test_obter_por_id(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        result = repo.obter_por_id(MagicMock())
        assert result is None

    def test_salvar(self) -> None:
        session = MagicMock()
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        entity = MagicMock()
        repo.salvar(entity)
        session.add.assert_called_once_with(entity)
        session.flush.assert_called_once()

    def test_contar(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 7
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.contar() == 7

    def test_contar_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

    def test_contar_por_status(self) -> None:
        session = MagicMock()
        session.execute.return_value.all.return_value = [
            ("recebida", 2),
            ("em_diagnostico", 3),
        ]
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        result = repo.contar_por_status()
        assert result == {"recebida": 2, "em_diagnostico": 3}

    def test_existe_ativa_para_cliente_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 1
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_para_cliente(MagicMock()) is True

    def test_existe_ativa_para_cliente_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_para_cliente(MagicMock()) is False

    def test_existe_ativa_para_veiculo(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_para_veiculo(MagicMock()) is False

    def test_existe_ativa_com_item_estoque(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_com_item_estoque(MagicMock()) is False

    def test_calcular_tempo_medio_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.calcular_tempo_medio_execucao() is None

    def test_calcular_tempo_medio_com_valor(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 120.5
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.calcular_tempo_medio_execucao() == 120.5

    def test_prioridade_e_encerradas_cobrem_todos_os_status(self) -> None:
        # Guard de drift (RF-023): um novo membro em StatusOrdem precisa
        # ser classificado — prioridade ativa (RN-018/RN-020) OU estado
        # encerrado (RN-019/RN-020). Sem classificacao, a listagem
        # degradaria em silencio (ordem ativa caindo no else_ 9, junto
        # das encerradas).
        from src.ordem_servico.infraestrutura.repository import (
            _ESTADOS_ENCERRADOS,
            _PRIORIDADE_STATUS,
        )

        classificados = _ESTADOS_ENCERRADOS | set(_PRIORIDADE_STATUS)
        assert classificados == {status.value for status in StatusOrdem}
        assert not (_ESTADOS_ENCERRADOS & set(_PRIORIDADE_STATUS))


@pytest.fixture
def engine_sqlite() -> Generator[Engine]:
    iniciar_mapeamentos()
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        metadata.drop_all(engine)
        engine.dispose()


def _inserir_ordem_crua(
    sessao: Session,
    *,
    status: StatusOrdem,
    criado_em: datetime,
    cliente_id: UUID,
    veiculo_id: UUID,
) -> UUID:
    ordem_id = uuid4()
    sessao.execute(
        ordens_de_servico_table.insert().values(
            id=ordem_id,
            cliente_id=cliente_id,
            veiculo_id=veiculo_id,
            status=status.value,
            orcamento_json=None,
            criado_em=criado_em,
            atualizado_em=criado_em,
        )
    )
    return ordem_id


class TestRepositoryOSIntegracao:
    def test_listar_paginado_mais_antiga_primeiro(self, engine_sqlite: Engine) -> None:
        # RF-023/RN-018: dentro do mesmo status, criado_em ASC (mais
        # antiga primeiro) — substitui a ordenacao criado_em DESC da fase 1.
        cliente_id = uuid4()
        veiculo_id = uuid4()
        base = datetime.now(UTC)

        with Session(engine_sqlite) as sessao_setup:
            for i in range(3):
                _inserir_ordem_crua(
                    sessao_setup,
                    status=StatusOrdem.RECEBIDA,
                    criado_em=base + timedelta(minutes=i),
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                )
            sessao_setup.commit()

        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)
            pagina1 = repo.listar(offset=0, limit=2)
            assert len(pagina1) == 2
            assert pagina1[0].criado_em < pagina1[1].criado_em

            pagina2 = repo.listar(offset=2, limit=2)
            assert len(pagina2) == 1

    def test_listar_prioriza_status_e_exclui_encerradas(
        self, engine_sqlite: Engine
    ) -> None:
        # RN-018 + RN-020: CASE de prioridade; COMPLEMENTAR no mesmo grupo
        # de AGUARDANDO_APROVACAO; encerradas fora do default (RN-019).
        cliente_id = uuid4()
        veiculo_id = uuid4()
        base = datetime.now(UTC)
        cenario = {
            "finalizada": (StatusOrdem.FINALIZADA, 1),
            "entregue": (StatusOrdem.ENTREGUE, 2),
            "cancelada": (StatusOrdem.CANCELADA, 3),
            "complementar": (StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR, 5),
            "aguardando": (StatusOrdem.AGUARDANDO_APROVACAO, 10),
            "diagnostico": (StatusOrdem.EM_DIAGNOSTICO, 20),
            "execucao": (StatusOrdem.EM_EXECUCAO, 30),
            "recebida": (StatusOrdem.RECEBIDA, 0),
        }

        with Session(engine_sqlite) as sessao_setup:
            ids = {
                nome: _inserir_ordem_crua(
                    sessao_setup,
                    status=status,
                    criado_em=base + timedelta(minutes=minutos),
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                )
                for nome, (status, minutos) in cenario.items()
            }
            sessao_setup.commit()

        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)

            listadas = [o.id for o in repo.listar(offset=0, limit=10)]
            assert listadas == [
                ids["execucao"],
                ids["complementar"],
                ids["aguardando"],
                ids["diagnostico"],
                ids["recebida"],
            ]

            completas = [
                o.id for o in repo.listar(offset=0, limit=10, incluir_encerradas=True)
            ]
            # Encerradas ao final (prioridade 9), criado_em ASC entre si.
            assert completas == [
                *listadas,
                ids["finalizada"],
                ids["entregue"],
                ids["cancelada"],
            ]

    def test_contar_com_e_sem_encerradas(self, engine_sqlite: Engine) -> None:
        cliente_id = uuid4()
        veiculo_id = uuid4()
        base = datetime.now(UTC)

        with Session(engine_sqlite) as sessao_setup:
            for status in (
                StatusOrdem.RECEBIDA,
                StatusOrdem.EM_EXECUCAO,
                StatusOrdem.FINALIZADA,
                StatusOrdem.ENTREGUE,
                StatusOrdem.CANCELADA,
            ):
                _inserir_ordem_crua(
                    sessao_setup,
                    status=status,
                    criado_em=base,
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                )
            sessao_setup.commit()

        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)
            assert repo.contar() == 5
            assert repo.contar(incluir_encerradas=False) == 2

    def test_obter_por_placa_e_documento_encontra_ordem(
        self, engine_sqlite: Engine
    ) -> None:
        from src.cliente_veiculo.infraestrutura.mapping import (
            clientes_table,
            veiculos_table,
        )

        enc = EncryptionService.instance()
        documento_raw = "12345678901"
        placa_raw = "ABC1D23"
        cliente_id = uuid4()
        veiculo_id = uuid4()
        doc_encrypted = enc.encrypt(documento_raw)
        doc_hash = enc.hash_deterministic(documento_raw)

        with Session(engine_sqlite) as sessao_setup:
            sessao_setup.execute(
                clientes_table.insert().values(
                    id=cliente_id,
                    nome="Cliente Teste",
                    documento=doc_encrypted,
                    documento_hash=doc_hash,
                    tipo_documento="cpf",
                    contato="(11) 99999-9999",
                    ativo=True,
                )
            )
            sessao_setup.execute(
                veiculos_table.insert().values(
                    id=veiculo_id,
                    placa=placa_raw,
                    marca="Fiat",
                    modelo="Uno",
                    ano=2020,
                    cliente_id=cliente_id,
                )
            )
            now = datetime.now(UTC)
            sessao_setup.execute(
                ordens_de_servico_table.insert().values(
                    id=uuid4(),
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                    status="recebida",
                    orcamento_json=None,
                    criado_em=now,
                    atualizado_em=now,
                )
            )
            sessao_setup.commit()

        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)
            resultados = repo.obter_por_placa_e_documento(
                placa=placa_raw, documento=documento_raw
            )
            assert len(resultados) == 1
            assert resultados[0].cliente_id == cliente_id
            assert resultados[0].veiculo_id == veiculo_id

    def test_obter_por_placa_e_documento_retorna_vazio_quando_nao_casa(
        self, engine_sqlite: Engine
    ) -> None:
        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)
            resultados = repo.obter_por_placa_e_documento(
                placa="XYZ9A99", documento="00000000000"
            )
            assert resultados == []
