from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.dominio.usuario import Usuario
from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.documento_anonimizado import DocumentoAnonimizado
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import EstoqueInsuficienteException
from src.estoque.dominio.item_estoque import ItemEstoque
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem
from tests.integracao.seed_helpers import (
    criar_cliente_com_veiculo,
    criar_ordem_recebida,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integracao


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _criar_cliente_cpf(
    session: Session,
    nome: str = "Maria Silva",
    cpf_numero: str = "21249722519",
    contato: str = "11999990000",
) -> Cliente:
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    repo = ClienteSQLAlchemyRepository(session=session)
    cliente = Cliente(
        _nome=nome,
        _documento=CPF(numero=cpf_numero),
        _contato=Contato(valor=contato),
    )
    repo.salvar(cliente)
    return cliente


def _criar_cliente_cnpj(
    session: Session,
    nome: str = "Oficina Ltda",
    cnpj_numero: str = "11222333000181",
    contato: str = "1133330000",
) -> Cliente:
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    repo = ClienteSQLAlchemyRepository(session=session)
    cliente = Cliente(
        _nome=nome,
        _documento=CNPJ(numero=cnpj_numero),
        _contato=Contato(valor=contato),
    )
    repo.salvar(cliente)
    return cliente


def _criar_servico(
    session: Session,
    nome: str = "Troca de Oleo",
    descricao: str = "Troca de oleo do motor",
    preco: Dinheiro | None = None,
) -> ServicoOferecido:
    from src.catalogo_servicos.infraestrutura.repository import (
        ServicoOferecidoSQLAlchemyRepository,
    )

    repo = ServicoOferecidoSQLAlchemyRepository(session=session)
    servico = ServicoOferecido(
        _nome=nome,
        _descricao=descricao,
        _preco=preco or Dinheiro(valor=Decimal("150.00")),
    )
    repo.salvar(servico)
    return servico


def _criar_item_estoque(
    session: Session,
    nome: str = "Filtro de Oleo",
    descricao: str = "Filtro de oleo automotivo",
    quantidade: int = 10,
    preco: Dinheiro | None = None,
) -> ItemEstoque:
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    repo = ItemEstoqueSQLAlchemyRepository(session=session)
    item = ItemEstoque(
        _nome=nome,
        _descricao=descricao,
        _quantidade=quantidade,
        _preco_unitario=preco or Dinheiro(valor=Decimal("35.00")),
    )
    repo.salvar(item)
    return item


def _criar_ordem_completa(
    session: Session,
) -> tuple[OrdemDeServico, Cliente, ServicoOferecido]:
    """Cria uma ordem de servico com cliente, veiculo e um servico no catalogo.

    Seed cliente+veiculo+OS via factory compartilhada (CPF/placa unicos por
    chamada); ``limpar_eventos=False`` preserva o comportamento anterior (os
    eventos ficam no agregado; nada aqui os consome).
    """
    cliente = criar_cliente_com_veiculo(session, nome="Maria Silva")
    servico = _criar_servico(session)
    ordem = criar_ordem_recebida(
        session,
        cliente_id=cliente.id,
        veiculo_id=cliente.veiculos[0].id,
        limpar_eventos=False,
    )
    return ordem, cliente, servico


# ===========================================================================
# 1. Autenticacao
# ===========================================================================


class TestUsuarioRepository:
    def test_salvar_e_obter_por_id(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.repository import (
            UsuarioSQLAlchemyRepository,
        )

        repo = UsuarioSQLAlchemyRepository(session=session)
        usuario = Usuario.criar(
            email="admin@pytstop.com",
            senha_hash="hashed_password_123",
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)

        resultado = repo.obter_por_id(usuario.id)

        assert resultado is not None
        assert resultado.email == "admin@pytstop.com"
        assert resultado.senha_hash == "hashed_password_123"
        assert resultado.papel == Papel.ADMIN

    def test_obter_por_email(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.repository import (
            UsuarioSQLAlchemyRepository,
        )

        repo = UsuarioSQLAlchemyRepository(session=session)
        usuario = Usuario.criar(
            email="mecanico@pytstop.com",
            senha_hash="hashed_password_456",
            papel=Papel.MECANICO,
        )
        repo.salvar(usuario)

        resultado = repo.obter_por_email("mecanico@pytstop.com")

        assert resultado is not None
        assert resultado.id == usuario.id
        assert resultado.papel == Papel.MECANICO

    def test_obter_por_email_inexistente(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.repository import (
            UsuarioSQLAlchemyRepository,
        )

        repo = UsuarioSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_email("naoexiste@pytstop.com")

        assert resultado is None

    def test_email_existe(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.repository import (
            UsuarioSQLAlchemyRepository,
        )

        repo = UsuarioSQLAlchemyRepository(session=session)
        usuario = Usuario.criar(
            email="check@pytstop.com",
            senha_hash="hashed_password_789",
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)

        assert repo.email_existe("check@pytstop.com") is True
        assert repo.email_existe("outro@pytstop.com") is False

    def test_email_unico_constraint(self, session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        from src.autenticacao.infraestrutura.repository import (
            UsuarioSQLAlchemyRepository,
        )

        repo = UsuarioSQLAlchemyRepository(session=session)
        usuario1 = Usuario.criar(
            email="duplicado@pytstop.com",
            senha_hash="hash_a",
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario1)

        usuario2 = Usuario.criar(
            email="duplicado@pytstop.com",
            senha_hash="hash_b",
            papel=Papel.ADMIN,
        )
        with pytest.raises(IntegrityError):
            repo.salvar(usuario2)
        # IntegrityError rolls back the SAVEPOINT; recover session state.
        session.rollback()

    def test_salvar_com_papel_atendente(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.repository import (
            UsuarioSQLAlchemyRepository,
        )

        repo = UsuarioSQLAlchemyRepository(session=session)
        usuario = Usuario.criar(
            email="atendente@pytstop.com",
            senha_hash="hashed_password_atd",
            papel=Papel.ATENDENTE,
        )
        repo.salvar(usuario)

        resultado = repo.obter_por_id(usuario.id)
        assert resultado is not None
        assert resultado.papel == Papel.ATENDENTE

    def test_obter_por_id_inexistente(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.repository import (
            UsuarioSQLAlchemyRepository,
        )

        repo = UsuarioSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_id(uuid4())

        assert resultado is None


class TestTokenRevogadoRepository:
    def test_revogar_e_verificar(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.token_revogado_repository import (
            TokenRevogadoSQLAlchemyRepository,
        )

        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        jti = "token-jti-abc-123"

        repo.revogar(jti)

        assert repo.esta_revogado(jti) is True

    def test_token_nao_revogado(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.token_revogado_repository import (
            TokenRevogadoSQLAlchemyRepository,
        )

        repo = TokenRevogadoSQLAlchemyRepository(session=session)

        assert repo.esta_revogado("jti-que-nao-existe") is False

    def test_revogar_multiplos_tokens(self, session: Session) -> None:
        from src.autenticacao.infraestrutura.token_revogado_repository import (
            TokenRevogadoSQLAlchemyRepository,
        )

        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        jti_1 = "token-jti-multi-1"
        jti_2 = "token-jti-multi-2"
        jti_3 = "token-jti-multi-3"

        repo.revogar(jti_1)
        repo.revogar(jti_2)

        assert repo.esta_revogado(jti_1) is True
        assert repo.esta_revogado(jti_2) is True
        assert repo.esta_revogado(jti_3) is False


# ===========================================================================
# 2. Cliente + Veiculo
# ===========================================================================


class TestClienteRepository:
    def test_salvar_e_obter_com_cpf(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)

        resultado = repo.obter_por_id(cliente.id)

        assert resultado is not None
        assert resultado.nome == "Maria Silva"
        assert isinstance(resultado.documento, CPF)
        assert resultado.documento.numero == "21249722519"
        assert resultado.contato == Contato(valor="11999990000")
        assert resultado.ativo is True

    def test_salvar_e_obter_com_cnpj(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cnpj(session)

        resultado = repo.obter_por_id(cliente.id)

        assert resultado is not None
        assert resultado.nome == "Oficina Ltda"
        assert isinstance(resultado.documento, CNPJ)
        assert resultado.documento.numero == "11222333000181"

    def test_obter_por_documento_cpf(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)

        resultado = repo.obter_por_documento(CPF(numero="21249722519"))

        assert resultado is not None
        assert resultado.id == cliente.id

    def test_obter_por_documento_inexistente(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_documento(CPF(numero="52998224725"))

        assert resultado is None

    def test_documento_unico_constraint(self, session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        _criar_cliente_cpf(session, cpf_numero="21249722519")

        duplicado = Cliente(
            _nome="Outro Nome",
            _documento=CPF(numero="21249722519"),
            _contato=Contato(valor="11888880000"),
        )
        with pytest.raises(IntegrityError):
            repo.salvar(duplicado)
        session.rollback()

    def test_adicionar_veiculo(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        placa = Placa(valor="ABC1D23")
        cliente.adicionar_veiculo(
            placa=placa,
            marca="Fiat",
            modelo="Uno",
            ano=2020,
        )
        session.flush()

        resultado = repo.obter_por_id(cliente.id)

        assert resultado is not None
        assert len(resultado.veiculos) == 1
        veiculo = resultado.veiculos[0]
        assert veiculo.placa == placa
        assert veiculo.marca == "Fiat"
        assert veiculo.modelo == "Uno"
        assert veiculo.ano == 2020

    def test_adicionar_multiplos_veiculos(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        cliente.adicionar_veiculo(
            placa=Placa(valor="AAA1111"),
            marca="Fiat",
            modelo="Uno",
            ano=2020,
        )
        cliente.adicionar_veiculo(
            placa=Placa(valor="BBB2222"),
            marca="VW",
            modelo="Gol",
            ano=2019,
        )
        session.flush()

        resultado = repo.obter_por_id(cliente.id)
        assert resultado is not None
        assert len(resultado.veiculos) == 2

    def test_listar_veiculos_do_cliente(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        cliente.adicionar_veiculo(
            placa=Placa(valor="XYZ9999"),
            marca="Honda",
            modelo="Civic",
            ano=2022,
        )
        cliente.adicionar_veiculo(
            placa=Placa(valor="DEF5678"),
            marca="Toyota",
            modelo="Corolla",
            ano=2021,
        )
        session.flush()

        resultado = repo.obter_por_id(cliente.id)
        assert resultado is not None
        placas = {v.placa.valor for v in resultado.veiculos}
        assert placas == {"XYZ9999", "DEF5678"}

    def test_atualizar_cliente(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        cliente.atualizar(nome="Maria Souza", contato=Contato(valor="11888881111"))
        session.flush()

        resultado = repo.obter_por_id(cliente.id)

        assert resultado is not None
        assert resultado.nome == "Maria Souza"
        assert resultado.contato == Contato(valor="11888881111")

    def test_desativar_cliente(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        assert cliente.ativo is True

        cliente.desativar()
        session.flush()

        resultado = repo.obter_por_id(cliente.id)
        assert resultado is not None
        assert resultado.ativo is False

    def test_anonimizar_cnpj_e_recarregar_retorna_documento_anonimizado(
        self, session: Session
    ) -> None:
        # Caso de aceite do issue #79: cliente cujo documento original era
        # CNPJ deve voltar do DB como DocumentoAnonimizado, e nao mais como
        # um CPF reconstruido via __new__ (que escondia o tipo original).
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cnpj(session)
        cliente_id = cliente.id
        repo.anonimizar_dados(cliente_id)
        session.expire_all()

        resultado = repo.obter_por_id(cliente_id)
        assert resultado is not None
        assert isinstance(resultado.documento, DocumentoAnonimizado)
        assert not isinstance(resultado.documento, CNPJ)
        assert not isinstance(resultado.documento, CPF)
        assert resultado.documento.cliente_id == cliente_id
        assert resultado.ativo is False

    def test_anonimizar_dois_clientes_preserva_unique_hash(
        self, session: Session
    ) -> None:
        # Apos anonimizacao, ambos viram DocumentoAnonimizado com cliente_id
        # diferente — o tombstone "ANONIMIZADO:{cliente_id}" precisa
        # permanecer unico mesmo se o ORM marcar dirty na proxima flush.
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente_a = _criar_cliente_cpf(session, cpf_numero="21249722519")
        cliente_b = _criar_cliente_cnpj(session, cnpj_numero="11222333000181")
        repo.anonimizar_dados(cliente_a.id)
        repo.anonimizar_dados(cliente_b.id)
        session.flush()
        session.expire_all()

        a = repo.obter_por_id(cliente_a.id)
        b = repo.obter_por_id(cliente_b.id)
        assert a is not None
        assert b is not None
        assert isinstance(a.documento, DocumentoAnonimizado)
        assert isinstance(b.documento, DocumentoAnonimizado)
        assert a.documento != b.documento

    def test_anonimizar_cascateia_para_veiculos_neutraliza_placa(
        self, session: Session
    ) -> None:
        """#72: a anonimizacao neutraliza a placa (PII) dos veiculos do cliente e
        preserva a linha/FK (historico de OS por veiculo_id intacto)."""
        from src.cliente_veiculo.dominio.placa import Placa
        from src.cliente_veiculo.dominio.placa_anonimizada import PlacaAnonimizada
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session, cpf_numero="93214407473")
        cliente.adicionar_veiculo(
            placa=Placa(valor="ABC1234"), marca="Fiat", modelo="Uno", ano=2020
        )
        repo.salvar(cliente)
        veiculo_id = cliente.veiculos[0].id

        repo.anonimizar_dados(cliente.id)
        session.expire_all()

        resultado = repo.obter_por_id(cliente.id)
        assert resultado is not None
        veiculo = resultado.veiculos[0]
        # Placa (PII) neutralizada -> PlacaAnonimizada, sem expor a placa real.
        assert isinstance(veiculo.placa, PlacaAnonimizada)
        assert veiculo.placa.valor == "ANONIMIZADO"
        assert veiculo.marca == "ANONIMIZADO"
        assert veiculo.modelo == "ANONIMIZADO"
        # Linha preservada (id intacto) -> FK ordens_de_servico.veiculo_id valida.
        assert veiculo.id == veiculo_id

    def test_anonimizar_dois_veiculos_preserva_unique_placa(
        self, session: Session
    ) -> None:
        """#72: o tombstone por-veiculo (ANONIMIZADO:{id}) mantem a UNIQUE da
        placa quando dois veiculos (de clientes distintos) sao anonimizados."""
        from src.cliente_veiculo.dominio.placa import Placa
        from src.cliente_veiculo.dominio.placa_anonimizada import PlacaAnonimizada
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente_a = _criar_cliente_cpf(session, cpf_numero="21249722519")
        cliente_a.adicionar_veiculo(
            placa=Placa(valor="AAA1111"), marca="Fiat", modelo="Uno", ano=2020
        )
        repo.salvar(cliente_a)
        cliente_b = _criar_cliente_cnpj(session, cnpj_numero="11222333000181")
        cliente_b.adicionar_veiculo(
            placa=Placa(valor="BBB2222"), marca="VW", modelo="Gol", ano=2021
        )
        repo.salvar(cliente_b)

        repo.anonimizar_dados(cliente_a.id)
        repo.anonimizar_dados(cliente_b.id)
        session.flush()  # tombstones distintos -> nao viola a UNIQUE da placa
        session.expire_all()

        a = repo.obter_por_id(cliente_a.id)
        b = repo.obter_por_id(cliente_b.id)
        assert a is not None
        assert b is not None
        assert isinstance(a.veiculos[0].placa, PlacaAnonimizada)
        assert isinstance(b.veiculos[0].placa, PlacaAnonimizada)
        assert a.veiculos[0].placa != b.veiculos[0].placa

    def test_projecao_de_os_mascara_placa_anonimizada(self, session: Session) -> None:
        """#72: a projecao de OS (``obter_veiculos_em_lote``) NAO vaza o tombstone
        bruto -> devolve o sentinela limpo ``"ANONIMIZADO"``, igual ao agregado."""
        from src.cliente_veiculo.dominio.placa import Placa
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )
        from src.ordem_servico.infraestrutura.adapters import (
            ClienteSQLAlchemyAdapter,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session, cpf_numero="93214407473")
        cliente.adicionar_veiculo(
            placa=Placa(valor="XYZ9876"), marca="Fiat", modelo="Uno", ano=2020
        )
        repo.salvar(cliente)
        veiculo_id = cliente.veiculos[0].id

        repo.anonimizar_dados(cliente.id)
        session.expire_all()

        adapter = ClienteSQLAlchemyAdapter(session=session)
        veiculos = adapter.obter_veiculos_em_lote({veiculo_id})
        # Sentinela limpo, sem o sufixo ``:{veiculo_id}`` do tombstone bruto.
        assert veiculos[veiculo_id].placa == "ANONIMIZADO"

    def test_listar_com_paginacao(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        _criar_cliente_cpf(session, nome="Cliente A", cpf_numero="21249722519")
        _criar_cliente_cpf(session, nome="Cliente B", cpf_numero="52998224725")
        _criar_cliente_cpf(session, nome="Cliente C", cpf_numero="11144477735")

        pagina_1 = repo.listar(offset=0, limit=2)
        pagina_2 = repo.listar(offset=2, limit=2)

        assert len(pagina_1) == 2
        assert len(pagina_2) == 1

    def test_contar(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

        _criar_cliente_cpf(session)
        assert repo.contar() == 1

    def test_placa_existe(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        placa = Placa(valor="PLK8899")
        cliente.adicionar_veiculo(
            placa=placa,
            marca="Ford",
            modelo="Ka",
            ano=2021,
        )
        session.flush()

        assert repo.placa_existe(Placa(valor="PLK8899")) is True
        assert repo.placa_existe(Placa(valor="ZZZ0000")) is False

    def test_placa_existe_excluindo_cliente(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        placa = Placa(valor="EXC1234")
        cliente.adicionar_veiculo(
            placa=placa,
            marca="Chevrolet",
            modelo="Onix",
            ano=2023,
        )
        session.flush()

        assert (
            repo.placa_existe(
                Placa(valor="EXC1234"),
                excluir_cliente_id=cliente.id,
            )
            is False
        )
        assert repo.placa_existe(Placa(valor="EXC1234")) is True

    def test_obter_por_id_inexistente(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_id(uuid4())

        assert resultado is None

    def test_remover_veiculo(self, session: Session) -> None:
        from src.cliente_veiculo.infraestrutura.repository import (
            ClienteSQLAlchemyRepository,
        )

        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = _criar_cliente_cpf(session)
        placa = Placa(valor="REM4567")
        veiculo = cliente.adicionar_veiculo(
            placa=placa,
            marca="Fiat",
            modelo="Argo",
            ano=2022,
        )
        session.flush()

        cliente.remover_veiculo(veiculo.id)
        session.flush()

        resultado = repo.obter_por_id(cliente.id)
        assert resultado is not None
        assert len(resultado.veiculos) == 0


# ===========================================================================
# 3. Catalogo de Servicos
# ===========================================================================


class TestServicoOferecidoRepository:
    def test_salvar_e_obter(self, session: Session) -> None:
        from src.catalogo_servicos.infraestrutura.repository import (
            ServicoOferecidoSQLAlchemyRepository,
        )

        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        servico = _criar_servico(session)

        resultado = repo.obter_por_id(servico.id)

        assert resultado is not None
        assert resultado.nome == "Troca de Oleo"
        assert resultado.descricao == "Troca de oleo do motor"
        assert resultado.preco == Dinheiro(valor=Decimal("150.00"))
        assert resultado.ativo is True

    def test_listar_com_paginacao(self, session: Session) -> None:
        from src.catalogo_servicos.infraestrutura.repository import (
            ServicoOferecidoSQLAlchemyRepository,
        )

        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        _criar_servico(session, nome="Servico A", descricao="Descricao A")
        _criar_servico(session, nome="Servico B", descricao="Descricao B")
        _criar_servico(session, nome="Servico C", descricao="Descricao C")

        pagina_1 = repo.listar(offset=0, limit=2)
        pagina_2 = repo.listar(offset=2, limit=2)

        assert len(pagina_1) == 2
        assert len(pagina_2) == 1

    def test_contar(self, session: Session) -> None:
        from src.catalogo_servicos.infraestrutura.repository import (
            ServicoOferecidoSQLAlchemyRepository,
        )

        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

        _criar_servico(session)
        assert repo.contar() == 1

    def test_atualizar_preco(self, session: Session) -> None:
        from src.catalogo_servicos.infraestrutura.repository import (
            ServicoOferecidoSQLAlchemyRepository,
        )

        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        servico = _criar_servico(session)
        novo_preco = Dinheiro(valor=Decimal("200.00"))

        servico.atualizar(
            nome="Troca de Oleo Premium",
            descricao="Troca de oleo sintetico",
            preco=novo_preco,
        )
        session.flush()

        resultado = repo.obter_por_id(servico.id)
        assert resultado is not None
        assert resultado.nome == "Troca de Oleo Premium"
        assert resultado.descricao == "Troca de oleo sintetico"
        assert resultado.preco == novo_preco

    def test_desativar_servico(self, session: Session) -> None:
        from src.catalogo_servicos.infraestrutura.repository import (
            ServicoOferecidoSQLAlchemyRepository,
        )

        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        servico = _criar_servico(session)
        assert servico.ativo is True

        servico.desativar()
        session.flush()

        resultado = repo.obter_por_id(servico.id)
        assert resultado is not None
        assert resultado.ativo is False

    def test_obter_por_id_inexistente(self, session: Session) -> None:
        from src.catalogo_servicos.infraestrutura.repository import (
            ServicoOferecidoSQLAlchemyRepository,
        )

        repo = ServicoOferecidoSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_id(uuid4())

        assert resultado is None


# ===========================================================================
# 4. Estoque
# ===========================================================================


class TestItemEstoqueRepository:
    def test_salvar_e_obter(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        item = _criar_item_estoque(session)

        resultado = repo.obter_por_id(item.id)

        assert resultado is not None
        assert resultado.nome == "Filtro de Oleo"
        assert resultado.descricao == "Filtro de oleo automotivo"
        assert resultado.quantidade == 10
        assert resultado.preco_unitario == Dinheiro(valor=Decimal("35.00"))
        assert resultado.ativo is True

    def test_listar_com_paginacao(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        _criar_item_estoque(session, nome="Item A")
        _criar_item_estoque(session, nome="Item B")
        _criar_item_estoque(session, nome="Item C")

        pagina_1 = repo.listar(offset=0, limit=2)
        pagina_2 = repo.listar(offset=2, limit=2)

        assert len(pagina_1) == 2
        assert len(pagina_2) == 1

    def test_contar(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

        _criar_item_estoque(session)
        assert repo.contar() == 1

    def test_reservar_quantidade(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        item = _criar_item_estoque(session, quantidade=10)

        item.reservar(3)
        session.flush()

        resultado = repo.obter_por_id(item.id)
        assert resultado is not None
        assert resultado.quantidade == 7

    def test_liberar_quantidade(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        item = _criar_item_estoque(session, quantidade=5)

        item.liberar(3)
        session.flush()

        resultado = repo.obter_por_id(item.id)
        assert resultado is not None
        assert resultado.quantidade == 8

    def test_reservar_estoque_insuficiente(self, session: Session) -> None:
        item = _criar_item_estoque(session, quantidade=2)

        with pytest.raises(EstoqueInsuficienteException):
            item.reservar(5)

    def test_reservar_ate_zero(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        item = _criar_item_estoque(session, quantidade=3)

        item.reservar(3)
        session.flush()

        resultado = repo.obter_por_id(item.id)
        assert resultado is not None
        assert resultado.quantidade == 0

    def test_ajustar_quantidade(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        item = _criar_item_estoque(session, quantidade=10)

        item.ajustar_quantidade(25)
        session.flush()

        resultado = repo.obter_por_id(item.id)
        assert resultado is not None
        assert resultado.quantidade == 25

    def test_ajustar_quantidade_negativa_erro(self, session: Session) -> None:
        item = _criar_item_estoque(session, quantidade=5)

        with pytest.raises(ValueError, match="negativa"):
            item.ajustar_quantidade(-1)

    def test_atualizar_item(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        item = _criar_item_estoque(session)
        novo_preco = Dinheiro(valor=Decimal("50.00"))

        item.atualizar(
            nome="Filtro Premium",
            descricao="Filtro de alta performance",
            preco_unitario=novo_preco,
        )
        session.flush()

        resultado = repo.obter_por_id(item.id)
        assert resultado is not None
        assert resultado.nome == "Filtro Premium"
        assert resultado.descricao == "Filtro de alta performance"
        assert resultado.preco_unitario == novo_preco

    def test_desativar_item(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        item = _criar_item_estoque(session)

        item.desativar()
        session.flush()

        resultado = repo.obter_por_id(item.id)
        assert resultado is not None
        assert resultado.ativo is False

    def test_obter_por_id_inexistente(self, session: Session) -> None:
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_id(uuid4())

        assert resultado is None


# ===========================================================================
# 5. Ordem de Servico
# ===========================================================================


class TestOrdemDeServicoRepository:
    def test_salvar_e_obter(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, cliente, _ = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_id(ordem.id)

        assert resultado is not None
        assert resultado.cliente_id == cliente.id
        assert resultado.status == StatusOrdem.RECEBIDA

    def test_adicionar_itens_a_ordem(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, servico = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Troca de oleo completa",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("150.00")),
        )
        ordem.adicionar_item(item)
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert len(resultado.itens) == 1
        assert resultado.itens[0].descricao == "Troca de oleo completa"
        assert resultado.itens[0].quantidade == 1
        assert resultado.itens[0].preco_unitario == Dinheiro(
            valor=Decimal("150.00"),
        )

    def test_adicionar_item_com_estoque(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, servico = _criar_ordem_completa(session)
        item_estoque = _criar_item_estoque(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _item_estoque_id=item_estoque.id,
            _descricao="Filtro para troca",
            _quantidade=2,
            _preco_unitario=Dinheiro(valor=Decimal("35.00")),
        )
        ordem.adicionar_item(item)
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert len(resultado.itens) == 1
        assert resultado.itens[0].item_estoque_id == item_estoque.id
        assert resultado.itens[0].servico_catalogo_id == servico.id

    def test_transicao_recebida_para_em_diagnostico(
        self,
        session: Session,
    ) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, _ = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        ordem.iniciar_diagnostico()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.EM_DIAGNOSTICO

    def test_fluxo_completo_ate_entrega(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, servico = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Servico completo",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("200.00")),
        )
        ordem.adicionar_item(item)

        ordem.iniciar_diagnostico()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.EM_DIAGNOSTICO

        ordem.gerar_orcamento()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.AGUARDANDO_APROVACAO
        assert resultado.orcamento is not None
        assert resultado.orcamento.total == Dinheiro(valor=Decimal("200.00"))

        ordem.aprovar_orcamento()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.EM_EXECUCAO

        ordem.finalizar_servico()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.FINALIZADA

        ordem.registrar_entrega()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.ENTREGUE

    def test_cancelar_ordem(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, _ = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        ordem.cancelar(motivo="Cliente desistiu")
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.CANCELADA

    def test_listar_com_paginacao(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        for cpf_num in ("21249722519", "52998224725", "11144477735"):
            cliente = _criar_cliente_cpf(
                session,
                nome=f"C-{cpf_num}",
                cpf_numero=cpf_num,
            )
            placa_str = f"AAA{cpf_num[:4]}"
            cliente.adicionar_veiculo(
                placa=Placa(valor=placa_str),
                marca="X",
                modelo="Y",
                ano=2020,
            )
            session.flush()
            veiculo = cliente.veiculos[0]
            ordem = OrdemDeServico.criar(
                cliente_id=cliente.id,
                veiculo_id=veiculo.id,
            )
            repo.salvar(ordem)

        pagina_1 = repo.listar(offset=0, limit=2)
        pagina_2 = repo.listar(offset=2, limit=2)

        assert len(pagina_1) == 2
        assert len(pagina_2) == 1

    def test_contar(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

        _criar_ordem_completa(session)
        assert repo.contar() == 1

    def test_contar_por_status(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        ordem1, _, servico1 = _criar_ordem_completa(session)

        cliente2 = _criar_cliente_cpf(
            session,
            nome="Outro",
            cpf_numero="52998224725",
        )
        cliente2.adicionar_veiculo(
            placa=Placa(valor="CCC3333"),
            marca="X",
            modelo="Y",
            ano=2020,
        )
        session.flush()
        ordem2 = OrdemDeServico.criar(
            cliente_id=cliente2.id,
            veiculo_id=cliente2.veiculos[0].id,
        )
        repo.salvar(ordem2)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico1.id,
            _descricao="Servico teste",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("100.00")),
        )
        ordem1.adicionar_item(item)
        ordem1.iniciar_diagnostico()
        session.flush()

        contagem = repo.contar_por_status()

        assert contagem.get("recebida", 0) == 1
        assert contagem.get("em_diagnostico", 0) == 1

    def test_calcular_tempo_medio_execucao_valor_exato_do_sql(
        self, session: Session
    ) -> None:
        """Media EXATA do SQL real (``extract('epoch', ...) / 60``, Postgres).

        Timestamps pinados via insert Core: FINALIZADA com 30 min e ENTREGUE
        com 90 min entram na media (= 60.0); CANCELADA com 999 min fica FORA
        (``_ESTADOS_FINALIZADOS``). O unitario anterior era um echo de mock
        (``scalar.return_value == retorno``) e nao provava o SQL.
        """
        from datetime import UTC, datetime, timedelta

        from src.ordem_servico.infraestrutura.mapping import (
            ordens_de_servico_table,
        )
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        # Sem ordens finalizadas/entregues: avg e NULL -> None.
        assert repo.calcular_tempo_medio_execucao() is None

        cliente = criar_cliente_com_veiculo(session)
        veiculo_id = cliente.veiculos[0].id
        base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        cenarios = (
            (StatusOrdem.FINALIZADA, 30),
            (StatusOrdem.ENTREGUE, 90),
            (StatusOrdem.CANCELADA, 999),  # fora da media
        )
        for status, minutos in cenarios:
            session.execute(
                ordens_de_servico_table.insert().values(
                    id=uuid4(),
                    cliente_id=cliente.id,
                    veiculo_id=veiculo_id,
                    status=status.value,
                    orcamento_json=None,
                    criado_em=base,
                    atualizado_em=base + timedelta(minutes=minutos),
                )
            )

        assert repo.calcular_tempo_medio_execucao() == pytest.approx(60.0)

    def test_existe_ativa_para_cliente(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        ordem, cliente, _ = _criar_ordem_completa(session)

        assert repo.existe_ativa_para_cliente(cliente.id) is True
        assert repo.existe_ativa_para_cliente(uuid4()) is False

    def test_existe_ativa_para_veiculo(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        ordem, cliente, _ = _criar_ordem_completa(session)
        veiculo_id = cliente.veiculos[0].id

        assert repo.existe_ativa_para_veiculo(veiculo_id) is True
        assert repo.existe_ativa_para_veiculo(uuid4()) is False

    def test_existe_ativa_com_item_estoque(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        ordem, _, servico = _criar_ordem_completa(session)
        item_estoque = _criar_item_estoque(session)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _item_estoque_id=item_estoque.id,
            _descricao="Item com estoque",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("35.00")),
        )
        ordem.adicionar_item(item)
        session.flush()

        assert repo.existe_ativa_com_item_estoque(item_estoque.id) is True
        assert repo.existe_ativa_com_item_estoque(uuid4()) is False

    def test_nao_existe_ativa_apos_cancelar(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        ordem, cliente, _ = _criar_ordem_completa(session)

        ordem.cancelar(motivo="Teste")
        session.flush()

        assert repo.existe_ativa_para_cliente(cliente.id) is False

    def test_nao_existe_ativa_apos_entrega(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        ordem, cliente, servico = _criar_ordem_completa(session)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Servico completo",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("100.00")),
        )
        ordem.adicionar_item(item)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.finalizar_servico()
        ordem.registrar_entrega()
        session.flush()

        assert repo.existe_ativa_para_cliente(cliente.id) is False

    def test_obter_por_id_inexistente(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        resultado = repo.obter_por_id(uuid4())

        assert resultado is None

    def test_obter_com_itens_aninhados(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, servico = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        item1 = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Servico A",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("100.00")),
        )
        item2 = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Servico B",
            _quantidade=2,
            _preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        ordem.adicionar_item(item1)
        ordem.adicionar_item(item2)
        session.flush()

        resultado = repo.obter_por_id(ordem.id)

        assert resultado is not None
        assert len(resultado.itens) == 2
        descricoes = {i.descricao for i in resultado.itens}
        assert descricoes == {"Servico A", "Servico B"}

    def test_orcamento_persiste_e_reconstroi(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, servico = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        item1 = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Mao de obra",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("200.00")),
        )
        item2 = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Peca",
            _quantidade=3,
            _preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        ordem.adicionar_item(item1)
        ordem.adicionar_item(item2)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        session.flush()

        session.expire_all()
        resultado = repo.obter_por_id(ordem.id)

        assert resultado is not None
        assert resultado.orcamento is not None
        assert resultado.orcamento.total == Dinheiro(valor=Decimal("350.00"))
        assert len(resultado.orcamento.itens) == 2

    def test_fluxo_orcamento_complementar(self, session: Session) -> None:
        from src.ordem_servico.infraestrutura.repository import (
            OrdemDeServicoSQLAlchemyRepository,
        )

        ordem, _, servico = _criar_ordem_completa(session)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Servico inicial",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("100.00")),
        )
        ordem.adicionar_item(item)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        session.flush()

        assert ordem.status == StatusOrdem.EM_EXECUCAO

        ordem.gerar_orcamento_complementar()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR

        ordem.aprovar_orcamento_complementar()
        session.flush()

        resultado = repo.obter_por_id(ordem.id)
        assert resultado is not None
        assert resultado.status == StatusOrdem.EM_EXECUCAO

    def test_subtotal_item_da_ordem(self, session: Session) -> None:
        ordem, _, servico = _criar_ordem_completa(session)

        item = ItemDaOrdem(
            _servico_catalogo_id=servico.id,
            _descricao="Multiplas unidades",
            _quantidade=3,
            _preco_unitario=Dinheiro(valor=Decimal("40.00")),
        )
        ordem.adicionar_item(item)

        assert item.subtotal == Dinheiro(valor=Decimal("120.00"))
