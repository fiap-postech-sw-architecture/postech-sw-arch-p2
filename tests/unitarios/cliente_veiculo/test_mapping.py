from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.documento_anonimizado import DocumentoAnonimizado
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
        _contato=Contato(valor="11999990000"),
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
                _contato=Contato(valor="11999990000"),
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
                _contato=Contato(valor="11999990000"),
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
                _contato=Contato(valor="11988887777"),
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

    def test_insert_e_select_de_cliente_reconstroi_contato(
        self, engine_sqlite: object
    ) -> None:
        # Espelha o round-trip da Placa: o VO ``Contato`` decompoe para a coluna
        # ``contato`` (String(255)) no before_insert e reidrata no load.
        cliente_id = uuid4()
        contato_livre = "Maria - maria@x.com / (11) 99999-0000"
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            cliente = Cliente(
                id=cliente_id,
                _nome="Maria",
                _documento=CPF(numero="21249722519"),
                _contato=Contato(valor=contato_livre),
            )
            sessao_insert.add(cliente)
            sessao_insert.flush()
            contato_gravado = sessao_insert.scalar(
                clientes_table.select().with_only_columns(clientes_table.c.contato)
            )
            sessao_insert.commit()

        # A coluna guarda a string crua (serializacao do VO), nao o objeto.
        assert contato_gravado == contato_livre

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert isinstance(carregado._contato, Contato)
            assert carregado.contato == Contato(valor=contato_livre)
            assert carregado.contato.valor == contato_livre

    def test_update_de_contato_persiste_via_before_update(
        self, engine_sqlite: object
    ) -> None:
        # O before_update decompoe o novo VO ``Contato`` de volta para a coluna.
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            cliente = Cliente(
                id=cliente_id,
                _nome="Joao",
                _documento=CPF(numero="21249722519"),
                _contato=Contato(valor="joao@old.com"),
            )
            sessao_insert.add(cliente)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_update:  # type: ignore[arg-type]
            cliente = sessao_update.get(Cliente, cliente_id)
            assert cliente is not None
            cliente.atualizar(nome="Joao", contato=Contato(valor="joao@new.com"))
            sessao_update.flush()
            contato_gravado = sessao_update.scalar(
                clientes_table.select()
                .with_only_columns(clientes_table.c.contato)
                .where(clientes_table.c.id == cliente_id)
            )
            sessao_update.commit()

        assert contato_gravado == "joao@new.com"

    def test_load_reidrata_contato_de_valor_lgpd_anonimizado(
        self, engine_sqlite: object
    ) -> None:
        # ``anonimizar_dados`` grava ``contato="anonimizado@anonimizado.local"``
        # via raw UPDATE (bypassa listeners). Ao recarregar, o VO PRECISA aceitar
        # esse sentinela — senao o load explodiria com ValueError.
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            sessao_insert.execute(
                clientes_table.insert().values(
                    id=cliente_id,
                    nome="ANONIMIZADO",
                    documento="ANONIMIZADO",
                    documento_hash=f"ANONIMIZADO:{cliente_id}",
                    tipo_documento="cpf",
                    contato="anonimizado@anonimizado.local",
                    ativo=False,
                )
            )
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert carregado.contato == Contato(valor="anonimizado@anonimizado.local")

    def test_cliente_carregado_rejeita_mutacao_de_id(
        self, engine_sqlite: object
    ) -> None:
        # Regressao: SQLAlchemy nao chama __post_init__ ao reidratar; o
        # listener ``load`` precisa ativar _id_atribuido para que
        # Entity.__setattr__ continue bloqueando mutacao de id.
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            cliente = Cliente(
                id=cliente_id,
                _nome="Joao",
                _documento=CPF(numero="21249722519"),
                _contato=Contato(valor="11999990000"),
            )
            sessao_insert.add(cliente)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            with pytest.raises(
                AttributeError, match="nao pode ser alterada apos criacao"
            ):
                carregado.id = uuid4()

    def test_veiculo_carregado_rejeita_mutacao_de_id(
        self, engine_sqlite: object
    ) -> None:
        cliente_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            cliente = Cliente(
                id=cliente_id,
                _nome="Maria",
                _documento=CPF(numero="21249722519"),
                _contato=Contato(valor="11988887777"),
            )
            cliente.adicionar_veiculo(
                placa=Placa(valor="XYZ9W87"),
                marca="VW",
                modelo="Gol",
                ano=2019,
            )
            sessao_insert.add(cliente)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            veiculo = carregado.veiculos[0]
            with pytest.raises(
                AttributeError, match="nao pode ser alterada apos criacao"
            ):
                veiculo.id = uuid4()


