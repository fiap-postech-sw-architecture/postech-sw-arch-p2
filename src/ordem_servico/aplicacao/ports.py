"""Portas de saida (Protocol) que a aplicacao OrdemDeServico consome.

Cada Protocol e definido aqui (no contexto consumidor) e implementado
em ``infraestrutura/adapters.py`` do PROPRIO contexto consumidor — padrao
Anti-Corruption Layer: o adapter traduz o modelo do contexto vizinho para
os DTOs deste modulo, sem vazar agregados alheios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.compartilhado.dominio.dinheiro import Dinheiro


@dataclass(frozen=True, slots=True)
class ServicoOferecidoDTO:
    """DTO imutavel devolvido por ``CatalogoPort.obter_servico``.

    Carrega apenas os campos que a aplicacao OrdemDeServico precisa
    para validar e snapshotar precos no orcamento.
    """

    id: UUID
    nome: str
    preco: Dinheiro
    ativo: bool


@dataclass(frozen=True, slots=True)
class ItemEstoqueDTO:
    """DTO imutavel devolvido por ``EstoquePort.obter_item``.

    Snapshot do preco da peca no momento da consulta — usado por
    ``AdicionarItem`` para registrar o preco da peca consumida (em vez
    do preco do servico, que seria pra mao-de-obra).

    ``ativo`` permite que ``_montar_item`` rejeite peca desativada antes de
    entrar na OS (issue #120): sem isso, um item desativado (fora do catalogo
    ativo) podia ser adicionado e reservado, furando o invariante que o guard
    de ``DesativarItemEstoque`` protege. Default ``True`` para nao quebrar
    construcoes que so consultam preco/nome (o adapter real sempre popula o
    valor efetivo).
    """

    id: UUID
    nome: str
    preco_unitario: Dinheiro
    ativo: bool = True


@dataclass(frozen=True, slots=True)
class ClienteResumoDTO:
    """DTO imutavel para enriquecer projecoes de OS com o nome do cliente."""

    id: UUID
    nome: str


@dataclass(frozen=True, slots=True)
class ClienteContatoDTO:
    """DTO imutavel devolvido por ``ClientePort.obter_contato`` (RF-024).

    ``contato`` e o campo livre do cadastro (telefone, e-mail ou ambos);
    a extracao/validacao do e-mail e responsabilidade do consumidor
    (``aplicacao/notificacoes.py``), nao do contexto Cliente+Veiculo.
    """

    id: UUID
    # PII (LGPD): nome e contato (telefone/e-mail livre) fora do __repr__ — o
    # repr default aparece em tracebacks (code-review-checklist-extended §C).
    nome: str = field(repr=False)
    contato: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class VeiculoResumoDTO:
    """DTO imutavel para enriquecer projecoes de OS com a placa do veiculo."""

    id: UUID
    placa: str


class EstoquePort(Protocol):
    """Porta para reserva, liberacao e consulta de itens no contexto Estoque."""

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def reservar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Reserva ``quantidade`` unidades do item.

        Implementacoes devem levantar ``EstoqueInsuficienteException`` (ou
        equivalente) se a quantidade disponivel for menor que a solicitada.
        Nao e idempotente: chamadas repetidas reservam quantidades adicionais.
        """
        pass

    def liberar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Libera ``quantidade`` unidades previamente reservadas.

        Implementacoes devem rejeitar liberacoes que excedam a reserva
        ativa para o item.
        """
        pass

    def obter_item(self, item_estoque_id: UUID) -> ItemEstoqueDTO | None:
        """Retorna o DTO do item de estoque, ou ``None`` se nao existir.

        Usado por ``AdicionarItem`` quando a linha da OS representa uma peca
        consumida (item_estoque_id presente): o ``preco_unitario`` da
        ItemDaOrdem precisa vir do estoque, nao do servico.
        """
        pass

    def obter_itens_em_lote(
        self, item_estoque_ids: set[UUID]
    ) -> dict[UUID, ItemEstoqueDTO]:
        """Resolve um conjunto de itens em uma unica consulta.

        Devolve um dict ``id -> DTO`` apenas com itens existentes; ids
        inexistentes ficam de fora. ``item_estoque_ids`` vazio retorna
        dict vazio sem tocar a infraestrutura. Usado pela query
        ``EnriquecerOrdemDeServico`` para evitar N+1 quando uma OS tem
        varios itens.
        """
        pass


class CatalogoPort(Protocol):
    """Porta para consulta de servicos oferecidos no contexto Catalogo de Servicos."""

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def obter_servico(self, servico_id: UUID) -> ServicoOferecidoDTO | None:
        """Retorna o DTO do servico pelo id, ou ``None`` se nao existir."""
        pass

    def obter_servicos_em_lote(
        self, servico_ids: set[UUID]
    ) -> dict[UUID, ServicoOferecidoDTO]:
        """Resolve um conjunto de servicos em uma unica consulta.

        Devolve um dict ``id -> DTO`` apenas com servicos existentes; ids
        inexistentes ficam de fora. ``servico_ids`` vazio retorna dict
        vazio sem tocar a infraestrutura. Usado pela query
        ``EnriquecerOrdemDeServico`` para evitar N+1 quando uma OS tem
        varios itens.
        """
        pass


class ClientePort(Protocol):
    """Porta para validar cliente e seus veiculos no contexto Cliente+Veiculo."""

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def cliente_existe(self, cliente_id: UUID) -> bool:
        """Indica se o cliente existe e esta ativo no contexto Cliente+Veiculo."""
        pass

    def veiculo_pertence_ao_cliente(self, cliente_id: UUID, veiculo_id: UUID) -> bool:
        """Indica se o veiculo existe e pertence ao cliente informado."""
        pass

    def obter_clientes_em_lote(
        self, cliente_ids: set[UUID]
    ) -> dict[UUID, ClienteResumoDTO]:
        """Resolve um conjunto de clientes em uma unica consulta.

        Devolve um dict ``id -> DTO`` apenas com clientes existentes; ids
        inexistentes (ex.: cliente removido) ficam de fora. ``cliente_ids``
        vazio retorna dict vazio sem tocar a infraestrutura. Usado pela
        query ``EnriquecerOrdemDeServico`` para evitar N+1 quando uma
        listagem hidrata varias ordens de uma vez.
        """
        pass

    def obter_veiculos_em_lote(
        self, veiculo_ids: set[UUID]
    ) -> dict[UUID, VeiculoResumoDTO]:
        """Resolve um conjunto de veiculos em uma unica consulta.

        Mesmo contrato batch de ``obter_clientes_em_lote``: ``set`` vazio
        retorna dict vazio; ids inexistentes ficam de fora.
        """
        pass

    def obter_contato(self, cliente_id: UUID) -> ClienteContatoDTO | None:
        """Retorna nome + contato do cliente, ou ``None`` se nao existir.

        Usado pela notificacao de mudanca de status (RF-024) para resolver
        o destinatario do e-mail sem que este contexto importe o agregado
        ``Cliente`` do vizinho.
        """
        pass


class FalhaEnvioEmailException(Exception):  # noqa: N818 -- sufixo Exception e a convencao do repo (ADR-009)
    """Falha de transporte ao enviar e-mail pela ``EmailPort``.

    Levantada pelos adapters no lugar das excecoes do transporte concreto
    (ex.: ``OSError``/``smtplib.SMTPException`` no adapter SMTP), para que
    a aplicacao trate falha de envio sem conhecer o mecanismo de entrega.
    """


class EmailPort(Protocol):
    """Porta de envio de e-mail (RF-024 / ADR-018).

    Declarada no contexto consumidor (OrdemDeServico) e realizada na
    borda por ``infraestrutura/email_adapter.py`` (SMTP generico).
    Implementacoes DEVEM traduzir falhas de transporte em
    ``FalhaEnvioEmailException`` e propaga-la: a politica de tratamento
    (log + repasse ao relay para retry/DLQ) e do handler de notificacao,
    nao da porta.
    """

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        """Envia um e-mail texto-plano para ``destinatario``.

        Raises:
            FalhaEnvioEmailException: falha de transporte no envio.
        """
        pass
