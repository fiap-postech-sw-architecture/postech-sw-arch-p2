# Scans de Segurança — Fechamento da Fase 2

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)

> **Versão**: 1.0 — bateria executada em 12/06/2026 como hardening de fechamento da fase 2. Complementa o [relatório de vulnerabilidades](relatorio-vulnerabilidades.md) da fase 1, que permanece válido para o escopo do MVP.

## Escopo

Reexecução dos scans automatizados de segurança sobre o código da fase 2 (RF-020..024, RNF-017..024): análise estática (bandit), auditoria de dependências (pip-audit) e detecção de segredos (gitleaks, working tree + histórico completo). Trivy e OWASP ZAP não foram reexecutados nesta bateria — a imagem runtime e a superfície HTTP foram auditadas na fase 1 e os deltas da fase 2 (rotas novas, OTel opcional) estão cobertos pelos demais scans e pela suíte de testes.

> **Nota:** o `relay/` e o `k8s/redis.yaml` (PRs [#56](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/56), [#62](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/62)) são posteriores a esta bateria de 12/06 e não foram cobertos por ela; o código do `relay/` segue coberto pelo gate `make security` (o bandit varre `src/ ui/ relay/`) no CI de cada PR.

## Resumo

| Ferramenta | Versão | Alvo | Resultado |
|---|---|---|---|
| bandit | 1.9.4 | `src/` + `ui/` (10.828 LoC) | **0 high / 0 medium**; 1 low aceito (detalhe abaixo) |
| pip-audit | 2.10.1 | ambiente do projeto sincronizado do `uv.lock` | 11 advisories em 5 pacotes → **corrigidos por upgrade**; re-scan limpo |
| gitleaks | 8.30.1 | working tree (`--no-git`) e histórico (`--log-opts="--all"`, 164 commits) | **0 leaks** após allowlist documentada |

## Análise Estática (bandit)

Gate do projeto (`make security`): `bandit -r src/ ui/ -c pyproject.toml --severity-level high` — **nenhum achado high**. A varredura completa (sem filtro de severidade) registra um único achado de severidade **low**:

| Arquivo | ID | Severidade | Análise |
|---|---|---|---|
| `ui/config.py:52` | B105 (hardcoded password) | Low / Medium | Fallback dev-only do `storage_secret` da UI NiceGUI, usado somente quando `UI_STORAGE_SECRET` não está definido. A UI é dev-only por design (não sobe em produção) e o próprio valor se documenta (`...-change-for-public-deploy`). Aceito. |

Reprodução:

```bash
make security
```

## Auditoria de Dependências (pip-audit)

Execução em ambiente efêmero (sem poluir o `.venv`), auditando as dependências resolvidas do projeto:

```bash
uv run --with pip-audit pip-audit
```

**Resultado inicial**: 11 advisories (9 IDs únicos) em 5 pacotes. **Ação: upgrade no `uv.lock`** — todos os fixes eram patch/minor, sem mudança de API para o nosso uso:

| Pacote | Versão | Advisories | Fix aplicado | Relevância para o projeto |
|---|---|---|---|---|
| pyjwt | 2.12.1 | PYSEC-2026-175/177/178/179 | **2.13.0** | Biblioteca central da autenticação (ADR-004). Os CVEs atingem `PyJWKClient`/JWKS e JWS destacado (`b64: false`) — fluxos que não usamos (HS256 com segredo estático) — mas, por ser o componente crítico de auth, o upgrade é obrigatório. |
| starlette | 1.0.0 | PYSEC-2026-161 | **1.0.1** | Base do FastAPI. Header `Host` malformado podia divergir `request.url.path` do path roteado, com potencial bypass de checagens path-based. Fixado na versão exata de correção para minimizar drift no fechamento. |
| urllib3 | 2.6.3 | PYSEC-2026-141/142 | **2.7.0** | Transitiva. DoS por descompressão e forward de headers sensíveis em redirect via API low-level — fluxos não exercitados pelo runtime, corrigidos por higiene. |
| idna | 3.11 | CVE-2026-45409 | **3.18** | Transitiva. DoS por entradas longas em `idna.encode()`; entradas do app são limitadas por validação Pydantic. |
| mako | 1.3.11 | CVE-2026-44307 | **1.3.12** | Transitiva (Alembic). Path traversal de templates apenas em Windows; runtime é container Linux e templates não são controlados por usuário. |

**Re-scan pós-upgrade**: `No known vulnerabilities found` (o pacote local `pytstop` é pulado por não estar no PyPI — esperado). Suíte completa verde após o bump (1426 testes unitários + 136 de integração), validando que os upgrades não regrediram comportamento.

## Detecção de Segredos (gitleaks)

Working tree (inclui arquivos não versionados) e histórico completo:

```bash
gitleaks detect --source . --no-git --config .gitleaks.toml --no-banner --redact
gitleaks detect --source . --log-opts="--all" --config .gitleaks.toml --no-banner --redact
```

**Resultado inicial**: 6 findings no working tree, todos falsos positivos ou valores de demo deliberados. Tratamento: allowlist em `.gitleaks.toml`, cada entrada com comentário justificando (Caso D do workflow A/B/C/D da fase 1):

| Finding | Tratamento |
|---|---|
| `db-image/docker-compose.yml` — `ENCRYPTION_KEY` Fernet | **N/A** — o `db-image/` (fast-check da fase 1) foi removido do repo ([TD-018](../tech-debt/README.md)); o arquivo não existe mais e a entrada da allowlist foi retirada do `.gitleaks.toml`. |
| `docs/seguranca/trivy-image-report.json` (2×) | Digests/hashes de pacotes no relatório do trivy detectados como `generic-api-key`; não são segredos. Allowlist por path. |
| `infra/terraform.tfstate.backup` (2× private-key) | Estado local do Terraform com credenciais do cluster kind descartável de dev. Gitignored (`infra/.gitignore`) — nunca chega ao repo; aparece só no scan `--no-git`. Allowlist por path (idem para o kubeconfig `infra/pytstop-config` que o provider kind grava no apply). |
| `docs/entrega/fase2/roteiro-video.md` — header `X-Webhook-Token` | Token de demo do webhook de decisão de orçamento (RF-022), valor auto-documentado (`demo-webhook-orcamento-nao-usar-em-producao`), o mesmo default de dev do compose/k8s. Allowlist por regex do valor literal. |

**Resultado pós-allowlist**: **0 leaks** no working tree e **0 leaks** no histórico (164 commits).

## Relação com Outros Documentos

- [Relatório de vulnerabilidades (fase 1)](relatorio-vulnerabilidades.md) — baseline OWASP API Top 10, trivy, ZAP e SonarQube
- [Plano de segurança](plano-seguranca.md) — modelo de ameaças e controles
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) — pipeline de segurança em camadas
- [Dívida técnica](../tech-debt/README.md) — débitos de segurança aceitos e rastreados

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)
