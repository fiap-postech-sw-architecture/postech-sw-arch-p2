from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    from types import TracebackType

from src.cliente_veiculo.aplicacao.dtos import (
    AdicionarVeiculoDTO,
    AtualizarClienteDTO,
    CriarClienteDTO,
)
from src.cliente_veiculo.aplicacao.use_cases import (
    AdicionarVeiculo,
    AtualizarCliente,
    CriarCliente,
    DesativarCliente,
    ListarClientes,
    ListarVeiculos,
    ObterCliente,
    RemoverVeiculo,
)
from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.exceptions import (
    ClienteNaoEncontradoException,
    DocumentoDuplicadoException,
    PlacaDuplicadaException,
    VeiculoNaoEncontradoException,
)
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException

CPF_VALIDO = "21249722519"
CNPJ_VALIDO = "11222333000181"

# Pool de CPFs validos distintos para testes de listagem/paginacao
# (gerados com brutils.cpf.generate; evitam colisao de documento).
_POOL_CPFS = (
    "21249722519",
    "57648016648",
    "93214407473",
    "44635573567",
    "09615692808",
    "68813601506",
    "25339375765",
)


def _cpf_alternativo(seed: int) -> str:
    """Retorna um CPF valido do pool para testes com multiplos clientes."""
    return _POOL_CPFS[seed % len(_POOL_CPFS)]


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
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rolled_back = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeClienteRepository:
    def __init__(self) -> None:
        self._clientes: dict[UUID, Cliente] = {}

    def obter_por_id(self, cliente_id: UUID) -> Cliente | None:
        return self._clientes.get(cliente_id)

    def salvar(self, cliente: Cliente) -> None:
        self._clientes[cliente.id] = cliente

    def listar(self, offset: int = 0, limit: int = 20) -> list[Cliente]:
        todos = list(self._clientes.values())
        return todos[offset : offset + limit]

    def contar(self) -> int:
        return len(self._clientes)

    def obter_por_documento(self, documento: CPF | CNPJ) -> Cliente | None:
        for c in self._clientes.values():
            if c.documento == documento:
                return c
        return None

    def placa_existe(
        self, placa: Placa, excluir_cliente_id: UUID | None = None
    ) -> bool:
        for c in self._clientes.values():
            if excluir_cliente_id and c.id == excluir_cliente_id:
                continue
            if any(v.placa == placa for v in c.veiculos):
                return True
        return False


class StubOrdemDeServicoPort:
    def __init__(
        self,
        os_ativa_cliente: bool = False,
        os_ativa_veiculo: bool = False,
    ) -> None:
        self._os_ativa_cliente = os_ativa_cliente
        self._os_ativa_veiculo = os_ativa_veiculo

    def existe_os_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        return self._os_ativa_cliente

    def existe_os_ativa_para_veiculo(self, veiculo_id: UUID) -> bool:
        return self._os_ativa_veiculo


