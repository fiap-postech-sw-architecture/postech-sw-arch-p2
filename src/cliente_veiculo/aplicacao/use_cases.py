from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from src.cliente_veiculo.aplicacao.dtos import (
    ClienteDTO,
    ClienteResumoDTO,
    VeiculoDTO,
)
from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.contato import Contato
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


def veiculo_dto(v: Veiculo) -> VeiculoDTO:
    """Converte uma entidade Veiculo em `VeiculoDTO` para retorno ao chamador."""
    return VeiculoDTO(
        id=v.id, placa=v.placa.valor, marca=v.marca, modelo=v.modelo, ano=v.ano
    )


def tipo_documento(cliente: Cliente) -> str:
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
        tipo_documento=tipo_documento(cliente),
        contato=cliente.contato.valor,
        ativo=cliente.ativo,
        veiculos=[veiculo_dto(v) for v in cliente.veiculos],
    )


def _cliente_resumo_dto(cliente: Cliente) -> ClienteResumoDTO:
    """Converte o agregado Cliente em `ClienteResumoDTO` (sem veiculos, para listas)."""
    return ClienteResumoDTO(
        id=cliente.id,
        nome=cliente.nome,
        documento_mascarado=cliente.documento.mascarado(),
        tipo_documento=tipo_documento(cliente),
        contato=cliente.contato.valor,
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

        contato = Contato(valor=dto.contato)
        cliente = Cliente.criar(nome=dto.nome, documento=documento, contato=contato)
        try:
            _salvar_com_commit(self._uow, self._repo, cliente)
        except IntegrityError as exc:
            # Corrida check-then-insert: outra transacao inseriu o mesmo
            # documento entre o obter_por_documento e o commit. A UNIQUE de
            # documento_hash barra a duplicata; mapeia para o mesmo 409 do
            # caminho de verificacao previa.
            raise DocumentoDuplicadoException() from exc
        return _cliente_dto(cliente)


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
        cliente = obter_cliente_ou_falhar(self._repo, cliente_id)
        return _cliente_dto(cliente)


class AtualizarCliente:
    """Atualiza nome e contato do cliente.

    Nome vazio e rejeitado pelo aggregate (`ValueError`). Levanta
    `ClienteNaoEncontradoException` se o cliente nao existe e
    `ViolacaoRegraDeNegocioException` se o cliente esta inativo/anonimizado
    (mutacao reverteria o erasure LGPD).
    """

    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, cliente_id: UUID, dto: AtualizarClienteDTO) -> ClienteDTO:
        cliente = obter_cliente_ou_falhar(self._repo, cliente_id)
        _exigir_cliente_ativo(cliente)
        cliente.atualizar(nome=dto.nome, contato=Contato(valor=dto.contato))
        _salvar_com_commit(self._uow, self._repo, cliente)
        return _cliente_dto(cliente)


