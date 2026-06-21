# A fórmula do 10 — passo a passo da entrega

O que levou a fase 1 à nota máxima e foi repetido na fase 2. Não é um truque: é
disciplina em cada etapa + o review multi-perspectiva (Parte A do SKILL) +
evidência rastreável. Use como roteiro de ponta a ponta.

## Ciclo de vida (o passo a passo)

1. **Brainstorming → spec → plano** (superpowers): nada de código antes de spec +
   plano escritos. Decisões arquiteturais viram **ADR**; design integrado vira
   **RFC**. Nenhuma decisão grande sem ADR/RFC antes de implementar.
2. **Gap analysis vs enunciado:** cada requisito do desafio recebe um ID
   (`RF-NN`/`RNF-NN`/`RN-NN`), confrontado com o código real (`file:line`).
   Isto vira a espinha da rastreabilidade.
3. **Implementação por tarefa, com TDD:** cada tarefa = subagente implementer
   (teste primeiro) → spec-review → quality-review (perspectivas/canônico) → PR →
   CI verde → **merge commit** (não squash). Sem auto-merge sem autorização.
4. **Review multi-perspectiva** (a formula do 10) em cada artefato significativo —
   ver `protocolo-perspective-review.md`. Toda finding aplicada ou rejeitada com
   justificativa; #17 (AI-Trace) nunca pulado; Copilot Gap Analysis após o push.
5. **Hardening:** gate de cobertura ≥95% mantido; scans (bandit/pip-audit/gitleaks)
   limpos ou com exceção justificada; tech-debt registrado e sincronizado.
6. **Pacote de entrega:** `docs/entrega/faseN/` com `entrega-fase-N.md`
   (rastreabilidade requisito→PR→evidência→bloco do vídeo), `roteiro-video.md`
   (≤15min), `postman_collection.json`, README reescrito com o **diagrama**
   (mesma fonte Mermaid no README e no documento). PDF via Parte B.
7. **Submissão:** os 3 itens do enunciado (repo compartilhado com
   `soat-architecture`, diagrama, link do vídeo).

## Barra de qualidade que define o 10

- **Rastreabilidade total:** 100% dos requisitos obrigatórios mapeados a IDs e a
  PRs, com evidência no código e no vídeo. Nada "implícito".
- **Arquitetura defendida:** ADRs com contexto/decisão/consequências; RFC com
  diagrama; conformidade verificada (ex.: import-linter para camadas).
- **Testes:** unit + integração nos fluxos críticos, gate ≥95% real (não só
  declarado), E2E executável. Fluxos novos sempre com teste.
- **Segurança:** scans no CI, 0 HIGH (exceções justificadas e documentadas),
  segredos fora do código (Secret/env), PII protegida.
- **Operação:** Docker/compose com healthcheck, manifests K8s com probes+HPA,
  IaC (Terraform) documentado, CI/CD que builda→testa→imagem→deploy.
- **Texto sem cara de IA:** #17 (AI-Trace Removal) + #18 (Human Reader) deixam a
  documentação concisa, coerente e humana. Isto move a nota em entregas
  document-heavy mais do que se imagina.
- **Idioma híbrido (ADR-009):** termos de negócio em PT sem acento nos
  identificadores; padrões técnicos em EN; docs em PT com acento.
- **Entrega impecável:** PDF com diagrama renderizado (não bloco de código),
  links clicáveis, vídeo dentro de 15min demonstrando deploy + CI/CD + APIs +
  escalabilidade automática.

## Como as 18 perspectivas cobrem a barra

- **#1–#3 (Implementation/Staff/Architect):** correção, simplicidade, decisões
  arquiteturais e suas consequências.
- **#4, #10 (Test Engineer, Coverage):** fluxos críticos testados, gate real.
- **#5 (Security):** scans, segredos, PII, authz.
- **#6, #7 (PM, TPM):** requisitos cobertos, escopo e prazo, rastreabilidade.
- **#8 (Tech Doc Writer):** clareza e completude da documentação avaliada.
- **#9, #12 (DDD estratégico/tático):** linguagem ubíqua, contextos, agregados.
- **#11 (OOP):** coesão, acoplamento, design.
- **#13 (Maintenance):** custo de evolução, legibilidade.
- **#14 (AI Agent):** o código/é navegável por agentes (futuras fases).
- **#15 (Git/GitHub):** histórico, PRs, workflow (ver idas-e-voltas).
- **#16 (DevOps/SRE):** Docker, K8s, CI/CD, infra.
- **#17 (AI-Trace Removal):** remove marcas de IA — roda 2x (S1 e S3).
- **#18 (Human Reader):** concisão e coerência para um leitor humano.

Regra de ouro: **nenhuma finding silenciosamente ignorada**. É isso que separa
um "bom" de um 10 — o revisor (banca) não encontra nada que o seu próprio
processo não tenha endereçado primeiro.
