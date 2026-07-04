# NOT FOR PRODUCTION DEPLOY — dev/testing tool only.
# Esta imagem serve a UI de simulacao NiceGUI consumindo o backend
# PytStop via HTTP. Nao deve ser promovida para publicos externos.

FROM python:3.14-slim AS base

ARG GIT_SHA=unknown
ARG GIT_DATE=unknown

LABEL org.opencontainers.image.title="postech-sw-arch-p2 ui" \
      org.opencontainers.image.source="https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2" \
      org.opencontainers.image.description="NiceGUI sandbox/UI dev-only." \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${GIT_DATE}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTSTOP_GIT_SHA="${GIT_SHA}" \
    PYTSTOP_GIT_DATE="${GIT_DATE}"

# Instala uv via bin estatico.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

# UID/GID fixos (1001), mesmo padrao do Dockerfile do app: a UI dev tambem
# nao precisa (nem deve) rodar como root.
RUN groupadd -r -g 1001 pytstop && useradd -r -u 1001 -g pytstop pytstop

WORKDIR /app
# O NiceGUI cria `.nicegui/` (storage) no CWD em runtime: o DIRETORIO /app
# precisa ser gravavel pelo nao-root. Os arquivos copiados abaixo continuam
# de root (leitura basta) — chown nao-recursivo de proposito.
RUN chown pytstop:pytstop /app

# Aproveita cache em duas camadas: lock primeiro, fonte depois.
# --no-install-project: instala SO as dependencias — sem src/ presente nesta
# camada, instalar "o projeto" gerava um pacote vazio enganoso; em runtime os
# imports resolvem pelo CWD /app (python -m ui), nao por um install.
COPY pyproject.toml uv.lock ./
RUN uv sync --extra ui --frozen --no-dev --no-install-project

# Copia UI + src: alguns modulos da UI (maquina_estados, stepper_os,
# paginas/ordens_servico) importam `StatusOrdem` direto do dominio do
# backend para garantir drift-check estatico. Sem src/ a imagem nao
# sobe (ModuleNotFoundError: No module named 'src').
COPY ui /app/ui
COPY src /app/src

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

USER pytstop

# `bash -c` + `exec` pra que (1) o banner com a SHA seja logado em todo
# start (LABEL OCI cobre o caso "via docker inspect"; este cobre o log
# do container) e (2) sinais (SIGTERM) sejam propagados pro python sem
# proxy do shell.
CMD ["bash", "-c", "echo \">>> pytstop ui | commit ${PYTSTOP_GIT_SHA:0:12} | ${PYTSTOP_GIT_DATE:-unknown}\" && exec python -m ui"]