class DesativarCliente:
    """Desativa (soft-delete) um cliente que nao tem OS ativa.

    Consulta `OrdemDeServicoPort.existe_os_ativa_para_cliente` antes de
    desativar. Se houver OS ativa, levanta `ViolacaoRegraDeNegocioException`.

    Decisao explicita: a desativacao e TERMINAL — nao existe caso de uso de
    reativacao e clientes inativos rejeitam qualquer mutacao (ver
    `_exigir_cliente_ativo`). Consequencia: o documento (CPF/CNPJ) permanece
    RESERVADO pela UNIQUE de `documento_hash`; um novo cadastro com o mesmo
    documento e rejeitado com `DocumentoDuplicadoException`.
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
        cliente = obter_cliente_ou_falhar(self._repo, cliente_id)
        if self._os_port.existe_os_ativa_para_cliente(cliente_id):
            raise ViolacaoRegraDeNegocioException(
                mensagem="Cliente possui ordem de servico ativa"
            )
        cliente.desativar()
        _salvar_com_commit(self._uow, self._repo, cliente)


class AdicionarVeiculo:
    """Adiciona um veiculo ao cliente, validando unicidade global da placa.

    Precondicoes: cliente ativo; `placa` nao cadastrada em outro cliente
    (verificacao via repository). Marca/modelo vazios sao rejeitados pelo
    dominio (`Veiculo.__post_init__`, que tambem apara com `strip()`).
    Poscondicao: veiculo anexado ao agregado e persistido.
    """

    def __init__(self, repo: ClienteRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, cliente_id: UUID, dto: AdicionarVeiculoDTO) -> VeiculoDTO:
        cliente = obter_cliente_ou_falhar(self._repo, cliente_id)
        _exigir_cliente_ativo(cliente)
        placa = Placa(valor=dto.placa)
        if self._repo.placa_existe(placa, excluir_cliente_id=cliente_id):
            raise PlacaDuplicadaException()
        veiculo = cliente.adicionar_veiculo(placa, dto.marca, dto.modelo, dto.ano)
        try:
            _salvar_com_commit(self._uow, self._repo, cliente)
        except IntegrityError as exc:
            # Corrida check-then-insert: outra transacao inseriu a mesma placa
            # entre o placa_existe e o commit; a UNIQUE de veiculos.placa barra
            # a duplicata. Mapeia para o mesmo 409 da verificacao previa.
            raise PlacaDuplicadaException() from exc
        return veiculo_dto(veiculo)


class ListarVeiculos:
    """Retorna os veiculos de um cliente como lista de `VeiculoDTO`."""

    def __init__(self, repo: ClienteRepository) -> None:
        self._repo = repo

    def executar(self, cliente_id: UUID) -> list[VeiculoDTO]:
        cliente = obter_cliente_ou_falhar(self._repo, cliente_id)
        return [veiculo_dto(v) for v in cliente.veiculos]


class RemoverVeiculo:
    """Remove um veiculo do cliente, bloqueando se houver qualquer OS vinculada."""

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
        with self._uow:
            cliente = obter_cliente_ou_falhar(self._repo, cliente_id)
            # Pre-check de cliente ativo (fail-fast + mensagem 409 consistente
            # com os demais use cases). O agregado ainda e a ultima linha:
            # `cliente.remover_veiculo` re-checa via `_exigir_ativo`.
            _exigir_cliente_ativo(cliente)
            # Confere a propriedade pelo agregado primeiro (evita chamada de
            # port quando o veiculo nem pertence ao cliente) e em seguida
            # adquire ``FOR UPDATE`` na linha do veiculo. O lock conflita com
            # o ``FOR KEY SHARE`` que a validacao de FK em INSERTs novos de
            # ordens_de_servico adquire, serializando as duas operacoes e
            # eliminando o IntegrityError silencioso por raca delete x criar.
            if not any(v.id == veiculo_id for v in cliente.veiculos):
                raise VeiculoNaoEncontradoException()
            # Re-checa a presenca da linha apos o lock: se outra transacao
            # concorrente ja deletou o veiculo, ``with_for_update`` retorna
            # zero linhas (silent no-op). Sem essa guarda, prosseguir levaria
            # ao DELETE de zero linhas no flush e a um StaleDataError → 500;
            # com a guarda, mapeamos explicitamente para 404.
            if not self._repo.bloquear_veiculo_para_remocao(veiculo_id):
                raise VeiculoNaoEncontradoException()
            if self._os_port.existe_os_para_veiculo(veiculo_id):
                raise ViolacaoRegraDeNegocioException(
                    mensagem=(
                        "Veiculo possui ordem de servico vinculada "
                        "e nao pode ser removido"
                    )
                )
            cliente.remover_veiculo(veiculo_id)
            self._repo.salvar(cliente)
            self._uow.commit()


def obter_cliente_ou_falhar(repo: ClienteRepository, cliente_id: UUID) -> Cliente:
    """Busca cliente pelo id; levanta `ClienteNaoEncontradoException` se None."""
    cliente = repo.obter_por_id(cliente_id)
    if cliente is None:
        raise ClienteNaoEncontradoException()
    return cliente


def _exigir_cliente_ativo(cliente: Cliente) -> None:
    """Rejeita mutacao de cliente inativo (desativado ou anonimizado).

    Fecha a brecha de "reverter" o erasure LGPD (#168): sem este guard, um
    PUT/POST re-escreveria nome/contato ou anexaria veiculos a um cliente
    anonimizado, re-populando PII num agregado que deveria ficar terminal.
    """
    if not cliente.ativo:
        raise ViolacaoRegraDeNegocioException(
            mensagem="cliente inativo nao pode ser alterado"
        )


def _salvar_com_commit(
    uow: UnitOfWork, repo: ClienteRepository, cliente: Cliente
) -> None:
    """Persiste o agregado dentro da UnitOfWork e confirma a transacao."""
    with uow:
        repo.salvar(cliente)
        uow.commit()
