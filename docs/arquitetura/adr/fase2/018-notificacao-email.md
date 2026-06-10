# Notificação de status por e-mail via adapter SMTP com Mailpit

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Proposta
* Data: 2026-06-10

## Contexto e Problema

O Tech Challenge da fase 2 exige "atualização de status da OS via alguma ferramenta como email" — ver [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md). O RF-024 do [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md) traduz a exigência em critério de aceite: transições de status disparam e-mail ao cliente (no mínimo: orçamento disponível e OS finalizada/entregue), falha de envio não bloqueia a transição e credenciais ficam fora do código (Secret). A interpretação do enunciado — **notificar** a atualização por e-mail, e não alterar status respondendo e-mail — está registrada no gap analysis (§3) e será confirmada com a banca.

A arquitetura do mecanismo não é opção deste ADR — é a convenção do projeto, ratificada pelo [ADR-015](015-arquitetura-alvo-fase-2.md): porta declarada em `aplicacao/` e adapter concreto em `infraestrutura/`, como as demais portas do contexto (`src/ordem_servico/aplicacao/ports.py` declara os Protocols que a aplicação consome, implementados na borda). A porta deste requisito é a **`EmailPort`**, no contexto consumidor `ordem_servico`.

A matéria-prima também já existe: o agregado `OrdemDeServico` emite eventos de domínio a cada transição (`src/ordem_servico/dominio/events.py` — `OrcamentoGeradoEvent`, `ServicoFinalizadoEvent`, `EntregaRegistradaEvent`, entre outros), mas o dispatch está deferido desde a fase 1 — o docstring de `src/ordem_servico/aplicacao/use_cases.py:10-14` registra que os eventos apenas "se acumulam em `_eventos_pendentes`", sem publicação. O RF-024 é o primeiro consumidor real desses eventos: os três citados cobrem um a um os e-mails mínimos do aceite.

O que este ADR decide: **qual adapter realiza a `EmailPort`** e o que entra no docker-compose e no cluster para a demo. Critérios: demo visível no vídeo sem custo nem segredo pessoal; atendimento do RF-024; configuração 12-factor por variáveis de ambiente.

**Qual adapter de e-mail realiza a `EmailPort` — e com qual servidor a demo funciona?**

## Decisão

Adapter **SMTP genérico configurado por variáveis de ambiente**, com **Mailpit** como servidor SMTP de desenvolvimento e demo.

- O adapter fala SMTP puro pela biblioteca padrão do Python (`smtplib`) — nenhuma dependência nova — e lê host, porta, remetente e credenciais opcionais de variáveis de ambiente. No cluster, valores não sensíveis entram por ConfigMap e sensíveis por Secret, no padrão do material — ConfigMap separa a configuração dos artefatos de implantação, injetada via `envFrom` (Kubernetes, Aula 04) — e na regra de nunca embutir credenciais em código (Terraform, Aula 02).
- O Mailpit é um servidor SMTP de teste com UI web: aceita qualquer mensagem sem credencial e a exibe numa caixa de entrada navegável. A demo do vídeo mostra a transição de status e, em seguida, o e-mail materializado na UI — sem conta externa, sem custo, sem segredo pessoal.
- **No docker-compose** (dev local — RNF-019): novo serviço `mailpit` (SMTP interno na 1025, UI web na 8025) ao lado de `app`, `postgres` e `ui`; o `app` recebe `SMTP_HOST=mailpit`.
- **No cluster** (demo — [ADR-016](016-plataforma-kubernetes.md)): Mailpit como Deployment com Service ClusterIP para o app — Deployment é o recurso padrão para workloads (Kubernetes, Aula 05) e ClusterIP o tipo de Service para consumo interno (Kubernetes, Aula 04); a UI é acessada por port-forward (ou NodePort) na gravação do vídeo.
- Produção real fica fora da fase 2: como o adapter é SMTP genérico, apontar as variáveis para um relay real (por exemplo, SES via interface SMTP) é mudança de configuração, não de código.

## Alternativas Consideradas

* Adapter SMTP genérico + Mailpit em dev/demo
* Provedor SaaS (SendGrid, Amazon SES)
* Adapter de log/console apenas

### Adapter SMTP genérico + Mailpit em dev/demo

