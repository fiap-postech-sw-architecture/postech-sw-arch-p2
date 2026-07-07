#!/usr/bin/env bash
# Gera o arquivo de segredos FORTES do ambiente cloud (ADR-025) se ainda
# nao existir. Idempotente: em re-runs reusa o arquivo, mantendo a
# ENCRYPTION_KEY estavel (senao a PII ja cifrada deixa de decifrar) e a
# senha do admin previsivel entre deploys do mesmo cluster.
#
# O `make cloud-up` fonte este arquivo e materializa os valores em Secrets
# do Kubernetes na hora do deploy -- os segredos NUNCA sao commitados
# (.env.cloud esta no .gitignore). Para o CD por OIDC (evolucao), os
# mesmos nomes vem do GitHub Environment `cloud`, nao deste arquivo.
#
# Uso: scripts/cloud-secrets.sh [caminho]   (default .env.cloud)
set -euo pipefail

f="${1:-.env.cloud}"

# Upgrade de arquivo existente: acrescenta chaves que versoes anteriores do
# script nao geravam (senhas de atendente/mecanico — ADR-025 adendo), sem
# tocar nas existentes (ENCRYPTION_KEY estavel).
if [ -f "$f" ]; then
  echo ">> $f ja existe -- reusando (apague para rotacionar todos os segredos)."
  for papel in ATENDENTE MECANICO; do
    if ! grep -q "^${papel}_PASSWORD=" "$f"; then
      echo "${papel}_PASSWORD=$(openssl rand -hex 24)" >> "$f"
      echo ">> ${papel}_PASSWORD acrescentada (upgrade)."
    fi
  done
  exit 0
fi

echo ">> gerando $f com segredos fortes..."

# Fernet key = urlsafe base64 de 32 bytes (o mesmo que Fernet.generate_key()).
# openssl + tr evita depender do python/cryptography no host.
jwt=$(openssl rand -hex 32)
enc=$(openssl rand -base64 32 | tr '+/' '-_')
webhook=$(openssl rand -hex 32)
pgpass=$(openssl rand -hex 16)
adminpass=$(openssl rand -hex 24)
atendentepass=$(openssl rand -hex 24)
mecanicopass=$(openssl rand -hex 24)

umask 077
cat > "$f" <<EOF
# Segredos do ambiente cloud de demonstracao (ADR-025). GERADO -- nao commitar.
# Apague este arquivo para rotacionar tudo no proximo 'make cloud-aks-up' /
# 'make vm-up' (que recria o ambiente do zero, entao a rotacao e' segura).
JWT_SECRET=$jwt
ENCRYPTION_KEY=$enc
ORCAMENTO_WEBHOOK_TOKEN=$webhook
POSTGRES_PASSWORD=$pgpass
ADMIN_EMAIL=admin@pytstop.dev
ADMIN_PASSWORD=$adminpass
ATENDENTE_PASSWORD=$atendentepass
MECANICO_PASSWORD=$mecanicopass
EOF

echo ">> $f criado (git-ignored)."
echo ">> ADMIN_EMAIL=admin@pytstop.dev"
echo ">> ADMIN_PASSWORD=$adminpass"
echo ">> guarde as senhas -- elas vivem em $f."
