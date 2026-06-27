# Rate limiter com storage compartilhado (Redis) sob HPA

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Aceita
* Data: 2026-06-27

## Contexto e Problema

A [RNF-024](../../../requisitos/fase2/gap-analysis-fase-2.md) exige *statelessness* para escala horizontal: a aplicação deve se comportar corretamente com N réplicas, sem depender de estado em memória de um pod específico. O requisito tem duas metades — o **pool de conexões** dimensionado para o pior caso do HPA (já entregue: `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` em [database.py](../../../../src/compartilhado/infraestrutura/database.py)) e o **rate limiter** sob múltiplas réplicas, o gap que este ADR fecha.

O rate limiter da fase 1 usa [slowapi](https://github.com/laurentS/slowapi) com o storage *in-memory* da biblioteca [limits](https://limits.readthedocs.io): cada processo mantém seu **próprio** contador por IP, na memória do pod ([middleware.py](../../../../src/compartilhado/interfaces/middleware.py)). Numa única réplica isso é correto. Sob o HPA ([ADR-016](016-plataforma-kubernetes.md)), com mais de uma réplica atrás do mesmo Service, as requisições de um mesmo IP são balanceadas entre pods e **cada pod conta isoladamente**: o limite efetivo passa a ser multiplicado pelo número de réplicas.

O efeito é duplo e indesejável:

- **Limite real frouxo**: com R réplicas, o teto que o cliente experimenta é ~R× o limite configurado — a proteção que o rate limiter deveria dar dilui à medida que o HPA escala, justamente quando a carga é maior.
- **429 inconsistentes**: o mesmo cliente, com a mesma taxa de chamadas, é barrado ou não dependendo de qual pod o atende — comportamento não determinístico que polui inclusive a demonstração de escalabilidade (ver o risco no [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md)).

**Como tornar o rate limiter correto e global sob HPA — um único contador por IP compartilhado entre todas as réplicas — sem quebrar o desenvolvimento local, o CI e os testes, que rodam num único processo?**

## Decisão

**Apontar o storage do slowapi/limits para um backend compartilhado — um Redis no cluster — via `storage_uri`.** O contador por IP deixa de viver na memória de cada pod e passa a residir num único Redis, que todas as réplicas consultam e incrementam; o limite torna-se global e correto, independente de quantos pods o HPA mantém de pé.

- **Redis como mais um workload de demo**: um `Deployment` + `Service` no cluster kind, seguindo o mesmo padrão dos demais serviços de apoio da fase — Mailpit ([ADR-018](018-notificacao-email.md)) e Jaeger ([ADR-020](020-observabilidade-opentelemetry.md)). Nenhuma infraestrutura gerenciada nova; o Redis sobe e desce com o cluster.
- **Opt-in por env `RATE_LIMIT_STORAGE_URI`** (ex.: `redis://redis:6379`): quando definida, o `Limiter` é construído com esse `storage_uri`; **quando ausente, o storage cai para `memory://`** — o default in-process. Isso preserva, sem custo nem dependência nova, o desenvolvimento local, o `docker compose` e o CI (um único processo, onde o contador in-memory já é correto), além da *fixture* que reseta o storage do limiter entre testes.
- **Redis sem persistência**: os contadores de rate limit são efêmeros e de janela curta — perdê-los num restart do Redis apenas zera as janelas em curso, sem impacto de negócio. Não se configura AOF/RDB.
- **Redis sem senha**: é um serviço interno do cluster de demonstração, acessível só pela rede do cluster; autenticação fica fora do escopo da fase (a registrar caso o Redis assuma usos sensíveis — ver Notas).
- **Dependência `redis` direta**, não o extra `slowapi[redis]`: esse extra fixa `redis<4`, que **conflita** com o `redis>=4` que o `limits 5.8` (a versão usada pelo slowapi atual) requer. Declara-se o `redis` como dependência direta na versão compatível com `limits`, e o slowapi consome esse backend pelo `storage_uri` — sem o pin transitivo do extra.

A construção do `Limiter` com o `storage_uri` derivado da env vive na borda (interfaces — ver Decisões Relacionadas); o domínio e a aplicação não tomam conhecimento do backend de rate limit.

## Alternativas Consideradas

* Redis compartilhado via `storage_uri` (escolhida)
* Aceitar o limite por-réplica e apenas documentá-lo
* Afinidade de sessão (sticky) no ingress por IP
* Contador de rate limit no PostgreSQL

### Redis compartilhado via `storage_uri`

* Bom, porque torna o limite **global e correto** sob HPA: um único contador por IP, independente do número de réplicas — resolve a causa-raiz, não o sintoma
* Bom, porque é **opt-in e sem custo** para dev/CI: ausente a env, cai para `memory://` e nada muda no fluxo local, no compose ou na *fixture* de reset dos testes
* Bom, porque reusa um **padrão de workload já conhecido** na fase (Deployment+Service de demo, como Mailpit e Jaeger) — nenhuma operação nova a aprender
* Ruim, porque adiciona **um componente** (Redis) a subir e operar no cluster
* Ruim, porque introduz um **ponto único de coordenação** do limite: se o Redis cair, o rate limiting é afetado (mitigável degradando para `memory://` — ver Notas)

### Aceitar o limite por-réplica e apenas documentá-lo

* Bom, porque é o mais simples: nenhuma infraestrutura nova, nenhuma dependência — só uma nota de débito
* Ruim, porque **não resolve o problema**: o limite real continua sendo ~N×réplicas, frouxo justamente sob carga, e os 429 seguem inconsistentes — era o status quo registrado como TD-016
* Ruim, porque enfraquece a própria demonstração de escala (RNF-024), em que o comportamento sob HPA deveria ser correto, não ressalvado

### Afinidade de sessão (sticky) no ingress por IP

* Bom, porque mantém o storage in-memory: roteando sempre o mesmo IP ao mesmo pod, cada contador volta a ser "o" contador daquele cliente
* Ruim, porque é **frágil**: qualquer rebalance — scale up/down do HPA, rollout, queda de pod — remapeia o IP para outro pod, cujo contador está zerado, reabrindo a janela e quebrando a garantia exatamente nos momentos de escala
* Ruim, porque acopla uma preocupação de aplicação (rate limit) à topologia de rede do ingress, e degrada a distribuição de carga (hot pods por IP)

### Contador de rate limit no PostgreSQL

* Bom, porque **não adiciona componente novo**: reaproveita o PostgreSQL ([ADR-002](../002-banco-postgresql.md)) que já é o banco do sistema — o mesmo princípio de "zero infra" do outbox ([ADR-022](022-transactional-outbox-relay.md))
* Ruim, porque **castiga o caminho quente**: cada requisição sujeita a limite vira uma escrita transacional no banco de negócio — contadores de alta frequência e janela curta são exatamente a carga para a qual um store em memória (Redis) é talhado e um RDBMS não
* Ruim, porque **mistura responsabilidades**: coloca tráfego de infraestrutura (rate limit) no banco transacional do domínio, competindo por conexões do pool já dimensionado da RNF-024

## Consequências

### Positivas

* O rate limiter passa a aplicar um **limite correto e global** sob HPA: um contador por IP para todas as réplicas, eliminando o teto frouxo (~N×) e os 429 não determinísticos
* **Opt-in sem custo** para dev/local/CI: ausente `RATE_LIMIT_STORAGE_URI`, o storage é `memory://` — o fluxo de um processo só, o `docker compose` e a *fixture* de reset dos testes seguem idênticos
* Reusa um **padrão de workload já estabelecido** na fase (Deployment+Service de demo); a equipe já opera Mailpit e Jaeger pelo mesmo molde
* A segunda metade da RNF-024 fica **fechada** — somada ao pool de conexões já entregue, a *statelessness* da aplicação sob N réplicas está completa

### Negativas

* **Um componente novo** (Redis) a empacotar, subir e operar no cluster — superfície operacional e de falha a mais
* O Redis vira o **ponto único de coordenação** do limite: indisponibilidade dele afeta o rate limiting. Mitigação possível: degradar para `memory://` (limite volta a ser por-réplica, mas o serviço não cai) — a registrar como comportamento de fallback se/quando implementado
* O Redis da fase é **de demonstração — sem HA e sem persistência**: não há réplica nem failover, e os contadores não sobrevivem a restart (aceitável para janelas curtas de rate limit; inadequado se o Redis assumir usos que exijam durabilidade)

### Neutras

* Parâmetros operacionais — URL/porta do Redis, política de *eviction*, limites por rota — ficam em **configuração** (env/ConfigMap), fora deste ADR
* O Redis introduzido fica **reaproveitável** para outros usos de cache no futuro (ex.: cache de leitura), caso surja necessidade — sem que isso seja um compromisso deste ADR
* A escolha do backend é transparente para a aplicação: trocar Redis por outro store suportado pelo `limits` é uma questão de `storage_uri`, sem mudança de código de domínio/aplicação

## Decisões Relacionadas

- [ADR-016](016-plataforma-kubernetes.md): o Redis é mais um workload no cluster kind da fase — a decisão se apoia na plataforma Kubernetes local já estabelecida
- [ADR-018](018-notificacao-email.md): o Mailpit usa o mesmo padrão Deployment+Service de serviço de apoio de demonstração que o Redis adota
- [ADR-020](020-observabilidade-opentelemetry.md): o Jaeger é o outro precedente do mesmo molde de workload de demo no cluster
- [ADR-015](015-arquitetura-alvo-fase-2.md): o rate limiting é preocupação de borda (interfaces); a construção do `Limiter` e a leitura da env vivem nessa camada, sem tocar domínio/aplicação

## Notas

* Requisito: [RNF-024](../../../requisitos/fase2/gap-analysis-fase-2.md) (statelessness/escala horizontal) — esta é a metade do rate limiter; a do pool de conexões já estava entregue
* Resolve **TD-016** ([dívida técnica](../../../tech-debt/README.md)): rate limiter slowapi in-memory por pod
* Implementação: PR #62
* Gatilho de revisão: se o Redis virar dependência crítica (HA, persistência, ou usos sensíveis como cache de dados), avaliar habilitar persistência/replicação e autenticação, ou tornar explícito o fallback para `memory://` quando o Redis estiver indisponível

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
