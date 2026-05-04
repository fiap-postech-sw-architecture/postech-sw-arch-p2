#!/bin/bash
set -e

echo ">>> pytstop app | commit ${PYTSTOP_GIT_SHA:0:12} | ${PYTSTOP_GIT_DATE:-unknown}"

if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
else
  echo "Skipping migrations on startup. Run 'alembic upgrade head' explicitly during deploy or set RUN_MIGRATIONS_ON_STARTUP=true."
fi

if [ "${RUN_SEED_ON_STARTUP:-false}" = "true" ]; then
  echo "Running admin seed..."
  # Seed e' best-effort: falha (credencial ausente, placeholder, race de replica)
  # nao deve bloquear o boot da API.
  python scripts/seed_admin.py || echo "Admin seed nao concluiu - prosseguindo com startup."
else
  echo "Skipping admin seed. Set RUN_SEED_ON_STARTUP=true to create the initial admin user."
fi

exec uvicorn src.main:app --host 0.0.0.0 --port 8000
