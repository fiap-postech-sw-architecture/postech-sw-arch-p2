from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import MutableMapping

_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Cap on recursion depth when scrubbing nested structures. Guards against
# pathological or cyclic structured log payloads without sacrificing coverage
# of realistic nesting (events usually nest 2-3 levels deep at most).
_MAX_SCRUB_DEPTH = 6


def _mask_cpf(match: re.Match[str]) -> str:
    raw = match.group().replace(".", "").replace("-", "")
    return f"***.***.{raw[6:9]}-**"


def _mask_cnpj(match: re.Match[str]) -> str:
    raw = match.group().replace(".", "").replace("/", "").replace("-", "")
    return f"**.***.{raw[4:7]}/****-**"


def _mask_email(match: re.Match[str]) -> str:
    email = match.group()
    local, domain = email.split("@", 1)
    masked_local = local[0] + "***" if local else "***"
    return f"{masked_local}@{domain}"


def _mask_string(value: str) -> str:
    value = _CPF_PATTERN.sub(_mask_cpf, value)
    value = _CNPJ_PATTERN.sub(_mask_cnpj, value)
    return _EMAIL_PATTERN.sub(_mask_email, value)


def _scrub_value(value: Any, depth: int) -> Any:  # noqa: ANN401
    # Recursivamente normaliza qualquer estrutura JSON-like; o tipo de entrada
    # nao e conhecivel a priori, dai o Any.
    if depth >= _MAX_SCRUB_DEPTH:
        return value
    if isinstance(value, str):
        return _mask_string(value)
    if isinstance(value, dict):
        return {k: _scrub_value(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(item, depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_value(item, depth + 1) for item in value)
    return value


def scrub_pii(
    _logger: Any,  # noqa: ANN401  # structlog bound logger; nao inspecionado
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Structlog processor que mascara CPF, CNPJ e email em todo o event_dict.

    Percorre recursivamente strings, dicts, listas e tuplas ate `_MAX_SCRUB_DEPTH`
    para pegar PII em payloads estruturados. Aplicado automaticamente pelo pipeline
    de logging para impedir vazamento de PII em logs (LGPD).
    """
    for key, value in event_dict.items():
        event_dict[key] = _scrub_value(value, depth=0)
    return event_dict


def configurar_logging() -> None:
    """Configura structlog: JSON output, timestamps ISO e scrub automatico de PII."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            scrub_pii,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