* Bom, porque a demo é visível e autocontida: o e-mail aparece numa caixa de entrada navegável durante o vídeo, sem conta externa, custo ou segredo pessoal
* Bom, porque 12-factor de ponta a ponta: toda a configuração por variáveis de ambiente via ConfigMap/Secret (Kubernetes, Aula 04), pronta para trocar de servidor sem tocar código
* Bom, porque zero dependência nova (`smtplib` é stdlib) e zero lock-in de provedor
* Ruim, porque o Mailpit é um sink local: prova o mecanismo de envio, não a entrega real a uma caixa externa (SPF/DKIM e reputação ficam fora)
* Ruim, porque adiciona um workload ao compose e ao cluster

### Provedor SaaS (SendGrid, Amazon SES)

* Bom, porque entrega real a caixas reais, com métricas de envio e bounce gerenciadas
* Bom, porque terceiriza a entregabilidade (SPF/DKIM, reputação de IP) — a parte operacionalmente difícil de e-mail
* Ruim, porque exige conta pessoal e chave de API como segredo no repositório/CI — exatamente o que o critério da demo proíbe — além da burocracia de habilitação (sandbox e verificação de remetente)
* Ruim, porque a gravação do vídeo passaria a depender de um serviço externo no ar e de cotas de envio

### Adapter de log/console apenas

* Bom, porque custo e esforço mínimos — nenhum workload extra
* Bom, porque a ideia sobrevive como dublê de teste: a `EmailPort` admite um fake em memória nos testes unitários, independentemente desta decisão
* Ruim, porque não satisfaz o RF-024: o requisito pede uma ferramenta como e-mail e o aceite do gap analysis pede e-mail ao cliente — linha de log não é e-mail
* Ruim, porque a demo no vídeo se reduziria a mostrar log — evidência fraca do requisito para a banca

## Consequências

### Positivas

* RF-024 demonstrável no vídeo: transição de status → e-mail na caixa do Mailpit
* O débito de dispatch declarado em `use_cases.py:10-14` ganha enfim um consumidor: os eventos de domínio existentes deixam de ser apenas acumulados
* Nenhum segredo pessoal no repositório ou no CI; quando houver provedor real, a credencial entra por Secret (RNF-020) sem mudança de código

### Negativas

* A entregabilidade real de e-mail não é validada na fase 2 — o Mailpit prova o mecanismo; a troca por relay real fica como passo de produção
* O aceite "falha de envio não bloqueia a transição" impõe disciplina no wiring: o envio precisa ser tolerante a falha (capturar o erro e registrar log, nunca abortar o caso de uso) — um modo de falha novo a cobrir nos testes (RNF-018)

### Neutras

* O destinatário vem do cadastro do cliente: hoje `Cliente` tem apenas o campo livre `_contato` (`src/cliente_veiculo/dominio/cliente.py:48`), sem e-mail dedicado/validado; reusar o contato ou criar campo próprio fica deferido ao plano de execução (fase de implementação)
* Quais transições além do mínimo notificam, o conteúdo das mensagens e o mecanismo exato de dispatch (chamada pós-commit no caso de uso vs event bus) ficam deferidos ao plano de execução, fora deste ADR
* O gap analysis nomeava a porta genericamente como `NotificacaoPort`; este ADR a especializa como `EmailPort`, refletindo o canal decidido — um eventual segundo canal (SMS, push) entraria como porta própria

## Decisões Relacionadas

- [ADR-015](015-arquitetura-alvo-fase-2.md): porta em `aplicacao/` + adapter em `infraestrutura/` é o desenho de Gateways da Clean — abstração definida pela camada interna, realização na borda
- [ADR-016](016-plataforma-kubernetes.md): o Mailpit roda no cluster kind como Deployment + Service para a demo do vídeo
- [ADR-009](../009-decisao-de-idioma.md): `EmailPort` e o adapter seguem o modelo híbrido de idioma (sufixo técnico em inglês)

## Notas

* Fonte das evidências: fichamentos das disciplinas Kubernetes (Aulas 04–05) e Terraform (Aula 02) da fase 2 (FIAP Pos Tech). As citações "(Disciplina, Aula NN)" referem-se ao material oficial
* Requisito formal: RF-024 ([gap-analysis-fase-2.md](../../../requisitos/fase2/gap-analysis-fase-2.md), §3 — incluindo a interpretação do enunciado a confirmar com a banca); exigência original em [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md)
* Mailpit é open-source, com manutenção ativa, e ocupa o papel que o MailHog tinha nas stacks clássicas de desenvolvimento

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
