from __future__ import annotations

from src.compartilhado.infraestrutura.logging import (
    configurar_logging,
    scrub_pii,
)


class TestLogging:
    def test_scrub_cpf(self) -> None:
        event_dict: dict[str, object] = {"event": "CPF 123.456.789-00"}
        result = scrub_pii(None, "info", event_dict)
        assert "123.456.789-00" not in str(result["event"])
        assert "***" in str(result["event"])

    def test_scrub_cnpj(self) -> None:
        event_dict: dict[str, object] = {"event": "CNPJ 12.345.678/0001-90"}
        result = scrub_pii(None, "info", event_dict)
        assert "12.345.678/0001-90" not in str(result["event"])

    def test_scrub_email(self) -> None:
        event_dict: dict[str, object] = {"event": "Email user@example.com"}
        result = scrub_pii(None, "info", event_dict)
        assert "user@example.com" not in str(result["event"])
        assert "u***@example.com" in str(result["event"])

    def test_scrub_non_string_values(self) -> None:
        event_dict: dict[str, object] = {"count": 42}
        result = scrub_pii(None, "info", event_dict)
        assert result["count"] == 42

    def test_configurar_logging(self) -> None:
        configurar_logging()

    def test_scrub_cpf_sem_pontuacao(self) -> None:
        event_dict: dict[str, object] = {"event": "CPF 12345678900"}
        result = scrub_pii(None, "info", event_dict)
        assert "12345678900" not in str(result["event"])

    def test_scrub_cnpj_sem_pontuacao(self) -> None:
        event_dict: dict[str, object] = {"event": "CNPJ 12345678000190"}
        result = scrub_pii(None, "info", event_dict)
        assert "12345678000190" not in str(result["event"])

    def test_scrub_recursivo_em_dict_aninhado(self) -> None:
        event_dict: dict[str, object] = {
            "payload": {
                "cliente": {
                    "cpf": "123.456.789-00",
                    "email": "joao@example.com",
                }
            }
        }
        result = scrub_pii(None, "info", event_dict)
        cliente = result["payload"]["cliente"]  # type: ignore[index]
        assert "123.456.789-00" not in str(cliente["cpf"])
        assert "joao@example.com" not in str(cliente["email"])

    def test_scrub_recursivo_em_lista(self) -> None:
        event_dict: dict[str, object] = {
            "itens": [
                {"cpf": "123.456.789-00"},
                "CNPJ 12.345.678/0001-90",
            ]
        }
        result = scrub_pii(None, "info", event_dict)
        itens = result["itens"]
        assert "123.456.789-00" not in str(itens)
        assert "12.345.678/0001-90" not in str(itens)

    def test_scrub_recursivo_em_tupla(self) -> None:
        event_dict: dict[str, object] = {
            "pair": ("user@example.com", "other-value"),
        }
        result = scrub_pii(None, "info", event_dict)
        pair = result["pair"]
        assert "user@example.com" not in str(pair)
        assert "u***@example.com" in str(pair)

    def test_scrub_respeita_profundidade_maxima(self) -> None:
        # Deeply nested: 8 levels deep. _MAX_SCRUB_DEPTH=6 means level 7+ is skipped.
        deep: dict[str, object] = {"cpf": "123.456.789-00"}
        for _ in range(8):
            deep = {"next": deep}
        event_dict: dict[str, object] = {"root": deep}
        # Must not raise / hang; output may still contain the PII at the deepest level.
        result = scrub_pii(None, "info", event_dict)
        assert "root" in result
