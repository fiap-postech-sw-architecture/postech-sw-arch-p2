# Aprovação e recusa externas de orçamento via token dedicado

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Aceita (autenticação **evoluída** por TD-027 — ver Atualização)
* Data: 2026-06-12

> **Atualização (TD-027, jun/2026).** A autenticação do canal externo evoluiu do
> **token estático** (`X-Webhook-Token`, comparado com `secrets.compare_digest`)
> para **assinatura HMAC por requisição**: o chamador envia `X-Webhook-Signature`
> (HMAC-SHA256 de `{ordem_id}.{timestamp}.` + body) e `X-Webhook-Timestamp`. O
> `ORCAMENTO_WEBHOOK_TOKEN` passa a ser a **chave HMAC** (não trafega mais). Isso
> **limita** **replay** (a janela de ±5 min expira a assinatura capturada;
> replay residual dentro da janela é aceito — TLS + rate-limit mitigam, um
> nonce-store fica fora de escopo do MVP) e fecha **adulteração** do corpo —
> exatamente a "Assinatura HMAC por request" listada
> abaixo como alternativa, agora adotada. Implementação:
> `webhook_signature.assinar_payload_webhook` +
> `router_publico.validar_assinatura_webhook`. O comportamento 503 (canal
> desabilitado sem segredo) e o 401 (credencial inválida) permanecem.

## Contexto e Problema

O RF-022 do [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md) exige "endpoint para notificações **externas** de aprovação ou recusa" do orçamento, com critério de aceite explícito: "chamada externa autenticada por credencial própria (não JWT de admin) aprova ou recusa a OS em `AGUARDANDO_APROVACAO`; recusa leva a OS a um estado terminal ou de retrabalho definido em ADR; tentativas em estado inválido retornam 409/422" (gap analysis, §3). A [RFC-002 §8](../../rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) ratifica o desenho: "novo endpoint para notificações externas de aprovação ou recusa, autenticado por token próprio guardado em Secret (seção 6), fora do RBAC interno".

Já existe um precedente de canal externo sem JWT no projeto: a consulta pública de acompanhamento por placa + documento (`src/compartilhado/interfaces/router_publico.py:51-96`), fora do middleware de auth e protegida por rate limit do slowapi. O novo endpoint segue o mesmo trilho.

O estado atual da decisão de orçamento é todo interno:

- **Aprovação** é admin-only via JWT: `POST /{ordem_id}/aprovacao` (`src/ordem_servico/interfaces/router.py:281-294`, `Depends(exigir_papel("admin"))`), delegando a `AprovarOrcamento` (`src/ordem_servico/aplicacao/use_cases.py:418-454`), que reserva estoque e transita para `EM_EXECUCAO`.
- **Recusa do orçamento inicial não existe**: o que há é o cancelamento genérico admin-only (`router.py:329-343` → `CancelarOrdem`, `use_cases.py:515-565`) e a rejeição do orçamento **complementar** (`router.py:378-391` → `RejeitarOrcamentoComplementar`, `use_cases.py:627-653`), que devolve a OS a `EM_EXECUCAO` mantendo o escopo originalmente aprovado.
- A `MaquinaDeStatus` já admite as transições necessárias — nenhuma transição nova é preciso: `AGUARDANDO_APROVACAO → {EM_EXECUCAO, CANCELADA}` (`src/ordem_servico/dominio/maquina_de_status.py:33-38`) e `AGUARDANDO_APROVACAO_COMPLEMENTAR → {EM_EXECUCAO, CANCELADA}` (`maquina_de_status.py:46-51`). O gap analysis previa "nova transição de recusa na MaquinaDeStatus", mas a verificação no código mostra que `CANCELADA` já é alcançável dos dois estados de espera.

**Como expor a decisão externa (aprovar/recusar) com autenticação própria, e qual o destino da recusa?**

## Decisão

Endpoint **`POST /api/v1/publico/ordens-de-servico/{ordem_id}/decisao-orcamento`** no router público existente (`src/compartilhado/interfaces/router_publico.py`), com corpo `{"decisao": "aprovada" | "recusada"}` e três pilares:

1. **Semântica da decisão sobre o orçamento corrente** (caso de uso `DecidirOrcamento`, que compõe os casos de uso existentes em vez de duplicar regra):
   - `aprovada` em `AGUARDANDO_APROVACAO` → reusa `AprovarOrcamento` (reserva estoque, `EM_EXECUCAO`); em `AGUARDANDO_APROVACAO_COMPLEMENTAR` → reusa `AprovarOrcamentoComplementar` (`EM_EXECUCAO`) — espelha os endpoints internos correspondentes.
   - `recusada` → **`CANCELADA`** via `CancelarOrdem` com motivo fixo **"orcamento recusado pelo cliente"**, a partir de qualquer um dos dois estados de espera (transições legais citadas no contexto). Recusa externa é lida como desistência do cliente: o canal externo é binário e não tem como expressar a semântica parcial "rejeitar só o complementar e seguir com o escopo aprovado" — essa decisão operacional continua disponível internamente em `POST /{ordem_id}/rejeicao-complementar`. O reuso de `CancelarOrdem` também garante a liberação das reservas de estoque quando a recusa acontece em `AGUARDANDO_APROVACAO_COMPLEMENTAR` (`use_cases.py:552-560`).
   - OS fora de `AGUARDANDO_APROVACAO`/`AGUARDANDO_APROVACAO_COMPLEMENTAR` → `TransicaoStatusInvalidaException` → **409** no envelope de erro padrão (`src/compartilhado/interfaces/error_handler.py:25-33`). O guard é indispensável na recusa: sem ele, `CancelarOrdem` aceitaria cancelar uma OS `RECEBIDA` ou `EM_EXECUCAO` via canal externo.
   - Resposta 200 reusa a projeção pública `AcompanhamentoResponse` (status + situação + timestamps), sem expor itens, orçamento ou dados do cliente — mesma postura LGPD da consulta pública.
