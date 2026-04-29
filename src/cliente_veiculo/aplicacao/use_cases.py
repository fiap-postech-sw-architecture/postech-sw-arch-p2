from __future__ import annotations

from typing import TYPE_CHECKING

from src.cliente_veiculo.aplicacao.dtos import (
    ClienteDTO,
    ClienteResumoDTO,
    VeiculoDTO,
)
from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.documento_anonimizado import DocumentoAnonimizado
from src.cliente_veiculo.dominio.exceptions import (
    ClienteNaoEncontradoException,
    DocumentoDuplicadoException,
    PlacaDuplicadaException,
    VeiculoNaoEncontradoException,
)
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException

if TYPE_CHECKING:
    from uuid import UUID

    from src.cliente_veiculo.aplicacao.dtos import (
        AdicionarVeiculoDTO,
        AtualizarClienteDTO,
        CriarClienteDTO,
    )
    from src.cliente_veiculo.aplicacao.ports import OrdemDeServicoPort
    from src.cliente_veiculo.dominio.documento import Documento
    from src.cliente_veiculo.dominio.repository import ClienteRepository
    from src.cliente_veiculo.dominio.veiculo import Veiculo
    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork


# ----- DTO mapping helpers -----


def _veiculo_dto(v: Veiculo) -> VeiculoDTO:
    """Converte uma entidade Veiculo em `VeiculoDTO` para retorno ao chamador."""
    return VeiculoDTO(
        id=v.id, placa=v.placa.valor, marca=v.marca, modelo=v.modelo, ano=v.ano
    )


def _tipo_documento(cliente: Cliente) -> str:
    """Retorna `"cpf"`, `"cnpj"` ou `"anonimizado"` conforme o tipo do documento.

    Levanta `ViolacaoRegraDeNegocioException` se o documento for de um tipo nao
    suportado. Isso protege contra novos tipos de Documento que possam ser
    adicionados no futuro e classificados silenciosamente como `"cnpj"`.
    """
    if isinstance(cliente.documento, CPF):
        return "cpf"
    if isinstance(cliente.documento, CNPJ):
        return "cnpj"
    if isinstance(cliente.documento, DocumentoAnonimizado):
        return "anonimizado"
    raise ViolacaoRegraDeNegocioException(
        mensagem=(
            f"Tipo de documento nao suportado: {type(cliente.documento).__name__}"
        )
    )


def _cliente_dto(cliente: Cliente) -> ClienteDTO:
    """Converte o agregado Cliente em `ClienteDTO` (detalhado, com veiculos)."""
    return ClienteDTO(
        id=cliente.id,
        nome=cliente.nome,
        documento_formatado=cliente.documento.formatado(),
        documento_mascarado=cliente.documento.mascarado(),
        tipo_documento=_tipo_documento(cliente),
        contato=cliente.contato,
        ativo=cliente.ativo,
        veiculos=[_veiculo_dto(v) for v in cliente.veiculos],
    )


def _cliente_resumo_dto(cliente: Cliente) -> ClienteResumoDTO:
    """Converte o agregado Cliente em `ClienteResumoDTO` (sem veiculos, para listas)."""
    return ClienteResumoDTO(
        id=cliente.id,
        nome=cliente.nome,
        documento_mascarado=cliente.documento.mascarado(),
        tipo_documento=_tipo_documento(cliente),
        contato=cliente.contato,
        ativo=cliente.ativo,
    )


# ----- Use cases -----


class CriarCliente:
    """Cria um novo Cliente com documento unico.

    Precondicoes: `tipo_documento` deve ser `"cpf"` ou `"cnpj"`; `documento`
    deve ser valido no padrao brasileiro.
    Poscondicao: cliente persistido e retornado como `ClienteDTO`.
    Excecoes: `ViolacaoRegraDeNegocioException` (tipo invalido),
    `DocumentoDuplicadoException` (ja cadastrado), `ValueError` (documento malformado).
    """

    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, dto: CriarClienteDTO) -> ClienteDTO:
        if dto.tipo_documento not in ("cpf", "cnpj"):
            raise ViolacaoRegraDeNegocioException(
                mensagem=f"Tipo de documento invalido: {dto.tipo_documento}"
            )

        documento: Documento
        if dto.tipo_documento == "cpf":
            documento = CPF(numero=dto.documento)
        else:
            documento = CNPJ(numero=dto.documento)

        if self._repo.obter_por_documento(documento) is not None:
            raise DocumentoDuplicadoException()

        cliente = Cliente(_nome=dto.nome, _documento=documento, _contato=dto.contato)
        self._salvar_com_commit(cliente)
        return _cliente_dto(cliente)

    def _salvar_com_commit(self, cliente: Cliente) -> None:
        with self._uow:
            self._repo.salvar(cliente)
            self._uow.commit()


class ListarClientes:
    """Lista clientes paginados (padrao: 20 por pagina) e conta total."""

    def __init__(self, repo: ClienteRepository) -> None:
        self._repo = repo

    def executar(self, offset: int = 0, limit: int = 20) -> list[ClienteResumoDTO]:
        clientes = self._repo.listar(offset=offset, limit=limit)
        return [_cliente_resumo_dto(c) for c in clientes]

    def contar(self) -> int:
        return self._repo.contar()


