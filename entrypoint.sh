#!/bin/bash
set -e

if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
else
  echo "Skipping migrations on startup. Run 'alembic upgrade head' explicitly during deploy or set RUN_MIGRATIONS_ON_STARTUP=true."
fi

exec uvicorn src.main:app --host 0.0.0.0 --port 8000
