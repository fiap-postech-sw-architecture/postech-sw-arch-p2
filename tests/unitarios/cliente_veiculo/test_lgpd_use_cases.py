from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.cliente_veiculo.aplicacao.dtos import RegistrarConsentimentoDTO
from src.cliente_veiculo.aplicacao.lgpd_use_cases import (
    ExcluirDadosPessoais,
    ExportarDadosPessoais,
    RegistrarConsentimento,
    RevogarConsentimento,
)
from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.consentimento import ConsentimentoCliente
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.documento_anonimizado import DocumentoAnonimizado
from src.cliente_veiculo.dominio.exceptions import (
    ClienteNaoEncontradoException,
    ConsentimentoNaoEncontradoException,
)
from src.cliente_veiculo.dominio.placa import Placa

CPF_VALIDO = "21249722519"


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None:
            self.rolled_back = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeClienteRepoLGPD:
    def __init__(self) -> None:
        self._clientes: dict[UUID, Cliente] = {}
        self._consentimentos: dict[tuple[UUID, str], ConsentimentoCliente] = {}
        self._anonimizado: set[UUID] = set()

    def obter_por_id(self, cliente_id: UUID) -> Cliente | None:
        return self._clientes.get(cliente_id)

    def salvar(self, cliente: Cliente) -> None:
        self._clientes[cliente.id] = cliente

    def listar(self, offset: int = 0, limit: int = 20) -> list[Cliente]:
        todos = list(self._clientes.values())
        return todos[offset : offset + limit]

    def contar(self) -> int:
        return len(self._clientes)

    def obter_por_documento(self, documento: object) -> Cliente | None:
        return None

    def placa_existe(
        self, placa: Placa, excluir_cliente_id: UUID | None = None
    ) -> bool:
        return False

    def obter_dados_pessoais(self, cliente_id: UUID) -> Cliente | None:
        return self._clientes.get(cliente_id)

    def anonimizar_dados(self, cliente_id: UUID) -> None:
        self._anonimizado.add(cliente_id)

    def salvar_consentimento(self, consentimento: ConsentimentoCliente) -> None:
        key = (consentimento.cliente_id, consentimento.tipo)
        self._consentimentos[key] = consentimento

    def obter_consentimento(
        self, cliente_id: UUID, tipo: str
    ) -> ConsentimentoCliente | None:
        return self._consentimentos.get((cliente_id, tipo))

    def revogar_consentimento(self, cliente_id: UUID, tipo: str) -> None:
        key = (cliente_id, tipo)
        c = self._consentimentos.get(key)
        if c is not None:
            c.revogar(datetime.now(tz=UTC))


class TestExportarDadosPessoais:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepoLGPD()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        repo.salvar(cliente)
        uc = ExportarDadosPessoais(repo=repo)
        result = uc.executar(cliente.id)
        assert result.nome == "Joao"
        assert result.tipo_documento == "cpf"
        assert result.contato == "11999"
        assert len(result.veiculos) == 1
        assert result.veiculos[0]["placa"] == "ABC1234"
        assert result.ativo is True

    def test_cliente_inexistente(self) -> None:
        repo = FakeClienteRepoLGPD()
        uc = ExportarDadosPessoais(repo=repo)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4())

    def test_export_de_cliente_anonimizado_retorna_tipo_anonimizado(self) -> None:
        # Apos anonimizacao, ``DocumentoAnonimizado`` substitui CPF/CNPJ no
        # agregado. O DTO precisa refletir o novo tipo — antes do refactor
        # caia no ramo ``else "cnpj"`` mesmo para CPFs originais.
        repo = FakeClienteRepoLGPD()
        cliente_id = uuid4()
        cliente = Cliente(
            id=cliente_id,
            _nome="ANONIMIZADO",
            _documento=DocumentoAnonimizado(cliente_id=cliente_id),
            _contato="anonimizado@anonimizado.local",
        )
        repo.salvar(cliente)
        uc = ExportarDadosPessoais(repo=repo)
        result = uc.executar(cliente_id)
        assert result.tipo_documento == "anonimizado"
        assert result.documento_formatado == "ANONIMIZADO"
        assert result.nome == "ANONIMIZADO"


class TestExcluirDadosPessoais:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepoLGPD()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = ExcluirDadosPessoais(repo=repo, uow=uow)
        uc.executar(cliente.id)
        assert cliente.id in repo._anonimizado
        assert uow.committed

    def test_cliente_inexistente(self) -> None:
        repo = FakeClienteRepoLGPD()
        uow = FakeUnitOfWork()
        uc = ExcluirDadosPessoais(repo=repo, uow=uow)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4())


class TestRegistrarConsentimento:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepoLGPD()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = RegistrarConsentimento(repo=repo, uow=uow)
        dto = RegistrarConsentimentoDTO(tipo="tratamento_dados")
        result = uc.executar(cliente.id, dto)
        assert result.tipo == "tratamento_dados"
        assert result.ativo is True
        assert result.revogado_em is None
        assert result.cliente_id == cliente.id
        assert uow.committed

    def test_cliente_inexistente(self) -> None:
        repo = FakeClienteRepoLGPD()
        uow = FakeUnitOfWork()
        uc = RegistrarConsentimento(repo=repo, uow=uow)
        dto = RegistrarConsentimentoDTO(tipo="marketing")
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4(), dto)


class TestRevogarConsentimento:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepoLGPD()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        agora = datetime.now(tz=UTC)
        consentimento = ConsentimentoCliente(
            _cliente_id=cliente.id,
            _tipo="marketing",
            _concedido_em=agora,
        )
        repo.salvar_consentimento(consentimento)
        uc = RevogarConsentimento(repo=repo, uow=uow)
        uc.executar(cliente.id, "marketing")
        salvo = repo.obter_consentimento(cliente.id, "marketing")
        assert salvo is not None
        assert salvo.ativo is False
        assert uow.committed

    def test_dupla_revogacao_levanta_erro(self) -> None:
        repo = FakeClienteRepoLGPD()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        agora = datetime.now(tz=UTC)
        consentimento = ConsentimentoCliente(
            _cliente_id=cliente.id,
            _tipo="marketing",
            _concedido_em=agora,
        )
        consentimento.revogar(agora)
        repo.salvar_consentimento(consentimento)
        uc = RevogarConsentimento(repo=repo, uow=uow)
        with pytest.raises(ValueError, match="ja foi revogado"):
            uc.executar(cliente.id, "marketing")

    def test_consentimento_inexistente(self) -> None:
        repo = FakeClienteRepoLGPD()
        uow = FakeUnitOfWork()
        uc = RevogarConsentimento(repo=repo, uow=uow)
        with pytest.raises(ConsentimentoNaoEncontradoException):
            uc.executar(uuid4(), "marketing")