class TestCriarCliente:
    def test_sucesso_com_cpf(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = CriarCliente(repo=repo, uow=uow)
        dto = CriarClienteDTO(
            nome="Joao", documento=CPF_VALIDO, tipo_documento="cpf", contato="11999"
        )
        result = uc.executar(dto)
        assert result.nome == "Joao"
        assert result.tipo_documento == "cpf"
        assert uow.committed

    def test_sucesso_com_cnpj(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = CriarCliente(repo=repo, uow=uow)
        dto = CriarClienteDTO(
            nome="Empresa", documento=CNPJ_VALIDO, tipo_documento="cnpj", contato="1133"
        )
        result = uc.executar(dto)
        assert result.tipo_documento == "cnpj"

    def test_documento_duplicado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = CriarCliente(repo=repo, uow=uow)
        dto = CriarClienteDTO(
            nome="Joao", documento=CPF_VALIDO, tipo_documento="cpf", contato="11999"
        )
        uc.executar(dto)
        with pytest.raises(DocumentoDuplicadoException):
            uc.executar(dto)

    def test_tipo_documento_invalido(self) -> None:
        from src.compartilhado.dominio.exceptions import (
            ViolacaoRegraDeNegocioException,
        )

        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = CriarCliente(repo=repo, uow=uow)
        dto = CriarClienteDTO(
            nome="Joao",
            documento=CPF_VALIDO,
            tipo_documento="passaporte",
            contato="11999",
        )
        with pytest.raises(ViolacaoRegraDeNegocioException, match="Tipo de documento"):
            uc.executar(dto)

    def test_documento_invalido_cpf_malformado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = CriarCliente(repo=repo, uow=uow)
        dto = CriarClienteDTO(
            nome="Joao",
            documento="12345678900",  # invalid checksum
            tipo_documento="cpf",
            contato="11999",
        )
        with pytest.raises(ValueError, match="CPF invalido"):
            uc.executar(dto)

    def test_documento_invalido_cnpj_vazio(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = CriarCliente(repo=repo, uow=uow)
        dto = CriarClienteDTO(
            nome="Empresa",
            documento="",
            tipo_documento="cnpj",
            contato="11999",
        )
        with pytest.raises(ValueError, match="CNPJ invalido"):
            uc.executar(dto)


class TestListarClientes:
    def test_lista_vazia(self) -> None:
        repo = FakeClienteRepository()
        uc = ListarClientes(repo=repo)
        assert uc.executar() == []

    def test_contar(self) -> None:
        repo = FakeClienteRepository()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = ListarClientes(repo=repo)
        assert uc.contar() == 1

    def test_com_dados(self) -> None:
        repo = FakeClienteRepository()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = ListarClientes(repo=repo)
        result = uc.executar()
        assert len(result) == 1
        assert result[0].nome == "Joao"

    def test_paginacao(self) -> None:
        repo = FakeClienteRepository()
        for i in range(5):
            cpf = CPF(numero=_cpf_alternativo(i))
            cliente = Cliente(_nome=f"Cliente {i}", _documento=cpf, _contato="11999")
            repo.salvar(cliente)
        uc = ListarClientes(repo=repo)
        result = uc.executar(offset=0, limit=2)
        assert len(result) == 2


class TestObterCliente:
    def test_encontrado(self) -> None:
        repo = FakeClienteRepository()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = ObterCliente(repo=repo)
        result = uc.executar(cliente.id)
        assert result.nome == "Joao"

    def test_nao_encontrado(self) -> None:
        repo = FakeClienteRepository()
        uc = ObterCliente(repo=repo)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4())


class TestAtualizarCliente:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = AtualizarCliente(repo=repo, uow=uow)
        dto = AtualizarClienteDTO(nome="Joao Silva", contato="11888")
        result = uc.executar(cliente.id, dto)
        assert result.nome == "Joao Silva"

    def test_nao_encontrado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = AtualizarCliente(repo=repo, uow=uow)
        dto = AtualizarClienteDTO(nome="X", contato="Y")
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4(), dto)


class TestDesativarCliente:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort(os_ativa_cliente=False)
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = DesativarCliente(repo=repo, uow=uow, os_port=os_port)
        uc.executar(cliente.id)
        assert repo.obter_por_id(cliente.id) is not None
        assert not repo.obter_por_id(cliente.id).ativo  # type: ignore[union-attr]

    def test_bloqueado_por_os_ativa(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort(os_ativa_cliente=True)
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = DesativarCliente(repo=repo, uow=uow, os_port=os_port)
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(cliente.id)

    def test_nao_encontrado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort()
        uc = DesativarCliente(repo=repo, uow=uow, os_port=os_port)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4())


class TestAdicionarVeiculo:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = AdicionarVeiculo(repo=repo, uow=uow)
        dto = AdicionarVeiculoDTO(placa="ABC1234", marca="Fiat", modelo="Uno", ano=2020)
        result = uc.executar(cliente.id, dto)
        assert result.placa == "ABC1234"
        assert uow.committed

    def test_placa_duplicada_global(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente1 = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        placa = Placa(valor="ABC1234")
        cliente1.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        repo.salvar(cliente1)
        cnpj = CNPJ(numero=CNPJ_VALIDO)
        cliente2 = Cliente(_nome="Maria", _documento=cnpj, _contato="11888")
        repo.salvar(cliente2)
        uc = AdicionarVeiculo(repo=repo, uow=uow)
        dto = AdicionarVeiculoDTO(placa="ABC1234", marca="VW", modelo="Gol", ano=2021)
        with pytest.raises(PlacaDuplicadaException):
            uc.executar(cliente2.id, dto)

    def test_cliente_nao_encontrado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        uc = AdicionarVeiculo(repo=repo, uow=uow)
        dto = AdicionarVeiculoDTO(placa="ABC1234", marca="Fiat", modelo="Uno", ano=2020)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4(), dto)

    def test_marca_vazia_rejeitada(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = AdicionarVeiculo(repo=repo, uow=uow)
        dto = AdicionarVeiculoDTO(placa="ABC1234", marca="  ", modelo="Uno", ano=2020)
        with pytest.raises(ViolacaoRegraDeNegocioException, match="Marca"):
            uc.executar(cliente.id, dto)

    def test_modelo_vazio_rejeitado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = AdicionarVeiculo(repo=repo, uow=uow)
        dto = AdicionarVeiculoDTO(placa="ABC1234", marca="Fiat", modelo="", ano=2020)
        with pytest.raises(ViolacaoRegraDeNegocioException, match="Modelo"):
            uc.executar(cliente.id, dto)


class TestListarVeiculos:
    def test_com_veiculos(self) -> None:
        repo = FakeClienteRepository()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        placa = Placa(valor="ABC1234")
        cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        repo.salvar(cliente)
        uc = ListarVeiculos(repo=repo)
        result = uc.executar(cliente.id)
        assert len(result) == 1

    def test_sem_veiculos(self) -> None:
        repo = FakeClienteRepository()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = ListarVeiculos(repo=repo)
        assert uc.executar(cliente.id) == []

    def test_cliente_nao_encontrado(self) -> None:
        repo = FakeClienteRepository()
        uc = ListarVeiculos(repo=repo)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4())


class TestRemoverVeiculo:
    def test_sucesso(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort(os_ativa_veiculo=False)
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        placa = Placa(valor="ABC1234")
        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        repo.salvar(cliente)
        uc = RemoverVeiculo(repo=repo, uow=uow, os_port=os_port)
        uc.executar(cliente.id, veiculo.id)
        assert len(repo.obter_por_id(cliente.id).veiculos) == 0  # type: ignore[union-attr]

    def test_bloqueado_por_os_ativa(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort(os_ativa_veiculo=True)
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        placa = Placa(valor="ABC1234")
        veiculo = cliente.adicionar_veiculo(placa, "Fiat", "Uno", 2020)
        repo.salvar(cliente)
        uc = RemoverVeiculo(repo=repo, uow=uow, os_port=os_port)
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(cliente.id, veiculo.id)

    def test_veiculo_nao_encontrado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort()
        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        repo.salvar(cliente)
        uc = RemoverVeiculo(repo=repo, uow=uow, os_port=os_port)
        with pytest.raises(VeiculoNaoEncontradoException):
            uc.executar(cliente.id, uuid4())

    def test_cliente_nao_encontrado(self) -> None:
        repo = FakeClienteRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort()
        uc = RemoverVeiculo(repo=repo, uow=uow, os_port=os_port)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(uuid4(), uuid4())


class _DocumentoFake:
    """Implementa o Protocol Documento estruturalmente, mas nao e CPF nem CNPJ."""

    numero = "00000000000"

    def formatado(self) -> str:
        return self.numero

    def mascarado(self) -> str:
        return "***"


class TestTipoDocumentoGuardaTipoDesconhecido:
    def test_tipo_documento_desconhecido_levanta(self) -> None:
        from src.cliente_veiculo.aplicacao.use_cases import _tipo_documento

        cpf = CPF(numero=CPF_VALIDO)
        cliente = Cliente(_nome="Joao", _documento=cpf, _contato="11999")
        # Substitui o documento por uma implementacao que nao e CPF nem CNPJ
        object.__setattr__(cliente, "_documento", _DocumentoFake())

        with pytest.raises(
            ViolacaoRegraDeNegocioException, match="Tipo de documento nao suportado"
        ):
            _tipo_documento(cliente)
