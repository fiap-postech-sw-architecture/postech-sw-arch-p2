# Roteiro do Vídeo — Fase 2

> [↑ Raiz do projeto](../../../README.md) · [↑ Entrega Fase 2](README.md)

> **Versão**: 1.0 — Fase 2.

Duração alvo: ~14min30s (folga dentro do limite de 15 min). O enunciado exige demonstrar: deploy da aplicação, execução do CI/CD, consumo das APIs e escalabilidade automática.

**Pré-gravação (não aparece no vídeo):**

- `make k8s-down` se houver cluster de sessão anterior (o bloco 2 grava o provisionamento do zero);
- Docker com memória suficiente para o cluster completo (no Colima: `colima start --memory 4`);
- abas prontas no browser: README do repo, aba Actions, Mailpit (`localhost:8025`), Jaeger (`localhost:16686`);
- ensaio completo do roteiro pelo menos uma vez (o `make cd-local` leva ~3-5 min em máquina fria).

## Estrutura

### 1. Visão geral + arquitetura (1 min)

- Apresentação: turma 15SOAT, grupo PytStop, fase 2 do Tech Challenge.
- Abrir o [README](../../../README.md) no GitHub: evolução da fase 1 — Clean Architecture verificada, Kubernetes com HPA, Terraform, CD com deploy real, e-mail de status e traces.
- Percorrer o diagrama Mermaid (renderizado pelo GitHub): pipeline → GHCR → cluster kind (Terraform: postgres + metrics-server; manifests: API + HPA + Mailpit + Jaeger).

**Evidência no ar**: diagrama de arquitetura visível e narrado.

### 2. Infraestrutura + deploy local (3 min)

Terminal na raiz do repo:

```bash
make cd-local
```

Narrar os estágios enquanto rolam (são os mesmos do CD — paridade local × pipeline):

1. `terraform apply` — cluster kind `pytstop` + namespace `pytstop-infra` + PostgreSQL StatefulSet (RNF-021);
2. build da imagem com tag por SHA + `kind load` (sem pull de registry);
3. metrics-server (pré-requisito do HPA);
4. `kubectl apply -f k8s/` — manifests do app;
5. Job `pytstop-migrate` (`alembic upgrade head` + seed) + `kubectl wait --for=condition=complete` — gate do schema antes do rollout (TD-015);
6. `set image` + rollout da API e do relay (sobem sobre o schema já migrado);
7. smoke test: `GET /api/v1/saude` → `{"status":"ok"}` na porta 18000.

Com o `cd-local` concluído:

```bash
kubectl --context kind-pytstop get pods -n pytstop
kubectl --context kind-pytstop get pods -n pytstop-infra
```

**Evidência no ar**: smoke OK no final do `make cd-local`; `pytstop-api`, `relay`, `redis`, `mailpit` e `jaeger` 1/1 Running em `pytstop`; `postgres-0` 1/1 Running em `pytstop-infra`.

### 3. CI/CD no GitHub Actions (2 min)

- Abrir a aba **Actions → workflow CD** e mostrar as execuções verdes na main:
  - [run 27450493913](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/27450493913) — primeiro deploy completo;
  - [run 27451618014](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/27451618014) — deploy com OTel/Jaeger.
- Entrar numa run e explicar os estágios ([cd.yml](../../../.github/workflows/cd.yml)):
  - job `image`: build da imagem e push no GHCR com **tag imutável por SHA do commit**;
  - job `deploy`: cluster kind **efêmero no runner** via Terraform → `kind load` → manifests → rollout → smoke test;
  - CI herdada (lint, mypy, bandit, testes com gate de 95%) bloqueia merge nos PRs.

**Evidência no ar**: duas runs verdes; logs do job `deploy` com `terraform apply` e smoke OK.

### 4. Consumo das APIs (4 min)

Port-forwards (terminais separados, deixar rodando):

```bash
kubectl --context kind-pytstop -n pytstop port-forward svc/pytstop-api 18000:8000
kubectl --context kind-pytstop -n pytstop port-forward svc/mailpit 8025:8025
```

Swagger em **http://localhost:18000/docs** (collection Postman equivalente versionada em [`docs/entrega/fase2/postman_collection.json`](postman_collection.json)). Login: `POST /api/v1/autenticacao/login` com `admin@pytstop.dev` / `pytstop-admin-demo-2026` → **Authorize** com o token.

**Preparação prévia (fora do ar, antes de gravar o bloco)**: cadastrar 1 cliente (com e-mail no contato), 1 veículo, 2 serviços e 1 item de estoque; criar 2 OS extras e avançá-las para status distintos (uma em diagnóstico, uma aguardando aprovação) para a listagem e a recusa externa terem matéria-prima.

Sequência gravada:

