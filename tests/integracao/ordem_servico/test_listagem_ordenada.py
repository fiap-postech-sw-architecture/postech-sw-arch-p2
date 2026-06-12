"""Integracao: listagem ordenada por prioridade de status (RF-023).

Exercita ``OrdemDeServicoSQLAlchemyRepository.listar``/``contar`` contra
Postgres real, cobrindo:

- RN-018: prioridade EM_EXECUCAO > AGUARDANDO_APROVACAO > EM_DIAGNOSTICO >
  RECEBIDA; dentro do grupo, mais antiga primeiro (``criado_em ASC``) com
  desempate deterministico por ``id``;
- RN-019: ``FINALIZADA``/``ENTREGUE`` fora da listagem padrao (filtro de
  leitura, sem soft-delete);
- RN-020: ``AGUARDANDO_APROVACAO_COMPLEMENTAR`` intercala com
  ``AGUARDANDO_APROVACAO`` no mesmo grupo; ``CANCELADA`` e encerrada;
- visao administrativa completa via ``incluir_encerradas=True`` (encerradas
  ao final da ordenacao).

As linhas sao inseridas direto na tabela (bypass deliberado do agregado)
para fixar ``status``/``criado_em`` sem percorrer a maquina de transicoes —
o alvo aqui e exclusivamente o read-side.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.mapping import ordens_de_servico_table
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integracao

_BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _criar_cliente_com_veiculo(session: Session) -> tuple[UUID, UUID]:
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    cliente = Cliente(
        _nome="Cliente Listagem",
        _documento=CPF(numero="21249722519"),
        _contato="11999990000",
    )
    ClienteSQLAlchemyRepository(session=session).salvar(cliente)
    cliente.adicionar_veiculo(
        placa=Placa(valor="LST1234"), marca="Fiat", modelo="Uno", ano=2020
    )
    session.flush()
    return cliente.id, cliente.veiculos[0].id


def _inserir_ordem(
    session: Session,
    *,
    cliente_id: UUID,
    veiculo_id: UUID,
    status: StatusOrdem,
    criado_em: datetime,
    ordem_id: UUID | None = None,
) -> UUID:
    ordem_id = ordem_id or uuid4()
    session.execute(
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


@pytest.fixture
def cenario_oito_status(session: Session) -> dict[str, UUID]:
    """Uma OS em cada um dos 8 status, mais duplicatas para antiguidade.

    Os offsets de ``criado_em`` (minutos sobre ``_BASE``) sao escolhidos
    para que a ordenacao por prioridade contradiga a ordenacao puramente
    cronologica: as encerradas sao as mais antigas (0/5/10) e, no grupo de
    aprovacao, ha uma AGUARDANDO_APROVACAO mais velha (35) e outra mais
    nova (50) que a COMPLEMENTAR (40) — provando a intercalacao do RN-020.
    """
    cliente_id, veiculo_id = _criar_cliente_com_veiculo(session)

    def inserir(status: StatusOrdem, minutos: int) -> UUID:
        return _inserir_ordem(
            session,
            cliente_id=cliente_id,
            veiculo_id=veiculo_id,
            status=status,
            criado_em=_BASE + timedelta(minutes=minutos),
        )

    ids = {
        "cancelada": inserir(StatusOrdem.CANCELADA, 0),
        "entregue": inserir(StatusOrdem.ENTREGUE, 5),
        "finalizada": inserir(StatusOrdem.FINALIZADA, 10),
        "execucao_velha": inserir(StatusOrdem.EM_EXECUCAO, 20),
        "execucao_nova": inserir(StatusOrdem.EM_EXECUCAO, 30),
        "aguardando_velha": inserir(StatusOrdem.AGUARDANDO_APROVACAO, 35),
        "complementar": inserir(StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR, 40),
        "aguardando_nova": inserir(StatusOrdem.AGUARDANDO_APROVACAO, 50),
        "diagnostico": inserir(StatusOrdem.EM_DIAGNOSTICO, 60),
        "recebida": inserir(StatusOrdem.RECEBIDA, 70),
    }
    session.flush()
    return ids


_ORDEM_ATIVAS = (
    "execucao_velha",
    "execucao_nova",
    "aguardando_velha",
    "complementar",
    "aguardando_nova",
    "diagnostico",
    "recebida",
)
_ORDEM_ENCERRADAS = ("cancelada", "entregue", "finalizada")


class TestListagemOrdenadaPorPrioridade:
    def test_default_ordena_por_prioridade_e_antiguidade(
        self, session: Session, cenario_oito_status: dict[str, UUID]
    ) -> None:
        """RN-018 + RN-020: prioridade de status, criado_em ASC no grupo.

        A COMPLEMENTAR (criado_em entre as duas AGUARDANDO_APROVACAO)
        precisa aparecer intercalada — mesmo grupo de prioridade.
        """
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        resultado = repo.listar(offset=0, limit=50)

        esperado = [cenario_oito_status[nome] for nome in _ORDEM_ATIVAS]
        assert [ordem.id for ordem in resultado] == esperado

    def test_default_exclui_encerradas(
        self, session: Session, cenario_oito_status: dict[str, UUID]
    ) -> None:
        """RN-019 + RN-020: FINALIZADA/ENTREGUE/CANCELADA fora do default."""
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        ids_listados = {ordem.id for ordem in repo.listar(offset=0, limit=50)}

        for nome in _ORDEM_ENCERRADAS:
            assert cenario_oito_status[nome] not in ids_listados

    def test_incluir_encerradas_ao_final(
        self, session: Session, cenario_oito_status: dict[str, UUID]
    ) -> None:
        """Visao administrativa completa: encerradas ao final da ordenacao.

        As encerradas sao as linhas mais antigas do cenario; ainda assim
        devem aparecer depois de todas as ativas (prioridade domina o
        criado_em), ordenadas entre si por criado_em ASC.
        """
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        resultado = repo.listar(offset=0, limit=50, incluir_encerradas=True)

        esperado = [
            cenario_oito_status[nome] for nome in (*_ORDEM_ATIVAS, *_ORDEM_ENCERRADAS)
        ]
        assert [ordem.id for ordem in resultado] == esperado

    def test_paginacao_fatiando_a_mesma_ordenacao(
        self, session: Session, cenario_oito_status: dict[str, UUID]
    ) -> None:
        """RF-023: paginacao continua deterministica sob a nova ordenacao."""
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        pagina = repo.listar(offset=2, limit=3)

        esperado = [cenario_oito_status[nome] for nome in _ORDEM_ATIVAS[2:5]]
        assert [ordem.id for ordem in pagina] == esperado

    def test_desempate_deterministico_por_id(self, session: Session) -> None:
        """RN-018: mesmo status e mesmo criado_em -> ordena por id ASC."""
        cliente_id, veiculo_id = _criar_cliente_com_veiculo(session)
        ids = [
            _inserir_ordem(
                session,
                cliente_id=cliente_id,
                veiculo_id=veiculo_id,
                status=StatusOrdem.RECEBIDA,
                criado_em=_BASE,
            )
            for _ in range(3)
        ]
        session.flush()

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        resultado = [ordem.id for ordem in repo.listar(offset=0, limit=10)]

        assert resultado == sorted(ids)

    def test_contar_acompanha_o_filtro_da_listagem(
        self, session: Session, cenario_oito_status: dict[str, UUID]
    ) -> None:
        """Total para paginacao reflete o mesmo universo filtrado."""
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        assert repo.contar() == 10
        assert repo.contar(incluir_encerradas=False) == 7
