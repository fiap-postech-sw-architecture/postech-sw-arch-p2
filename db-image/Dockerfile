FROM postgres:16

ARG GIT_SHA=unknown
ARG GIT_DATE=unknown

LABEL org.opencontainers.image.title="postech-sw-arch-p1 seeded DB" \
      org.opencontainers.image.source="https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1" \
      org.opencontainers.image.description="Postgres 16 com dump da DB seedada (pytstop) via make update-ghcr." \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${GIT_DATE}"

ENV POSTGRES_DB=pytstop \
    POSTGRES_USER=pytstop \
    POSTGRES_PASSWORD=pytstop \
    PYTSTOP_GIT_SHA="${GIT_SHA}" \
    PYTSTOP_GIT_DATE="${GIT_DATE}"

COPY 00-init.sql /docker-entrypoint-initdb.d/00-init.sql
COPY 99-version.sh /docker-entrypoint-initdb.d/99-version.sh
