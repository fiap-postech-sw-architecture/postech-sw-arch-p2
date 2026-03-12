# Resolver toda a dívida técnica dentro da Fase 1 via MVPs iterativos

* Status: aceito
* Data: 2026-03-12

## Contexto e Problema

O documento de dívida técnica lista 15 itens com severidades Alta, Média e Baixa, originalmente planejados para fases futuras (F2, F3). Entretanto, o currículo das fases 2 a 4 é desconhecido — cada fase pode ter requisitos próprios e stack diferente, tornando o diferimento uma aposta sem base concreta.

Como endereçar a dívida técnica sem depender de fases cujo escopo é desconhecido?

## Decisão

Resolver todos os 15 itens de dívida técnica dentro da Fase 1, distribuindo-os em 8 versões MVP iterativas (MVP-0.01 a MVP-1.0). Cada versão agrupa itens de tech debt com o contexto delimitado onde naturalmente se encaixam.

O mapeamento completo está em [`docs/tech-debt.md`](../../tech-debt.md).

## Alternativas Consideradas

* Resolver tudo em F1 via MVPs iterativos (escolhida)
* Diferir itens de Média/Baixa severidade para F2/F3

### Resolver tudo em F1 via MVPs iterativos

Distribuir os 15 itens ao longo das 8 semanas, agrupados por afinidade com o contexto sendo implementado naquela semana.

* Bom, porque elimina a dependência de fases cujo currículo é desconhecido
* Bom, porque a entrega final demonstra domínio mais amplo do conteúdo (DDD, segurança, qualidade)
* Bom, porque todos os itens são viáveis no prazo com assistência de IA
* Bom, porque há estratégia de corte documentada caso o tempo aperte
* Ruim, porque aumenta o escopo da F1 em relação ao planejamento inicial

### Diferir itens de Média/Baixa severidade para F2/F3

Manter o planejamento original, resolvendo apenas itens de Alta severidade na F1.

* Bom, porque reduz o escopo da F1
* Ruim, porque o currículo de F2-F4 é desconhecido — diferir não tem base concreta
* Ruim, porque F2-F4 podem ter stack diferente, tornando os itens irrelevantes ou redundantes
* Ruim, porque a entrega da F1 fica com lacunas conhecidas e documentadas

## Consequências

### Positivas

* Dívida técnica zero ao final da F1
* Entrega demonstra competência em segurança (LGPD, JWT revogação), qualidade (mutation testing) e patterns avançados (transactional outbox)
* Estratégia de corte garante que itens inegociáveis são priorizados se o tempo apertar

### Negativas

* Escopo maior exige disciplina no cronograma — atrasos acumulam
* Itens cortáveis (TD-013 notificações stub, TD-015 mutation testing hard, TD-004 consentimento, TD-007 histórico orçamento) podem não ser implementados se o cronograma apertar

## Notas

Itens inegociáveis: TD-001 (encriptação PII), TD-003+TD-006 (revogação JWT + refresh tokens), TD-009+TD-010 (Docker secrets + CSP), TD-011+TD-012 (transactional outbox), TD-014 (índice GIN).
