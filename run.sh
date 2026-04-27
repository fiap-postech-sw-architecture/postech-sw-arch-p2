#!/usr/bin/env bash
# run.sh — fallback do Makefile para ambientes sem `make` (ex.: Git Bash
# no Windows). Espelha os targets de docker mais usados. Para os demais
# (lint/test/typecheck/etc.), use `uv run <ferramenta> ...` direto.
#
# Uso: ./run.sh <target>
# Requer: bash, docker, uv.

set -euo pipefail

ensure_env_dev() {
    if [ ! -f .env.dev ]; then
        cp .env.dev.example .env.dev
        echo ">> .env.dev criado a partir de .env.dev.example (dev defaults)."
        echo ">> Edite o arquivo antes de promover para qualquer ambiente nao-local."
    fi
}

ensure_docker() {
    # Espelha o que scripts/docker-check.sh faz (warnings sobre socket).
    if [ -f scripts/docker-check.sh ]; then
        # shellcheck disable=SC1091
        source scripts/docker-check.sh
    fi
}

case "${1:-help}" in
    up)
        ensure_env_dev
        ensure_docker
        bash scripts/kill-stale-ui.sh
        docker compose up -d
        ;;
    rebuild)
        ensure_env_dev
        ensure_docker
        bash scripts/kill-stale-ui.sh
        docker compose up -d --build --force-recreate
        ;;
    down)
        ensure_docker
        docker compose down
        ;;
    up-backend)
        ensure_env_dev
        ensure_docker
        docker compose up -d postgres app
        ;;
    seed-users)
        # Carrega .env.dev se existir e roda seed local.
        set -a
        [ -f .env ] && . ./.env
        [ -f .env.dev ] && . ./.env.dev
        set +a
        uv run python scripts/seed_usuarios.py
        ;;
    seed-users-docker)
        # Copia o script pro container em runtime e roda dali. Funciona
        # mesmo se a imagem do backend estiver stale.
        docker compose cp scripts/seed_usuarios.py app:/tmp/seed_usuarios.py
        docker compose exec app python /tmp/seed_usuarios.py
        ;;
    seed-demo)
        # Popula dados de demo (7 clientes, 10 veiculos, 8 servicos,
        # 14 itens, 8 OS em 7 estados) via API HTTP. Precisa do admin
        # criado antes (seed-users / seed-users-docker). Idempotente.
        # `--extra ui` e obrigatorio: seed_demo.py importa ui/cliente_api
        # (httpx + nicegui). Sem o extra, fresh venvs falham com
        # ModuleNotFoundError.
        set -a
        [ -f .env ] && . ./.env
        [ -f .env.dev ] && . ./.env.dev
        set +a
        uv run --extra ui python scripts/seed_demo.py
        ;;
    reset-db)
        # "Nuke e repopula" — single-command pra voltar pro zero. Faz:
        #   down -v + up -d --build + poll /saude + seed-users + seed-demo.
        # Use quando ENCRYPTION_KEY mudou entre restarts (CPFs ilegiveis),
        # quando quer DB limpo pra testar do zero com dados realistas, ou
        # apos git pull para rodar imagens frescas com DB virgem. NAO usa
        # prod. Pular seed-demo: export SKIP_DEMO=1 antes.
        ensure_env_dev
        ensure_docker
        echo ">> derrubando stack e apagando volume postgres_data..."
        docker compose down -v
        bash scripts/kill-stale-ui.sh
        echo ">> rebuildando imagens e subindo stack do zero..."
        docker compose up -d --build
        echo ">> aguardando /api/v1/saude responder 200..."
        for i in $(seq 1 30); do
            if curl -fsS http://localhost:8000/api/v1/saude >/dev/null 2>&1; then
                echo ">> backend respondendo em $i tentativa(s)."
                break
            fi
            if [ "$i" -eq 30 ]; then
                echo "!! backend nao respondeu em 60s — verifique docker compose logs app"
                exit 1
            fi
            sleep 2
        done
        echo ">> populando usuarios seed..."
        docker compose cp scripts/seed_usuarios.py app:/tmp/seed_usuarios.py
        docker compose exec -T app python /tmp/seed_usuarios.py
        if [ -z "${SKIP_DEMO:-}" ]; then
            echo ">> populando dados de demo (clientes/OS/catalogo/estoque)..."
            set -a
            [ -f .env ] && . ./.env
            [ -f .env.dev ] && . ./.env.dev
            set +a
            uv run --extra ui python scripts/seed_demo.py
        else
            echo ">> SKIP_DEMO=1: pulando seed de demo (banco so com usuarios)."
        fi
        echo ">> pronto. Abra http://localhost:8080/ e faca login como admin."
        ;;
    ui)
        # `--extra ui` traz nicegui + httpx (seriam ModuleNotFoundError em
        # fresh venv sem o extra ativo).
        uv run --extra ui python -m ui
        ;;
    help|-h|--help)
        cat <<HELP
Uso: ./run.sh <target>

Targets suportados:
  up                    postgres + backend + UI em containers
  rebuild               forca rebuild das imagens + recria containers
  down                  derruba todos os containers
  up-backend            so postgres + backend (sem UI container)
  seed-users            popula usuarios seed via Python local
  seed-users-docker     popula usuarios seed via container backend
  seed-demo             popula dados de demo (7 clientes, 8 OS em 7 estados etc.)
  reset-db              nuke e repopula: down -v + up --build + saude + seed-users + seed-demo
                        (SKIP_DEMO=1 pula o seed-demo)
  ui                    roda a UI localmente (python -m ui)
  help                  mostra esta ajuda

Para lint/test/typecheck/etc., use \`uv run <ferramenta>\` direto.
HELP
        ;;
    *)
        echo "Target desconhecido: $1"
        echo "Rode \`./run.sh help\` para ver os targets suportados."
        exit 1
        ;;
esac