class TestAnonimizacaoLGPD:
    """Cobre o comportamento da reidratacao apos ``anonimizar_dados``.

    Apos a raw UPDATE escrever ``documento="ANONIMIZADO"`` /
    ``documento_hash="ANONIMIZADO:{cliente_id}"``, o ``Cliente`` deve
    voltar a memoria com um ``DocumentoAnonimizado`` no lugar do CPF/CNPJ.
    """

    def _inserir_tombstone_legado(
        self,
        engine: object,
        cliente_id: object,
        tipo_documento: str,
    ) -> None:
        """Simula o estado pos-``anonimizar_dados`` com raw INSERT.

        Reproduz exatamente as colunas que o repository grava — assim cobrimos
        a compatibilidade com linhas anonimizadas antes deste refactor (que
        permanecem com ``documento="ANONIMIZADO"`` literal).
        """
        with Session(engine) as sessao:  # type: ignore[arg-type]
            sessao.execute(
                clientes_table.insert().values(
                    id=cliente_id,
                    nome="ANONIMIZADO",
                    documento="ANONIMIZADO",
                    documento_hash=f"ANONIMIZADO:{cliente_id}",
                    tipo_documento=tipo_documento,
                    contato="anonimizado@anonimizado.local",
                    ativo=False,
                )
            )
            sessao.commit()

    def test_load_apos_anonimizar_retorna_documento_anonimizado_para_cpf(
        self, engine_sqlite: object
    ) -> None:
        cliente_id = uuid4()
        self._inserir_tombstone_legado(engine_sqlite, cliente_id, "cpf")

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert isinstance(carregado._documento, DocumentoAnonimizado)
            assert not isinstance(carregado._documento, CPF)
            assert carregado._documento.cliente_id == cliente_id

    def test_load_apos_anonimizar_retorna_documento_anonimizado_para_cnpj(
        self, engine_sqlite: object
    ) -> None:
        # Regressao do bug PR #78: cliente cujo documento original era CNPJ
        # era reidratado como CPF (via CPF.__new__), entao isinstance(doc, CNPJ)
        # virava False sem aviso. Apos o refactor, o tipo correto e
        # DocumentoAnonimizado independente do tipo original.
        cliente_id = uuid4()
        self._inserir_tombstone_legado(engine_sqlite, cliente_id, "cnpj")

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(Cliente, cliente_id)
            assert carregado is not None
            assert isinstance(carregado._documento, DocumentoAnonimizado)
            assert not isinstance(carregado._documento, CNPJ)
            assert not isinstance(carregado._documento, CPF)

    def test_resave_de_cliente_anonimizado_preserva_tombstone_unico(
        self, engine_sqlite: object
    ) -> None:
        # Anonimiza dois clientes e re-salva um. O before_update do mapping
        # NAO pode recalcular hash a partir do sentinela "ANONIMIZADO" — isso
        # geraria o mesmo hash para os dois clientes e violaria o UNIQUE.
        id_a = uuid4()
        id_b = uuid4()
        self._inserir_tombstone_legado(engine_sqlite, id_a, "cpf")
        self._inserir_tombstone_legado(engine_sqlite, id_b, "cnpj")

        with Session(engine_sqlite) as sessao:  # type: ignore[arg-type]
            cliente_a = sessao.get(Cliente, id_a)
            assert cliente_a is not None
            # Marca dirty: any write attribute triggers UPDATE on flush.
            object.__setattr__(cliente_a, "_nome", "ANONIMIZADO")
            sessao.flush()
            sessao.commit()

        with Session(engine_sqlite) as sessao_check:  # type: ignore[arg-type]
            hash_a = sessao_check.scalar(
                clientes_table.select()
                .with_only_columns(clientes_table.c.documento_hash)
                .where(clientes_table.c.id == id_a)
            )
            hash_b = sessao_check.scalar(
                clientes_table.select()
                .with_only_columns(clientes_table.c.documento_hash)
                .where(clientes_table.c.id == id_b)
            )
            assert hash_a == f"ANONIMIZADO:{id_a}"
            assert hash_b == f"ANONIMIZADO:{id_b}"
            assert hash_a != hash_b
