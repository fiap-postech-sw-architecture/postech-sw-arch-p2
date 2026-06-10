# Observabilidade com OpenTelemetry e Jaeger em escopo mínimo condicional

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Proposta
* Data: 2026-06-10

## Contexto e Problema

O Tech Challenge da fase 2 **não exige observabilidade**: nenhum requisito do [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md) ou do [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md) (RF-020–RF-024, RNF-017–RNF-024) menciona traces, métricas de aplicação ou logs estruturados. O OpenTelemetry, porém, é disciplina integral da fase — e o challenge "englobará os conhecimentos obtidos em todas as disciplinas da fase", valendo 60% da nota de todas elas (desafio, "Sobre o Tech Challenge"). Instrumentar a aplicação é, portanto, uma decisão de **diferencial**: custo e risco contra valor de demonstração para a banca.

O material distingue monitoramento (reativo) de observabilidade (investigativa) e organiza o tema nos três pilares — logs, métricas e traces (OpenTelemetry, Aula 01). O hands-on de partida é exatamente o caso do PytStop: aplicação Python com instrumentação automática exportando traces (Aula 01); o backend de tracing das aulas práticas é o Jaeger, consumindo OTLP do SDK — o Jaeger Client está obsoleto (Aula 02). O custo de entrada é baixo: a instrumentação automática de FastAPI e SQLAlchemy captura spans de cada endpoint e de cada query sem alteração de código.

Do outro lado da balança, o escopo obrigatório da fase já é grande — o gap analysis (risco 4) classifica o prazo como risco alto e manda cortar opcionais cedo. Hoje a aplicação não emite traces nem métricas de aplicação; a única telemetria prevista é o metrics-server do HPA (RNF-023), que é infraestrutura do cluster, não instrumentação.

**A fase 2 instrumenta a aplicação com OpenTelemetry — e, em caso afirmativo, com que escopo?**

## Decisão

**Incluir, em escopo mínimo e como onda final condicional**: instrumentação automática de FastAPI e SQLAlchemy exportando traces via OTLP para um **Jaeger no cluster** — executada **somente após os requisitos obrigatórios (RF-020–RF-024, RNF-017–RNF-024) estarem verdes**.

- **Escopo incluído**:
  - instrumentação automática (`opentelemetry-instrumentation-fastapi` e `opentelemetry-instrumentation-sqlalchemy`) — o ponto de partida que o material trata como obrigatório, por dar a visão geral instantânea com esforço mínimo (OpenTelemetry, Aulas 01 e 05); nenhuma camada interna importa OTel — telemetria é detalhe de borda ([ADR-015](015-arquitetura-alvo-fase-2.md));
  - exportação **OTLP**, o formato nativo recomendado (Aulas 01 e 02), com endpoint configurado por variável de ambiente — sem endpoint configurado, a instrumentação fica inerte, e compose e CI não pagam custo algum;
  - **Jaeger** (all-in-one, com receiver OTLP) como Deployment + Service no cluster kind, no mesmo padrão de workload de demo do Mailpit ([ADR-018](018-notificacao-email.md)), com UI acessada por port-forward na gravação do vídeo.
- **Escopo excluído, conscientemente**: Collector dedicado, métricas (Prometheus/Grafana), logs estruturados com correlação (Loki) e amostragem configurada. A exportação direta SDK→Jaeger contraria a recomendação de produção do material — "resista à tentação de exportar diretamente" (Aula 05) — mas o alvo aqui é cluster de demonstração local/efêmero, não produção; o Collector é o primeiro passo da evolução pós-fase 2, não desta entrega.
- **Condição de execução**: o trabalho só começa com os obrigatórios verdes; se o prazo apertar, esta onda é cortada por inteiro sem afetar requisito algum (gap analysis, risco 4).
- **Por que incluir**: o OpenTelemetry é a única disciplina da fase que ficaria sem reflexo no entregável; a demo é visível e barata — a Jaeger UI mostrando a jornada de uma requisição (endpoint → caso de uso → queries SQL) — e o risco de desvio de esforço é neutralizado pelo condicionamento.

## Alternativas Consideradas

* Escopo mínimo condicional: auto-instrumentação + Jaeger
* Stack completa da disciplina: Collector + Jaeger + Prometheus + Grafana + Loki
* Rejeitar: nenhuma instrumentação na fase 2

### Escopo mínimo condicional: auto-instrumentação + Jaeger

