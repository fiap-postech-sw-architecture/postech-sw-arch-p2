# Usar JWT HS256 para autenticação

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-03-20

## Contexto e Problema

O sistema precisa de autenticação para proteger endpoints administrativos (gestão de estoque, aprovação de orçamentos, etc.). O enunciado do Tech Challenge exige explicitamente o uso de JWT. Como implementar autenticação que atenda ao requisito e seja adequada ao escopo do MVP?

## Decisão

Adotar JWT com as seguintes especificações:

- **Algoritmo**: HS256 com enforcement explícito na validação (prevenção de algorithm confusion)
- **Tempo de vida**: 30 minutos por token (configurável via `JWT_EXPIRATION_MINUTES`)
- **Claims customizados**: `Papel` (Enum do domínio) incluído no payload
- **Transporte**: exclusivamente via header `Authorization: Bearer <token>` (sem cookies)
- **Refresh tokens**: token de renovação com rotação e TTL configurável (RF-013)
- **Revogação**: tabela `tokens_revogados` com JTI; logout invalida o token corrente (RF-012)

## Alternativas Consideradas

* JWT HS256 com revogação e refresh tokens
* Autenticação baseada em sessão
* OAuth2/OIDC com provedor externo

### JWT HS256 com revogação e refresh tokens

Tokens assinados com chave simétrica. Validação inclui verificação de revogação via tabela `tokens_revogados`.

* Bom, porque é stateless, sem necessidade de armazenar sessões no servidor
* Bom, porque a implementação é simples com a biblioteca Python madura PyJWT
* Bom, porque atende diretamente ao requisito do Tech Challenge
* Bom, porque o `Papel` no payload permite autorização sem consulta adicional ao banco
* Ruim, porque revogação via tabela `tokens_revogados` adiciona consulta ao banco em cada request
* Ruim, porque refresh tokens com rotação adicionam complexidade ao fluxo de autenticação

### Autenticação baseada em sessão

Sessões armazenadas no servidor (banco ou cache), identificadas por cookie.

* Bom, porque permite revogação imediata (basta invalidar a sessão)
* Bom, porque é um padrão bem estabelecido e simples de implementar
* Ruim, porque não atende ao requisito explícito de JWT do Tech Challenge
* Ruim, porque é stateful, exigindo armazenamento de sessão no servidor
* Ruim, porque cookies adicionam complexidade de CORS em APIs REST

### OAuth2/OIDC com provedor externo

Delegação de autenticação para um provedor de identidade (Keycloak, Auth0, etc.).

* Bom, porque suporta cenários complexos de identidade em ambientes de produção
* Bom, porque suporta SSO, refresh tokens e revogação nativamente
* Ruim, porque adiciona dependência de infraestrutura externa (provedor de identidade)
* Ruim, porque a complexidade de configuração é desproporcional ao escopo do MVP
* Ruim, porque o overhead operacional não se justifica para um projeto acadêmico

## Consequências

### Positivas

* Atende diretamente ao requisito de JWT do Tech Challenge
* Implementação baseada em JWT simplifica a infraestrutura no contexto de autenticação (sem Redis ou sessões server-side para validar tokens)
* Enforcement explícito do algoritmo HS256 previne ataques de algorithm confusion
* `Papel` no payload permite autorização rápida sem roundtrip ao banco
* Header-only elimina complexidade de gerenciamento de cookies e CORS

### Negativas

* Revogação via tabela `tokens_revogados` adiciona uma consulta ao banco por request autenticado
* Refresh tokens com rotação aumentam a superfície de ataque se o token de renovação for comprometido
* HS256 usa chave simétrica compartilhada; em cenários multi-serviço, RS256 seria mais adequado
* O tempo de vida curto (30 min) pode impactar a experiência do usuário em operações longas

## Decisões Relacionadas

- [ADR-001](001-framework-fastapi.md): FastAPI como framework web — a injeção de dependências nativa provê o `JWTService` e os guards de papel aos endpoints protegidos
- [ADR-023](fase2/023-rate-limiter-storage-compartilhado.md): Rate limiter com storage compartilhado (Redis) — o Redis introduzido na fase 2 atende ao rate limiting, não à validação de tokens, que permanece stateless

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