2. **Autenticação por token estático dedicado**, fora do RBAC/JWT interno: header `X-Webhook-Token` comparado em tempo constante (`secrets.compare_digest`) com a variável de ambiente `ORCAMENTO_WEBHOOK_TOKEN` (Secret no cluster — RFC-002 §6). Header ausente ou divergente → **401**. Token **não configurado** no servidor → **503 "canal externo de decisao de orcamento desabilitado"**: ausência de configuração é indisponibilidade do canal (estado do servidor), não falha de credencial do chamador — e não abre o canal sem credencial.
3. **Rate limit** pelo slowapi existente, no mesmo patamar do vizinho público de acompanhamento (10/minute por IP), mitigando força bruta contra o token e enumeração de `ordem_id`.

## Alternativas Consideradas

* Token estático dedicado em header próprio (escolhida)
* Reutilizar o JWT interno (usuário de serviço)
* Assinatura HMAC por request
* Manter a decisão apenas interna (sem endpoint externo)

### Token estático dedicado em header próprio

* Bom, porque cumpre literalmente o RF-022/RFC-002 §8: credencial própria, fora do RBAC, rotacionável por Secret sem deploy de código
* Bom, porque a validação é trivial de auditar (uma comparação em tempo constante) e testável sem infraestrutura
* Ruim, porque um token estático vazado autoriza qualquer chamada até a rotação — mitigado por rate limit, escopo mínimo do endpoint (uma rota, sem leitura de dados sensíveis) e transporte TLS

### Reutilizar o JWT interno (usuário de serviço)

* Bom, porque nenhum mecanismo novo de autenticação
* Ruim, porque o ator externo não é um usuário do sistema: exigiria criar usuário sintético, senha gerenciada e papel no RBAC — exatamente o acoplamento que o RF-022 manda evitar ("não JWT de admin")
* Ruim, porque tokens JWT expiram: o sistema externo precisaria do fluxo de login/refresh, inflando o contrato de integração

### Assinatura HMAC por request

* Bom, porque elimina o replay e o risco do segredo em trânsito (assina-se o corpo, o segredo nunca viaja)
* Ruim, porque adiciona complexidade real (canonicalização do corpo, janela de timestamp, tolerância de clock) sem exigência do requisito — fica registrado como evolução natural se o canal externo ganhar criticidade

### Manter a decisão apenas interna

* Bom, porque zero superfície nova de ataque
* Ruim, porque não cumpre o RF-022: "notificações externas" pressupõe um chamador de fora do RBAC; a aprovação admin-only existente já foi avaliada como insuficiente no gap analysis (§1, "Total para o canal externo")

## Consequências

### Positivas

* RF-022 atendido nos dois sentidos (aprovação e recusa) e nos dois estados de espera, incluindo o complementar
* Nenhuma transição nova na `MaquinaDeStatus` e nenhuma regra duplicada: `DecidirOrcamento` compõe `AprovarOrcamento`, `AprovarOrcamentoComplementar` e `CancelarOrdem`
* A recusa via `CancelarOrdem` emite `OrdemCanceladaEvent` com o motivo — o consumo de e-mail do [ADR-018](018-notificacao-email.md) cobre a notificação da recusa sem trabalho extra

### Negativas

* Token estático é o degrau mais simples de autenticação máquina-a-máquina: sem expiração nem prova de posse; rotação é operacional (trocar o Secret)
* Recusa externa do orçamento complementar cancela a OS inteira — comportamento deliberado (desistência), mas que exige comunicação clara ao integrador externo; a rejeição parcial permanece somente interna

### Neutras

* O rate limiter slowapi é in-memory por processo (RNF-024): com N réplicas o teto efetivo é N×limite — aceitável para o canal de demo, já documentado como pendência da fase
  * _Nota posterior:_ desde a [ADR-023](023-rate-limiter-storage-compartilhado.md) o rate limiter usa storage compartilhado (Redis), tornando o limite correto e global sob HPA — esta consequência reflete o estado no momento desta ADR (mantida como registro histórico).
* `ORCAMENTO_WEBHOOK_TOKEN` entra em `.env.dev.example`/docker-compose com valor de demonstração; o Secret K8s correspondente entra com os manifests (RNF-020)
* Auditoria da origem da decisão limita-se ao log estruturado do request (request_id + rota pública); trilha formal de auditoria fica fora do escopo

## Decisões Relacionadas

- [ADR-015](015-arquitetura-alvo-fase-2.md): o guard e o roteamento da decisão vivem em caso de uso (`aplicacao/`), não no router — regra de dependência das camadas
- [ADR-018](018-notificacao-email.md): os eventos emitidos pelas transições desta decisão (`OrcamentoAprovadoEvent`, `OrdemCanceladaEvent`) são matéria-prima da notificação por e-mail
- [RFC-002 §6 e §8](../../rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md): token do endpoint externo classificado como **Secret** no cluster; evolução da API da fase 2

## Notas

* Requisito formal: RF-022 ([gap-analysis-fase-2.md](../../../requisitos/fase2/gap-analysis-fase-2.md), §1 e §3); desenho de infraestrutura em [RFC-002](../../rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) §6 (secrets) e §8 (evolução da API)
* O destino dos estados extras na listagem (RN-020), que o gap analysis sugeria ratificar junto deste ADR, já foi realizado no RF-023 (listagem ordenada) e não é redecidido aqui

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