class ObterCliente:
    """Busca um cliente pelo id; levanta `ClienteNaoEncontradoException` se ausente."""

    def __init__(self, repo: ClienteRepository) -> None:
        self._repo = repo

    def executar(self, cliente_id: UUID) -> ClienteDTO:
        cliente = _obter_cliente_ou_falhar(self._repo, cliente_id)
        return _cliente_dto(cliente)


class AtualizarCliente:
    """Atualiza nome e contato do cliente.

    Nome vazio e rejeitado pelo aggregate (`ValueError`). Levanta
    `ClienteNaoEncontradoException` se o cliente nao existe.
    """

    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, cliente_id: UUID, dto: AtualizarClienteDTO) -> ClienteDTO:
        cliente = _obter_cliente_ou_falhar(self._repo, cliente_id)
        cliente.atualizar(nome=dto.nome, contato=dto.contato)
        self._salvar_com_commit(cliente)
        return _cliente_dto(cliente)

    def _salvar_com_commit(self, cliente: Cliente) -> None:
        with self._uow:
            self._repo.salvar(cliente)
            self._uow.commit()


class DesativarCliente:
    """Desativa (soft-delete) um cliente que nao tem OS ativa.

    Consulta `OrdemDeServicoPort.existe_os_ativa_para_cliente` antes de
    desativar. Se houver OS ativa, levanta `ViolacaoRegraDeNegocioException`.
    """

    def __init__(
        self,
        repo: ClienteRepository,
        uow: UnitOfWork,
        os_port: OrdemDeServicoPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._os_port = os_port

    def executar(self, cliente_id: UUID) -> None:
        cliente = _obter_cliente_ou_falhar(self._repo, cliente_id)
        if self._os_port.existe_os_ativa_para_cliente(cliente_id):
            raise ViolacaoRegraDeNegocioException(
                mensagem="Cliente possui ordem de servico ativa"
            )
        cliente.desativar()
        self._salvar_com_commit(cliente)

    def _salvar_com_commit(self, cliente: Cliente) -> None:
        with self._uow:
            self._repo.salvar(cliente)
            self._uow.commit()


class AdicionarVeiculo:
    """Adiciona um veiculo ao cliente, validando marca/modelo e unicidade da placa.

    Precondicoes: `marca` e `modelo` nao vazios; `placa` nao cadastrada em
    outro cliente (verificacao via repository). Poscondicao: veiculo anexado
    ao agregado e persistido.
    """

    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, cliente_id: UUID, dto: AdicionarVeiculoDTO) -> VeiculoDTO:
        if not dto.marca.strip():
            raise ViolacaoRegraDeNegocioException(
                mensagem="Marca do veiculo nao pode ser vazia"
            )
        if not dto.modelo.strip():
            raise ViolacaoRegraDeNegocioException(
                mensagem="Modelo do veiculo nao pode ser vazio"
            )
        cliente = _obter_cliente_ou_falhar(self._repo, cliente_id)
        placa = Placa(valor=dto.placa)
        if self._repo.placa_existe(placa, excluir_cliente_id=cliente_id):
            raise PlacaDuplicadaException()
        veiculo = cliente.adicionar_veiculo(placa, dto.marca, dto.modelo, dto.ano)
        self._salvar_com_commit(cliente)
        return _veiculo_dto(veiculo)

    def _salvar_com_commit(self, cliente: Cliente) -> None:
        with self._uow:
            self._repo.salvar(cliente)
            self._uow.commit()


class ListarVeiculos:
    """Retorna os veiculos de um cliente como lista de `VeiculoDTO`."""

    def __init__(self, repo: ClienteRepository) -> None:
        self._repo = repo

    def executar(self, cliente_id: UUID) -> list[VeiculoDTO]:
        cliente = _obter_cliente_ou_falhar(self._repo, cliente_id)
        return [_veiculo_dto(v) for v in cliente.veiculos]


class RemoverVeiculo:
    """Remove um veiculo do cliente, bloqueando se houver OS ativa para o veiculo."""

    def __init__(
        self,
        repo: ClienteRepository,
        uow: UnitOfWork,
        os_port: OrdemDeServicoPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._os_port = os_port

    def executar(self, cliente_id: UUID, veiculo_id: UUID) -> None:
        cliente = _obter_cliente_ou_falhar(self._repo, cliente_id)
        # Verifica se o veiculo pertence ao cliente ANTES de consultar o port
        # de OS (evita uma chamada potencialmente cara/externa quando o
        # veiculo_id nao pertence ao agregado).
        if not any(v.id == veiculo_id for v in cliente.veiculos):
            raise VeiculoNaoEncontradoException()
        if self._os_port.existe_os_ativa_para_veiculo(veiculo_id):
            raise ViolacaoRegraDeNegocioException(
                mensagem="Veiculo possui ordem de servico ativa"
            )
        cliente.remover_veiculo(veiculo_id)
        self._salvar_com_commit(cliente)

    def _salvar_com_commit(self, cliente: Cliente) -> None:
        with self._uow:
            self._repo.salvar(cliente)
            self._uow.commit()


def _obter_cliente_ou_falhar(repo: ClienteRepository, cliente_id: UUID) -> Cliente:
    """Busca cliente pelo id; levanta `ClienteNaoEncontradoException` se None."""
    cliente = repo.obter_por_id(cliente_id)
    if cliente is None:
        raise ClienteNaoEncontradoException()
    return cliente