* Bom, porque traces visíveis no vídeo a custo mínimo: duas bibliotecas de instrumentação e um workload a mais no cluster — o mesmo exercício do hands-on de partida da disciplina (Aula 01)
* Bom, porque zero impacto nas camadas internas (ADR-015), zero segredo e custo zero — o mesmo envelope dos ADRs 016–018
* Bom, porque o condicionamento ("somente após obrigatórios verdes") protege os requisitos que efetivamente compõem o aceite da fase
* Ruim, porque entrega um dos três pilares: sem métricas RED nem logs correlacionados por TraceId, fica distante da plataforma integrada que a disciplina descreve como objetivo final (Aula 04)
* Ruim, porque sem Collector diverge da arquitetura de produção recomendada pelo material (Aula 05) — divergência aceita e registrada, não ignorada

### Stack completa da disciplina: Collector + Jaeger + Prometheus + Grafana + Loki

* Bom, porque cobre os três pilares com correlação por TraceId — o objetivo final descrito pela disciplina (Aula 04) — e o conjunto completo dos sinais de avaliação do material
* Bom, porque usa o Collector como intermediário, conforme a recomendação de produção (Aula 05)
* Ruim, porque adiciona quatro ou cinco workloads, pipeline de telemetria e dashboards — esforço da ordem dos próprios obrigatórios de infraestrutura, gasto num item que o challenge não pede; colisão frontal com o risco 4
* Ruim, porque mais partes móveis no cluster da demo significam mais modos de falha na gravação do vídeo

### Rejeitar: nenhuma instrumentação na fase 2

* Bom, porque foco total nos obrigatórios — risco de prazo zerado neste item
* Bom, porque nenhum workload nem dependência nova
* Ruim, porque a disciplina OpenTelemetry ficaria sem qualquer reflexo no entregável que vale 60% da sua nota — e a porta de entrada custa pouco demais para que a rejeição economize algo relevante
* Ruim, porque o vídeo perde a única demonstração de diagnóstico interno do sistema (a jornada da requisição), num desafio cujo mote é preparar a aplicação para operação em escala

## Consequências

### Positivas

* O vídeo pode demonstrar a jornada real de uma requisição na Jaeger UI — do endpoint FastAPI às queries SQLAlchemy — diferencial visível para a banca
* A disciplina OpenTelemetry ganha representação concreta no entregável
* A base instalada (SDK + OTLP) é o ponto de partida correto para evoluir para Collector, métricas e logs correlacionados — acréscimo de configuração e workloads, sem retrabalho de instrumentação

### Negativas

* Métricas e logs ficam de fora: perguntas de tendência (latência p95, taxa de erro) seguem sem resposta na fase 2 — a métrica existente é a do metrics-server do HPA, mecanismo independente
* A ausência do Collector pode ser notada por avaliador que siga o material à risca — mitigada por este ADR registrar a divergência e o motivo
* Por desenho, a onda pode ser cortada: o ADR pode terminar a fase como Proposta sem implementação — preferível a comprometer obrigatórios

### Neutras

* Versões das bibliotecas, variáveis `OTEL_*`, manifest do Jaeger, amostragem e um eventual span manual de negócio (ex.: aprovação de orçamento, o tipo de contexto que a Aula 05 recomenda adicionar à instrumentação automática) ficam deferidos ao plano de execução da infraestrutura (fase de implementação), fora deste ADR
* A demo de HPA (RNF-023) não depende desta decisão — metrics-server e OTel são trilhos separados
* Se a banca vier a exigir os três pilares, a reabertura deste ADR parte da alternativa de stack completa

## Decisões Relacionadas

- [ADR-015](015-arquitetura-alvo-fase-2.md): a instrumentação automática vive na borda (Frameworks & Drivers); entidades e casos de uso não conhecem OTel
- [ADR-016](016-plataforma-kubernetes.md): o Jaeger roda no cluster kind da demo, como mais um workload local/efêmero de custo zero
- [ADR-018](018-notificacao-email.md): mesmo padrão de workload de demonstração — Deployment + Service, UI por port-forward na gravação
- [ADR-019](019-pipeline-cicd-deploy.md): o pipeline não ganha estágio novo por causa do OTel; o manifest do Jaeger entra no mesmo `kubectl apply` do job de CD quando a onda for executada

## Notas

* Fonte das evidências: fichamento da disciplina OpenTelemetry (Aulas 01–05) da fase 2 (FIAP Pos Tech). As citações "(Disciplina, Aula NN)" referem-se ao material oficial
* Sem requisito formal: nenhum RF/RNF do [gap-analysis-fase-2.md](../../../requisitos/fase2/gap-analysis-fase-2.md) cobre observabilidade — decisão de diferencial; o peso vem de o challenge englobar todas as disciplinas da fase ([desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md), "Sobre o Tech Challenge")
* Gatilhos de revisão: corte da onda por prazo (o ADR permanece Proposta, sem implementação) ou exigência de escopo maior pela banca (reabre pela alternativa de stack completa)

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
