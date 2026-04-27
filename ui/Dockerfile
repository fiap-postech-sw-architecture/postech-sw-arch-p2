# NOT FOR PRODUCTION DEPLOY — dev/testing tool only.
# Esta imagem serve a UI de simulacao NiceGUI consumindo o backend
# PytStop via HTTP. Nao deve ser promovida para publicos externos.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Instala uv via bin estatico.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# Aproveita cache em duas camadas: lock primeiro, fonte depois.
COPY pyproject.toml uv.lock ./
RUN uv sync --extra ui --frozen --no-dev

# Copia UI + src: alguns modulos da UI (maquina_estados, stepper_os,
# paginas/ordens_servico) importam `StatusOrdem` direto do dominio do
# backend para garantir drift-check estatico. Sem src/ a imagem nao
# sobe (ModuleNotFoundError: No module named 'src').
COPY ui /app/ui
COPY src /app/src

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

CMD ["python", "-m", "ui"]
