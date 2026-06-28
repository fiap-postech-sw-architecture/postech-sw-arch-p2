#!/bin/bash
set -e

echo ">>> pytstop app | commit ${PYTSTOP_GIT_SHA:0:12} | ${PYTSTOP_GIT_DATE:-unknown}"

# Migrate+seed gated por env, ligados no compose/`make up` (container unico,
# sem corrida). No cluster k8s a migracao roda no Job dedicado pytstop-migrate
# antes do rollout (TD-015), entao o configmap fixa RUN_MIGRATIONS_ON_STARTUP=
# false e estes blocos viram no-op no pod.
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

# --no-proxy-headers: a app gerencia o trust de X-Forwarded-For explicitamente
# via TRUSTED_PROXIES (ProxyHeadersMiddleware proprio, testado). Esta flag
# desliga a camada implicita do uvicorn (proxy_headers=True +
# forwarded_allow_ips="127.0.0.1" por padrao desde 0.44 — confiaria no XFF de
# peers loopback), para o comportamento em runtime casar com os testes e o
# default documentado (XFF ignorado quando TRUSTED_PROXIES vazio).
exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
