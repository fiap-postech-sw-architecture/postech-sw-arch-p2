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

  # Windows (Git Bash / MSYS / Cygwin): Docker Desktop expoe o engine via
  # named pipe (\\.\pipe\docker_engine), nao Unix socket. O CLI do Docker
  # ja resolve isso por default — basta confirmar que `docker info`
  # responde, sem tentar achar arquivo de socket que nao existe nessa
  # plataforma.
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*)
      if docker info >/dev/null 2>&1; then
        _docker_check_finish 0
        return 0
      fi
      echo "ERRO: Docker Desktop nao parece estar rodando." >&2
      echo "" >&2
      echo "Abra o Docker Desktop e aguarde a baleia ficar estavel na bandeja." >&2
      _docker_check_finish 1
      return 1
      ;;
  esac

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
