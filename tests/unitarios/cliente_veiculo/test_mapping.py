from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.cliente_veiculo.infraestrutura import mapping as mapping_module
from src.cliente_veiculo.infraestrutura.mapping import (
    clientes_table,
    iniciar_mapeamentos,
    veiculos_table,
)
from src.compartilhado.infraestrutura.database import metadata


class TestMapping:
    def test_clientes_table_colunas(self) -> None:
        colunas = {c.name for c in clientes_table.columns}
        assert colunas == {
            "id",
            "nome",
            "documento",
            "documento_hash",
            "tipo_documento",
            "contato",
            "ativo",
        }

    def test_veiculos_table_colunas(self) -> None:
        colunas = {c.name for c in veiculos_table.columns}
        assert colunas == {
            "id",
            "placa",
            "marca",
            "modelo",
            "ano",
            "cliente_id",
        }

    def test_clientes_id_primary_key(self) -> None:
        assert clientes_table.c.id.primary_key

    def test_veiculos_id_primary_key(self) -> None:
        assert veiculos_table.c.id.primary_key

    def test_documento_hash_unique(self) -> None:
        assert clientes_table.c.documento_hash.unique

    def test_placa_unique(self) -> None:
        assert veiculos_table.c.placa.unique

    def test_iniciar_mapeamentos_e_idempotente(self) -> None:
        iniciar_mapeamentos()
        iniciar_mapeamentos()
        assert mapping_module._mapeamento_iniciado is True


@pytest.fixture
def engine_sqlite() -> object:
    iniciar_mapeamentos()
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    return engine


def _criar_cliente(documento: CPF | CNPJ, nome: str = "Joao Silva") -> Cliente:
    return Cliente(
        id=uuid4(),
        _nome=nome,
        _documento=documento,
        _contato="11999990000",
    )


class TestEventosMapeamento:
    def test_insert_e_select_de_cliente_com_cpf_cifra_e_decifra(
        self, engine_sqlite: object
    ) -> None:
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            cliente = Cliente(
                id=cliente_id,
                _nome="Joao Silva",
                _documento=CPF(numero="21249722519"),
                _contato="11999990000",
            )
            sessao_insert.add(cliente)
            sessao_insert.flush()
            documento_cifrado = sessao_insert.scalar(
                clientes_table.select().with_only_columns(clientes_table.c.documento)
            )
            tipo_gravado = sessao_insert.scalar(
                clientes_table.select().with_only_columns(
                    clientes_table.c.tipo_documento
                )
            )
            hash_gravado = sessao_insert.scalar(
                clientes_table.select().with_only_columns(
                    clientes_table.c.documento_hash
                )
            )
            sessao_insert.commit()

        assert documento_cifrado is not None
        assert documento_cifrado.startswith("gAAAAA")
        assert tipo_gravado == "cpf"
        assert hash_gravado is not None
        assert len(hash_gravado) == 64

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert isinstance(carregado._documento, CPF)
            assert carregado._documento.numero == "21249722519"

    def test_carregamento_de_cliente_com_documento_plaintext_legado(
        self, engine_sqlite: object
    ) -> None:
        """Cobre a branch em que o documento no banco NAO esta cifrado (legado).

        O listener `_reconstruir_documento` testa `startswith("gAAAAA")` para
        decidir se deve decifrar. Valores legados (migrados antes da adocao da
        cifra) passam direto pelo branch else e sao lidos como plaintext.
        """
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            sessao_insert.execute(
                clientes_table.insert().values(
                    id=cliente_id,
                    nome="Legado",
                    documento="21249722519",  # plaintext, nao comeca com gAAAAA
                    documento_hash="deterministic-hash-legado",
                    tipo_documento="cpf",
                    contato="11988887777",
                    ativo=True,
                )
            )
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert isinstance(carregado._documento, CPF)
            assert carregado._documento.numero == "21249722519"

    def test_insert_de_cliente_com_cnpj(self, engine_sqlite: object) -> None:
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            cliente = Cliente(
                id=cliente_id,
                _nome="Empresa LTDA",
                _documento=CNPJ(numero="11222333000181"),
                _contato="11999990000",
            )
            sessao_insert.add(cliente)
            sessao_insert.flush()
            tipo_gravado = sessao_insert.scalar(
                clientes_table.select().with_only_columns(
                    clientes_table.c.tipo_documento
                )
            )
            sessao_insert.commit()

        assert tipo_gravado == "cnpj"

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert isinstance(carregado._documento, CNPJ)

    def test_insert_e_select_de_veiculo_reconstroi_placa(
        self, engine_sqlite: object
    ) -> None:
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            cliente = Cliente(
                id=cliente_id,
                _nome="Maria",
                _documento=CPF(numero="21249722519"),
                _contato="11988887777",
            )
            cliente.adicionar_veiculo(
                placa=Placa(valor="ABC1D23"),
                marca="Fiat",
                modelo="Uno",
                ano=2020,
            )
            sessao_insert.add(cliente)
            sessao_insert.flush()
            placa_gravada = sessao_insert.scalar(
                veiculos_table.select().with_only_columns(veiculos_table.c.placa)
            )
            sessao_insert.commit()

        assert placa_gravada == "ABC1D23"

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert len(carregado.veiculos) == 1
            assert carregado.veiculos[0]._placa.valor == "ABC1D23"
