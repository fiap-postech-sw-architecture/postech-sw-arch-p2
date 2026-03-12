# Usar JWT HS256 para autenticacao

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O sistema precisa de autenticacao para proteger endpoints administrativos (gestao de estoque, aprovacao de orcamentos, etc.). O enunciado do Tech Challenge exige explicitamente o uso de JWT. Como implementar autenticacao que atenda ao requisito e seja adequada ao escopo do MVP?

## Decisão

Adotar JWT com as seguintes especificações:

- **Algoritmo**: HS256 com enforcement explícito na validação (prevenção de algorithm confusion)
- **Tempo de vida**: 15 minutos por token
- **Claims customizados**: `Papel` (Enum do domínio) incluído no payload
- **Transporte**: exclusivamente via header `Authorization: Bearer <token>` (sem cookies)
- **Refresh tokens**: não implementados no MVP (risco aceito)
- **Revogação**: não implementada no MVP (mitigada pelo tempo de vida curto)

## Alternativas Consideradas

* JWT HS256 (stateless)
* Autenticação baseada em sessão
* OAuth2/OIDC com provedor externo

### JWT HS256 (stateless)

Tokens assinados com chave simétrica, validados localmente sem consulta ao banco.

* Bom, porque é stateless, sem necessidade de armazenar sessões no servidor
* Bom, porque a implementação é simples com bibliotecas Python maduras (PyJWT, python-jose)
* Bom, porque atende diretamente ao requisito do Tech Challenge
* Bom, porque o `Papel` no payload permite autorização sem consulta adicional ao banco
* Ruim, porque não permite revogação imediata de tokens no MVP
* Ruim, porque sem refresh tokens, o usuário precisa autenticar novamente a cada 15 minutos

### Autenticação baseada em sessão

Sessões armazenadas no servidor (banco ou cache), identificadas por cookie.

* Bom, porque permite revogação imediata (basta invalidar a sessão)
* Bom, porque é um padrão bem estabelecido e simples de implementar
* Ruim, porque não atende ao requisito explícito de JWT do Tech Challenge
* Ruim, porque é stateful, exigindo armazenamento de sessão no servidor
* Ruim, porque cookies adicionam complexidade de CORS em APIs REST

### OAuth2/OIDC com provedor externo

Delegação de autenticação para um provedor de identidade (Keycloak, Auth0, etc.).

* Bom, porque é a solução mais robusta para ambientes de produção
* Bom, porque suporta SSO, refresh tokens e revogação nativamente
* Ruim, porque adiciona dependência de infraestrutura externa (provedor de identidade)
* Ruim, porque a complexidade de configuração é desproporcional ao escopo do MVP
* Ruim, porque o overhead operacional não se justifica para um projeto acadêmico

## Consequências

### Positivas

* Atende diretamente ao requisito de JWT do Tech Challenge
* Implementação stateless simplifica a infraestrutura (sem Redis ou tabela de sessões)
* Enforcement explícito do algoritmo HS256 previne ataques de algorithm confusion
* `Papel` no payload permite autorização rápida sem roundtrip ao banco
* Header-only elimina complexidade de gerenciamento de cookies e CORS

### Negativas

* Sem revogação no MVP: um token comprometido permanece válido por até 15 minutos (risco aceito)
* Sem refresh tokens: usuários precisam autenticar novamente após expiração do token
* HS256 usa chave simétrica compartilhada; em cenários multi-serviço, RS256 seria mais adequado
* O tempo de vida curto (15 min) pode impactar a experiência do usuário em operações longas
