"""Implementacao SQLAlchemy do repositorio de OrdemDeServico."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from sqlalchemy import case, extract, func, select

from src.cliente_veiculo.infraestrutura.mapping import (
    clientes_table,
    veiculos_table,
)
from src.compartilhado.infraestrutura.encryption import EncryptionService
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.mapping import (
    itens_da_ordem_table,
    ordens_de_servico_table,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

# Estados nos quais nao deve existir "ordem ativa" para contagens, existencia
# e outras projecoes de leitura. Frozenset + Final impedem mutacao acidental
# da allow-list global (lesson PR #61 Copilot Gap Analysis).
_ESTADOS_TERMINAIS: Final[frozenset[str]] = frozenset(
    {StatusOrdem.ENTREGUE.value, StatusOrdem.CANCELADA.value}
)
_ESTADOS_FINALIZADOS: Final[frozenset[str]] = frozenset(
    {StatusOrdem.ENTREGUE.value, StatusOrdem.FINALIZADA.value}
)
# Estados encerrados ficam fora da listagem padrao (RN-019/RN-020).
# Filtro de leitura: nenhum delete fisico, nenhuma coluna de soft-delete —
# o proprio status e o marcador.
_ESTADOS_ENCERRADOS: Final[frozenset[str]] = frozenset(
    {
        StatusOrdem.FINALIZADA.value,
        StatusOrdem.ENTREGUE.value,
        StatusOrdem.CANCELADA.value,
    }
)
# Prioridade de exibicao da listagem (RN-018; RN-020 agrupa a COMPLEMENTAR
# com AGUARDANDO_APROVACAO). Estados encerrados caem no else_ (9), ao final,
# quando a visao administrativa completa e solicitada.
_PRIORIDADE_STATUS: Final[dict[str, int]] = {
    StatusOrdem.EM_EXECUCAO.value: 0,
    StatusOrdem.AGUARDANDO_APROVACAO.value: 1,
    StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR.value: 1,
    StatusOrdem.EM_DIAGNOSTICO.value: 2,
    StatusOrdem.RECEBIDA.value: 3,
}
_PRIORIDADE_ENCERRADAS: Final[int] = 9
# Regex compatibility com cliente_veiculo: CPF/CNPJ sao armazenados
# apenas com digitos (ver `cliente_veiculo/dominio/cpf.py:_NAO_DIGITO`),
# e placa e normalizada para uppercase sem hifen (ver
# `cliente_veiculo/dominio/placa.py:__post_init__`). A consulta por
# placa+documento precisa aplicar a mesma normalizacao antes do
# lookup, caso contrario entradas mascaradas/lowercase nao casam.
_NAO_DIGITO: Final[re.Pattern[str]] = re.compile(r"\D")


class OrdemDeServicoSQLAlchemyRepository:
    """Implementacao SQLAlchemy de ``OrdemDeServicoRepository`` (Protocol de dominio).

    Encapsula consultas sobre ``ordens_de_servico``, ``itens_da_ordem``,
    e — para ``obter_por_placa_e_documento`` — joins com as tabelas
    ``clientes`` e ``veiculos`` do contexto Cliente+Veiculo (somente
    leitura, sem atravessar camadas de dominio daquele contexto).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def obter_por_id(
        self, ordem_id: UUID, *, com_lock: bool = False
    ) -> OrdemDeServico | None:
        """Retorna a ordem pelo id, ou ``None`` se nao existir.

        ``com_lock=True`` aplica ``SELECT ... FOR UPDATE`` para serializar
        as transicoes concorrentes da MESMA ordem (issue #82): sem o lock,
        N requisicoes simultaneas leem o estado stale, todas validam a
        transicao como legal e todas commitam -> N eventos/e-mails. Com o
        lock, a 2a transacao bloqueia ate a 1a commitar, re-le o estado
        pos-commit e a maquina de status rejeita a transicao agora ilegal
        (espelha o ``com_lock`` do repositorio de Estoque). ``com_lock=False``
        (default) preserva o caminho de LEITURA sem overhead de lock — os
        caminhos read-only (consulta de status, listagem, acompanhamento
        publico) NUNCA devem travar a linha.
        """
        if not com_lock:
            return self._session.get(OrdemDeServico, ordem_id)
        stmt = (
            select(OrdemDeServico)
            .where(ordens_de_servico_table.c.id == ordem_id)
            .with_for_update(nowait=False)
        )
        return self._session.scalars(stmt).one_or_none()

    def salvar(self, ordem: OrdemDeServico) -> None:
        """Persiste a ordem (insert ou update) e faz flush imediato."""
        self._session.add(ordem)
        self._session.flush()

    def listar(
        self,
        offset: int = 0,
        limit: int = 20,
        *,
        incluir_encerradas: bool = False,
    ) -> list[OrdemDeServico]:
        """Pagina ordens por prioridade de status + antiguidade (RF-023).

        Ordenacao SQL: ``CASE`` de prioridade no status (RN-018/RN-020),
        depois ``criado_em ASC`` (mais antiga primeiro) e ``id`` como
        desempate — paginacao deterministica mesmo quando duas ordens
        compartilham criado_em (PR #58 lesson). Por padrao, estados
        encerrados ficam fora (RN-019/RN-020); ``incluir_encerradas=True``
        devolve a visao completa, com encerradas ao final (prioridade 9).
        """
        prioridade = case(
            _PRIORIDADE_STATUS,
            value=ordens_de_servico_table.c.status,
            else_=_PRIORIDADE_ENCERRADAS,
        )
        stmt = (
            select(OrdemDeServico)
            .order_by(
                prioridade,
                ordens_de_servico_table.c.criado_em.asc(),
                ordens_de_servico_table.c.id,
            )
            .offset(offset)
            .limit(limit)
        )
        if not incluir_encerradas:
            stmt = stmt.where(
                ordens_de_servico_table.c.status.notin_(_ESTADOS_ENCERRADOS)
            )
        return list(self._session.scalars(stmt))

    def contar(self, *, incluir_encerradas: bool = True) -> int:
        """Total de ordens persistidas.

        ``incluir_encerradas=False`` restringe ao universo da listagem
        padrao (RN-019/RN-020), mantendo o ``total`` de paginacao
        consistente com ``listar``; o default preserva o total historico
        usado pelas metricas.
        """
        stmt = select(func.count()).select_from(ordens_de_servico_table)
        if not incluir_encerradas:
            stmt = stmt.where(
                ordens_de_servico_table.c.status.notin_(_ESTADOS_ENCERRADOS)
            )
        result = self._session.scalar(stmt)
        return result if result is not None else 0

    def contar_por_status(self) -> dict[str, int]:
        """Mapa ``status.value -> contagem`` para todas as ordens."""
        stmt = select(
            ordens_de_servico_table.c.status,
            func.count(),
        ).group_by(ordens_de_servico_table.c.status)
        rows = self._session.execute(stmt).all()
        return {str(status): int(count) for status, count in rows}

    def existe_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        """Indica se o cliente tem alguma ordem em estado nao terminal."""
        stmt = (
            select(func.count())
            .select_from(ordens_de_servico_table)
            .where(ordens_de_servico_table.c.cliente_id == cliente_id)
            .where(ordens_de_servico_table.c.status.notin_(_ESTADOS_TERMINAIS))
        )
        return (self._session.scalar(stmt) or 0) > 0

    def existe_ativa_para_veiculo(self, veiculo_id: UUID) -> bool:
        """Indica se o veiculo tem alguma ordem em estado nao terminal."""
        stmt = (
            select(func.count())
            .select_from(ordens_de_servico_table)
            .where(ordens_de_servico_table.c.veiculo_id == veiculo_id)
            .where(ordens_de_servico_table.c.status.notin_(_ESTADOS_TERMINAIS))
        )
        return (self._session.scalar(stmt) or 0) > 0

    def existe_ativa_com_item_estoque(self, item_estoque_id: UUID) -> bool:
        """Indica se o item de estoque esta referenciado por alguma ordem ativa."""
        stmt = (
            select(func.count())
            .select_from(
                ordens_de_servico_table.join(
                    itens_da_ordem_table,
                    ordens_de_servico_table.c.id == itens_da_ordem_table.c.ordem_id,
                )
            )
            .where(itens_da_ordem_table.c.item_estoque_id == item_estoque_id)
            .where(ordens_de_servico_table.c.status.notin_(_ESTADOS_TERMINAIS))
        )
        return (self._session.scalar(stmt) or 0) > 0

    def obter_por_placa_e_documento(
        self, placa: str, documento: str
    ) -> list[OrdemDeServico]:
        """Lista ordens cujo veiculo bate com ``placa`` E cliente com ``documento``.

        ``documento`` pode ser CPF ou CNPJ (com ou sem mascara); a
        entrada e normalizada para apenas digitos antes do hash, para
        casar com o formato persistido pelo contexto Cliente+Veiculo.
        ``placa`` e normalizada para uppercase sem hifen pelo mesmo
        motivo. A comparacao do documento usa
        ``EncryptionService.hash_deterministic`` para lookup por valor
        sem expor o documento em claro no banco.
        """
        enc = EncryptionService.instance()
        documento_normalizado = _NAO_DIGITO.sub("", documento)
        placa_normalizada = placa.upper().replace("-", "")
        doc_hash = enc.hash_deterministic(documento_normalizado)
        stmt = (
            select(OrdemDeServico)
            .join(
                clientes_table,
                ordens_de_servico_table.c.cliente_id == clientes_table.c.id,
            )
            .join(
                veiculos_table,
                ordens_de_servico_table.c.veiculo_id == veiculos_table.c.id,
            )
            .where(veiculos_table.c.placa == placa_normalizada)
            .where(clientes_table.c.documento_hash == doc_hash)
        )
        return list(self._session.scalars(stmt))

    def calcular_tempo_medio_execucao(self) -> float | None:
        """Tempo medio (minutos) entre criacao e atualizacao de ordens finalizadas.

        Retorna ``None`` se nao houver ordens em ``FINALIZADA``/``ENTREGUE``.
        Usa ``extract('epoch', ...)`` — dialeto Postgres; testes de
        integracao precisam de Postgres para exercitar este metodo.
        """
        diferenca = (
            extract(
                "epoch",
                ordens_de_servico_table.c.atualizado_em
                - ordens_de_servico_table.c.criado_em,
            )
            / 60.0
        )
        stmt = (
            select(func.avg(diferenca))
            .select_from(ordens_de_servico_table)
            .where(ordens_de_servico_table.c.status.in_(_ESTADOS_FINALIZADOS))
        )
        resultado = self._session.scalar(stmt)
        return float(resultado) if resultado is not None else None
