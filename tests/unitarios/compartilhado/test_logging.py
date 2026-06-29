from __future__ import annotations

import io
import json
import logging
from typing import TYPE_CHECKING

import pytest
import structlog

from src.compartilhado.infraestrutura.logging import (
    adicionar_versao_imagem,
    configurar_logging,
    scrub_pii,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


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

    def test_adicionar_versao_imagem_injeta_git_sha_e_date(self) -> None:
        # Defaults vem do env do processo (PYTSTOP_GIT_SHA/DATE); em
        # tests sem essas vars setadas, valor esperado e "unknown".
        result = adicionar_versao_imagem(None, "info", {"event": "boot"})
        assert "git_sha" in result
        assert "git_date" in result

    def test_adicionar_versao_imagem_nao_sobrescreve_explicit(self) -> None:
        result = adicionar_versao_imagem(
            None, "info", {"event": "x", "git_sha": "explicit"}
        )
        assert result["git_sha"] == "explicit"

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


class TestScrubTelefone:
    """Telefone BR formatado deve ser mascarado; numero qualquer NAO (LGPD)."""

    @pytest.mark.parametrize(
        "telefone",
        [
            "(11) 99999-0000",
            "(11) 9999-0000",
            "+55 11 99999-0000",
            "+55 (11) 99999-0000",
            "11 99999-0000",
        ],
    )
    def test_telefone_formatado_mascarado(self, telefone: str) -> None:
        event_dict: dict[str, object] = {"event": f"contato {telefone}"}
        result = scrub_pii(None, "info", event_dict)
        text = str(result["event"])
        assert telefone not in text
        assert "***" in text

    @pytest.mark.parametrize(
        "nao_telefone",
        [
            "id 12345",  # id curto
            "valor R$ 1500.00",  # preco
            "ordem 998877",  # numero de ordem
            "ano 2026",
            "porta 8000",
        ],
    )
    def test_nao_telefone_preservado(self, nao_telefone: str) -> None:
        # Guard contra falso-positivo: numeros que nao sao telefone ficam intactos.
        event_dict: dict[str, object] = {"event": nao_telefone}
        result = scrub_pii(None, "info", event_dict)
        assert str(result["event"]) == nao_telefone


class TestScrubChavesSensiveis:
    """Denylist de chaves: o VALOR e mascarado pelo nome do campo, nao por regex."""

    @pytest.mark.parametrize(
        "chave",
        [
            "password",
            "senha",
            "token",
            "secret",
            "authorization",
            "refresh_token",
            "access_token",
            "api_key",
        ],
    )
    def test_chave_sensivel_mascara_valor(self, chave: str) -> None:
        event_dict: dict[str, object] = {chave: "super-secreto-xyz"}
        result = scrub_pii(None, "info", event_dict)
        assert "super-secreto-xyz" not in str(result[chave])
        assert result[chave] == "***"

    def test_chave_sensivel_case_insensitive(self) -> None:
        event_dict: dict[str, object] = {"Authorization": "Bearer abc.def.ghi"}
        result = scrub_pii(None, "info", event_dict)
        assert "abc.def.ghi" not in str(result["Authorization"])

    def test_chave_sensivel_aninhada(self) -> None:
        event_dict: dict[str, object] = {
            "payload": {"user": "joao", "password": "hunter2"}
        }
        result = scrub_pii(None, "info", event_dict)
        inner = result["payload"]
        assert inner["user"] == "joao"  # type: ignore[index]
        assert "hunter2" not in str(inner["password"])  # type: ignore[index]

    def test_chave_nao_sensivel_preservada(self) -> None:
        event_dict: dict[str, object] = {"username": "joao", "count": 3}
        result = scrub_pii(None, "info", event_dict)
        assert result["username"] == "joao"
        assert result["count"] == 3


@pytest.fixture
def logging_pipeline() -> Iterator[io.StringIO]:
    """Configura o pipeline real e captura o stdout do root logger.

    Restaura o estado anterior do structlog/root logger no teardown para
    nao vazar configuracao entre testes (configurar_logging instala um
    handler no root).
    """
    root = logging.getLogger()
    handlers_anteriores = root.handlers[:]
    nivel_anterior = root.level
    config_anterior = structlog.get_config()

    buffer = io.StringIO()
    configurar_logging(stream=buffer)
    try:
        yield buffer
    finally:
        root.handlers = handlers_anteriores
        root.setLevel(nivel_anterior)
        structlog.configure(**config_anterior)


class TestPipelineMascaraTraceback:
    """O traceback (chave `exception`) deve sair mascarado pelo pipeline real.

    Cobre o bug central da issue #86: `scrub_pii` rodava ANTES de
    `format_exc_info`, entao a chave `exception` (montada por format_exc_info)
    escapava do mascaramento. Apos o reorder, o traceback e mascarado.
    """

    def test_excecao_com_pii_no_traceback_structlog(
        self, logging_pipeline: io.StringIO
    ) -> None:
        log = structlog.get_logger("test.pipeline")
        try:
            raise RuntimeError(
                "cliente CPF 123.456.789-00 email joao@example.com tel (11) 99999-0000"
            )
        except RuntimeError:
            log.exception("falha no processamento")

        saida = logging_pipeline.getvalue()
        assert saida, "pipeline nao emitiu nada"
        # A chave exception precisa existir (format_exc_info rodou)...
        registro = json.loads(saida.strip().splitlines()[-1])
        assert "exception" in registro
        # ...e o traceback nao pode conter PII crua.
        assert "123.456.789-00" not in saida
        assert "joao@example.com" not in saida
        assert "(11) 99999-0000" not in saida

    def test_excecao_com_pii_no_traceback_stdlib(
        self, logging_pipeline: io.StringIO
    ) -> None:
        # Caminho do handler 500 (error_handler.py): logger STDLIB, nao structlog.
        # Deve passar pelo ProcessorFormatter (foreign_pre_chain) e ser scrubado.
        stdlogger = logging.getLogger("test.stdlib.handler500")
        try:
            raise ValueError("documento 987.654.321-00 contato +55 11 98888-7777")
        except ValueError:
            stdlogger.exception("Erro interno (request_id=abc)")

        saida = logging_pipeline.getvalue()
        assert saida, "pipeline stdlib nao emitiu nada"
        assert "987.654.321-00" not in saida
        assert "+55 11 98888-7777" not in saida
        # Confirma que o traceback foi de fato renderizado (nao so a mensagem).
        registro = json.loads(saida.strip().splitlines()[-1])
        assert "exception" in registro

    def test_stdlib_log_simples_e_scrubado(self, logging_pipeline: io.StringIO) -> None:
        # Log stdlib sem excecao (ex.: uvicorn access log) tambem e scrubado.
        logging.getLogger("uvicorn.access").warning(
            "request de joao@example.com cpf 111.222.333-44"
        )
        saida = logging_pipeline.getvalue()
        assert "joao@example.com" not in saida
        assert "111.222.333-44" not in saida

    def test_uvicorn_loggers_religados_ao_root(self) -> None:
        # uvicorn instala handler proprio + propagate=False; configurar_logging
        # deve limpar o handler cru e religar propagate para o scrubber do root.
        root = logging.getLogger()
        handlers_anteriores = root.handlers[:]
        nivel_anterior = root.level
        config_anterior = structlog.get_config()

        # Simula o estado que o uvicorn deixa: handler proprio + propagate desligado.
        acc = logging.getLogger("uvicorn.access")
        handlers_acc_anteriores = acc.handlers[:]
        propagate_acc_anterior = acc.propagate
        handler_cru = logging.StreamHandler(io.StringIO())
        acc.handlers = [handler_cru]
        acc.propagate = False

        buffer = io.StringIO()
        try:
            configurar_logging(stream=buffer)
            # O handler cru do uvicorn foi removido e propagate religado.
            assert handler_cru not in acc.handlers
            assert acc.handlers == []
            assert acc.propagate is True

            acc.info("GET /clientes?cpf=123.456.789-00")
            saida = buffer.getvalue()
            # Saiu pelo scrubber do root (e nao pelo handler cru do uvicorn).
            assert "123.456.789-00" not in saida
            assert handler_cru.stream.getvalue() == ""  # type: ignore[attr-defined]
        finally:
            root.handlers = handlers_anteriores
            root.setLevel(nivel_anterior)
            acc.handlers = handlers_acc_anteriores
            acc.propagate = propagate_acc_anterior
            structlog.configure(**config_anterior)
