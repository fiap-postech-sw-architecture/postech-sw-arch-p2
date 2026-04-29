from __future__ import annotations

from uuid import uuid4

import pytest

from src.cliente_veiculo.dominio.documento_anonimizado import DocumentoAnonimizado


class TestDocumentoAnonimizado:
    def test_numero_retorna_sentinela(self) -> None:
        doc = DocumentoAnonimizado(cliente_id=uuid4())
        assert doc.numero == "ANONIMIZADO"

    def test_formatado_retorna_sentinela(self) -> None:
        doc = DocumentoAnonimizado(cliente_id=uuid4())
        assert doc.formatado() == "ANONIMIZADO"

    def test_mascarado_retorna_sentinela(self) -> None:
        doc = DocumentoAnonimizado(cliente_id=uuid4())
        assert doc.mascarado() == "ANONIMIZADO"

    def test_igualdade_por_cliente_id(self) -> None:
        cid = uuid4()
        a = DocumentoAnonimizado(cliente_id=cid)
        b = DocumentoAnonimizado(cliente_id=cid)
        assert a == b

    def test_desigualdade_por_cliente_id(self) -> None:
        a = DocumentoAnonimizado(cliente_id=uuid4())
        b = DocumentoAnonimizado(cliente_id=uuid4())
        assert a != b

    def test_hash_consistente(self) -> None:
        cid = uuid4()
        a = DocumentoAnonimizado(cliente_id=cid)
        b = DocumentoAnonimizado(cliente_id=cid)
        assert hash(a) == hash(b)

    def test_usavel_em_set(self) -> None:
        cid = uuid4()
        a = DocumentoAnonimizado(cliente_id=cid)
        b = DocumentoAnonimizado(cliente_id=cid)
        assert len({a, b}) == 1

    def test_imutabilidade(self) -> None:
        doc = DocumentoAnonimizado(cliente_id=uuid4())
        with pytest.raises(AttributeError):
            doc.cliente_id = uuid4()  # type: ignore[misc]

    def test_repr_inclui_cliente_id(self) -> None:
        cid = uuid4()
        doc = DocumentoAnonimizado(cliente_id=cid)
        r = repr(doc)
        assert "DocumentoAnonimizado" in r
        assert str(cid) in r

    def test_satisfaz_protocolo_documento(self) -> None:
        from src.cliente_veiculo.dominio.documento import Documento

        doc: Documento = DocumentoAnonimizado(cliente_id=uuid4())
        # Acesso aos tres membros do Protocol nao deve levantar.
        assert doc.numero == "ANONIMIZADO"
        assert doc.formatado() == "ANONIMIZADO"
        assert doc.mascarado() == "ANONIMIZADO"
