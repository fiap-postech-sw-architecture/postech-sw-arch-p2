from __future__ import annotations

from uuid import uuid4

from src.cliente_veiculo.dominio.placa import Placa
from src.cliente_veiculo.dominio.placa_anonimizada import PlacaAnonimizada


class TestPlacaAnonimizada:
    def test_valor_e_sentinela_sem_pii(self) -> None:
        p = PlacaAnonimizada(veiculo_id=uuid4())
        assert p.valor == "ANONIMIZADO"

    def test_nao_e_placa_real(self) -> None:
        p = PlacaAnonimizada(veiculo_id=uuid4())
        assert not isinstance(p, Placa)

    def test_repr_nao_vaza_placa(self) -> None:
        vid = uuid4()
        p = PlacaAnonimizada(veiculo_id=vid)
        assert "ANONIMIZADO" not in repr(p)  # repr expoe so o veiculo_id (nao PII)
        assert str(vid) in repr(p)

    def test_igualdade_por_veiculo_id(self) -> None:
        vid = uuid4()
        assert PlacaAnonimizada(veiculo_id=vid) == PlacaAnonimizada(veiculo_id=vid)
        assert PlacaAnonimizada(veiculo_id=vid) != PlacaAnonimizada(veiculo_id=uuid4())
