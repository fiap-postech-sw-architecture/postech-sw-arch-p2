"""Seeds compartilhados da integracao: cliente + veiculo (+ OS) e usuarios.

A factory era reimplementada em 5 arquivos (concorrencia_lock,
notificacao_email, relay_smtp_falha, outbox_uow, repositories — issue #173).
CPF (brutils, valido) e placa (contador monotonico) sao UNICOS por chamada:
arquivos que commitam de verdade (threads, relay, TestClient) nao colidem com
residuo de um teste anterior cujo cleanup nao rodou, nem entre chamadas do
mesmo teste. O caller controla a transacao — a factory apenas cria e faz
``flush`` na session recebida (savepoint da fixture ``session`` OU session
propria com commit real).
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session, sessionmaker

    from src.autenticacao.dominio.papel import Papel
    from src.autenticacao.dominio.usuario import Usuario

# Senha padrao dos usuarios de teste (compartilhada pelos fixtures/logins).
SENHA_PADRAO = "senhaforte1234"

_contador_placa = itertools.count(1)


def placa_unica(prefixo: str = "ITG") -> str:
    """Placa unica no padrao antigo (3 letras + 4 digitos).

    O ``prefixo`` (3 letras) identifica o arquivo/cenario no banco em caso de
    residuo; o contador (0001-9999) garante unicidade dentro da sessao.
    """
    n = next(_contador_placa) % 10000
    return f"{prefixo}{n:04d}"


def cpf_unico() -> str:
    """CPF valido e unico por chamada (gerador do brutils)."""
    from brutils.cpf import generate as gerar_cpf

    return gerar_cpf()


def criar_cliente_com_veiculo(
    sessao: Session,
    *,
    nome: str = "Cliente Teste",
    contato: str = "11999990000",
    cpf: str | None = None,
    placa: str | None = None,
) -> Cliente:
    """Cria cliente (CPF unico por default) + 1 veiculo (placa unica) e flusha.

    Retorna o agregado; o veiculo fica em ``cliente.veiculos[0]``.
    """
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    cliente = Cliente(
        _nome=nome,
        _documento=CPF(numero=cpf or cpf_unico()),
        _contato=Contato(valor=contato),
    )
    ClienteSQLAlchemyRepository(session=sessao).salvar(cliente)
    cliente.adicionar_veiculo(
        placa=Placa(valor=placa or placa_unica()),
        marca="Fiat",
        modelo="Uno",
        ano=2020,
    )
    sessao.flush()
    return cliente


def criar_ordem_recebida(
    sessao: Session,
    *,
    cliente_id: UUID,
    veiculo_id: UUID,
    limpar_eventos: bool = True,
) -> OrdemDeServico:
    """Cria uma OS RECEBIDA para o par cliente/veiculo e flusha.

    ``limpar_eventos=True`` (default) descarta o evento de criacao — a maioria
    dos cenarios nao quer exercitar a outbox no seed.
    """
    ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
    if limpar_eventos:
        ordem.limpar_eventos()
    from src.ordem_servico.infraestrutura.repository import (
        OrdemDeServicoSQLAlchemyRepository,
    )

    OrdemDeServicoSQLAlchemyRepository(session=sessao).salvar(ordem)
    sessao.flush()
    return ordem


def criar_usuario(
    session_factory: sessionmaker[Session], *, email: str, papel: Papel
) -> Usuario:
    """Cria e COMMITA um usuario com ``SENHA_PADRAO`` (para login via API)."""
    from src.autenticacao.dominio.usuario import Usuario
    from src.autenticacao.infraestrutura.password_hasher import hash_senha
    from src.autenticacao.infraestrutura.repository import UsuarioSQLAlchemyRepository

    with session_factory() as sess:
        usuario = Usuario.criar(
            email=email, senha_hash=hash_senha(SENHA_PADRAO), papel=papel
        )
        UsuarioSQLAlchemyRepository(session=sess).salvar(usuario)
        sess.commit()
    return usuario