1. **RF-020 — abrir OS com serviços e peças**: `POST /api/v1/ordens-de-servico/` com `servicos` + `pecas` no payload → **201** com `id` único. Guardar o `id`.
2. **RF-021 — situação no vocabulário do challenge**: `GET /api/v1/ordens-de-servico/{id}` → campo `situacao: "Recebida"`; mencionar que a consulta pública (`GET /api/v1/acompanhamento?placa=...&documento=...`) devolve o mesmo rótulo.
3. **RF-023 — listagem ordenada**: `GET /api/v1/ordens-de-servico/` → ordem Em execução > Aguardando aprovação > Em diagnóstico > Recebida, mais antigas primeiro, sem finalizadas/entregues (exclusão lógica — `incluir_encerradas=true` mostra que continuam no banco).
4. **RF-022 — decisão externa de orçamento** (avançar a OS nova até `aguardando_aprovacao`: diagnóstico → orçamento). No terminal:

   ```bash
   curl -s -X POST "http://localhost:18000/api/v1/publico/ordens-de-servico/<OS_ID>/decisao-orcamento" \
     -H "X-Webhook-Token: demo-webhook-orcamento-nao-usar-em-producao" \
     -H "Content-Type: application/json" \
     -d '{"decisao": "aprovada"}'
   ```

   → situação vira "Em execução" (estoque reservado). Re-rodar a listagem: a OS aprovada agora abre a lista (prioridade máxima). Repetir na OS preparada em aguardando aprovação com `{"decisao": "recusada"}` → "Cancelada". Mostrar que sem o header o retorno é **401** (token dedicado, fora do RBAC interno — ADR-021).
5. **RF-024 — e-mail de status**: abrir **http://localhost:8025** (Mailpit) → um e-mail por transição do bloco (diagnóstico, orçamento disponível, Em execução na aprovação, Cancelada na recusa), com destinatário extraído do contato do cliente. Mencionar que o e-mail agora flui pela **Transactional Outbox** (evento gravado na mesma transação da mudança de OS) e é entregue pelo **relay** assíncrono, eliminando o dual-write (ADR-022).

**Evidência no ar**: 201 + id; `situacao` nos GETs; listagem na ordem da regra; aprovação e recusa externas com efeito; caixa de entrada do Mailpit com os e-mails.

### 5. Escalabilidade automática — HPA (3 min)

Num terminal, observar o HPA (RNF-020/RNF-023):

```bash
kubectl --context kind-pytstop get hpa -n pytstop -w
```

Noutro, gerar carga (comando do [k8s/README.md](../../../k8s/README.md); subir `gerador-carga-2`/`-3` se precisar de mais pressão):

```bash
kubectl --context kind-pytstop run gerador-carga -n pytstop --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://pytstop-api:8000/api/v1/saude > /dev/null; done"
```

Narrar: metrics-server alimenta o HPA; quando CPU cruza 70% (ou memória 80%) do request, as réplicas sobem de 1 em direção a 5; `kubectl get pods -n pytstop` mostra os pods novos atendendo a mesma carga (RNF-024 — JWT stateless, chave de cifra única via Secret). O rate limiter usa **storage compartilhado (Redis)** (ADR-023), então o limite é global e correto entre as réplicas (não ×réplicas); respostas `429` durante o loop seguem esperadas sob carga e também consomem CPU ([k8s/README.md](../../../k8s/README.md)). Encerrar a carga e mencionar o scale-down (janela de estabilização ~5 min — não esperar no ar):

```bash
kubectl --context kind-pytstop delete pod -n pytstop gerador-carga
```

**Evidência no ar**: coluna `TARGETS` do HPA subindo; `REPLICAS` 1→N; pods novos em Running.

### 6. Observabilidade — OTel + Jaeger (1 min)

```bash
kubectl --context kind-pytstop -n pytstop port-forward svc/jaeger 16686:16686
```

Abrir **http://localhost:16686** → serviço `pytstop-api` → *Find Traces* → abrir 1 trace de requisição do bloco 4: span do endpoint FastAPI com os spans das queries SQLAlchemy aninhados (ADR-020; instrumentação condicional — ligada só no cluster de demo).

**Evidência no ar**: um trace aberto com spans `fastapi` + `sqlalchemy`.

### 7. Encerramento (30 s)

- Qualidade sustentada na evolução: cobertura **95,3%** com gate de 95% na CI, contratos de camadas verificados por **import-linter** (Clean Architecture — ADR-015), scans de segurança herdados da fase 1 (bandit na CI; bateria completa em `docs/seguranca/`).
- Decisões registradas: ADRs 015–024 + RFC-002; rastreabilidade completa em [entrega-fase-2.md](entrega-fase-2.md).
- Repositório privado compartilhado com `soat-architecture`.

## Notas de Produção

- Terminal com fonte grande (14pt+); Swagger em tela cheia durante o bloco 4.
- Gravar o bloco 2 sem cortes (o apply é a prova do RNF-021); acelerar trechos de espera na edição com timestamp visível.
- Deixar os port-forwards rodando desde a preparação — não gravar a digitação deles.
- Conferir antes de gravar: `make cd-local` verde de ponta a ponta, Mailpit vazio (limpar caixa), Jaeger acessível.
- Ter os UUIDs da preparação (cliente, veículo, serviço, item) colados num rascunho para preencher payloads sem digitação ao vivo.

> [↑ Raiz do projeto](../../../README.md) · [↑ Entrega Fase 2](README.md)
