#!/bin/bash
# Mata instancias locais de `python -m ui` que segurariam a porta 8080
# antes do docker compose tentar bindar.
#
# Background: `docker compose down -v` so derruba containers do compose. Se
# voce rodou `make ui` (ou `python -m ui`) em outra aba e esqueceu de parar,
# esse processo continua vivo segurando 8080. O proximo `docker compose up
# -d` levanta o container UI mas o port mapping 0.0.0.0:8080->8080 falha
# silenciosamente (porta ocupada). Browser hits o processo antigo, dev ve
# bug "ainda presente" mesmo com fix em produ
# cao.
#
# Sourceavel ou executavel direto. Idempotente (no-op se nao houver match).

set -u

# pgrep -f matcha contra a linha de comando completa. `python -m ui` cobre
# tanto `uv run python -m ui` quanto `.venv/bin/python -m ui` direto. Sem
# filtro de PID: pgrep nunca lista a si proprio, e este shell (bash do
# script) nao casa com o padrao. O antigo `grep -v $$` filtrava por
# SUBSTRING e podia descartar PIDs legitimos que contivessem o PID do shell
# (ex.: $$=123 descartaria 1234).
pids=$(pgrep -f "python -m ui" 2>/dev/null || true)

if [ -n "$pids" ]; then
    # Lista um por linha pra debug claro.
    pid_list=$(echo "$pids" | tr '\n' ' ')
    echo ">> matando python -m ui locais que segurariam a porta 8080 (PIDs: $pid_list)"
    kill $pids 2>/dev/null || true
    # Da um respiro pro SO liberar o socket antes do compose tentar bindar.
    sleep 1
fi
