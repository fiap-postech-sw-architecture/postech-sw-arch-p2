#!/bin/bash
# Banner exibido na primeira inicializacao do postgres (quando o initdb
# roda os scripts de /docker-entrypoint-initdb.d/). Em restarts
# subsequentes o initdb e pulado e este script nao roda; nesses casos a
# SHA continua disponivel via:
#   docker inspect <image>                       (LABEL org.opencontainers.image.revision)
#   docker exec <ctr> printenv PYTSTOP_GIT_SHA
SHA_SHORT="${PYTSTOP_GIT_SHA:0:12}"
echo ">>> pytstop seeded DB | commit ${SHA_SHORT:-unknown} | ${PYTSTOP_GIT_DATE:-unknown}"
