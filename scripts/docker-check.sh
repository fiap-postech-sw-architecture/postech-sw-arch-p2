#!/bin/bash
# Detecta o socket do Docker e exporta DOCKER_HOST se necessario.
# Uso: source scripts/docker-check.sh && docker compose up -d

_docker_check_finish() {
  local status="$1"
  if [ "${BASH_SOURCE[0]}" != "$0" ]; then
    return "$status"
  fi
  exit "$status"
}

docker_check_main() {
  if [ -n "$DOCKER_HOST" ]; then
    _docker_check_finish 0
    return 0
  fi

  local -a candidates=(
    "$HOME/.docker/run/docker.sock"
    "$HOME/.docker/desktop/docker.sock"
    "/var/run/docker.sock"
    "$HOME/.colima/default/docker.sock"
  )
  local sock

  for sock in "${candidates[@]}"; do
    if [ -S "$sock" ]; then
      export DOCKER_HOST="unix://$sock"
      echo "Docker socket encontrado: $sock" >&2
      _docker_check_finish 0
      return 0
    fi
  done

  echo "ERRO: Nenhum socket Docker encontrado." >&2
  echo "" >&2
  echo "Verifique se o Docker esta rodando e consulte o README (secao Troubleshooting)." >&2
  _docker_check_finish 1
}

docker_check_main
