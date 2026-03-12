# Usar PostgreSQL 16 como banco de dados

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O sistema precisa de um banco de dados que atenda aos requisitos técnicos do domínio de oficina mecânica. As entidades centrais do domínio impõem demandas específicas ao banco de dados:

- **`OrdemDeServico`** — máquina de estados com transições controladas (`StatusOrdemDeServico`); exige tipos ENUM nativos para validação no nível do banco
- **`ItemEstoque`** — controle de concorrência em reservas e baixas; exige `SELECT FOR UPDATE NOWAIT` para locking pessimista sem deadlocks
- **`Orcamento`** — itens com estrutura semi-flexível; exige JSONB para armazenamento e consultas indexadas
- **`Usuario`** — papéis de acesso (`Papel`); exige ENUM nativo para mapeamento direto via SQLAlchemy

Quais capacidades são necessárias?

- Tipos ENUM nativos para estados de `OrdemDeServico` e `Papel` de `Usuario`
- `SELECT FOR UPDATE NOWAIT` para controle de concorrência no `ItemEstoque`
- JSONB para armazenamento flexível de itens do `Orcamento`
- Transações robustas com garantias ACID completas

## Decisão

Adotar o PostgreSQL 16 como banco de dados relacional do projeto.

O PostgreSQL atende a todos os requisitos técnicos identificados com funcionalidades nativas, sem necessidade de workarounds. O suporte a ENUM nativo, JSONB e locking pessimista com `NOWAIT` são diferenciais diretos para o domínio modelado.

## Alternativas Consideradas

* PostgreSQL 16
* MySQL 8
* SQLite
* MongoDB

### PostgreSQL 16

Banco de dados relacional open-source com suporte avançado a tipos, JSONB e controle de concorrência.

* Bom, porque tem tipos ENUM nativos, mapeados diretamente para os estados do domínio
* Bom, porque suporta `SELECT FOR UPDATE NOWAIT`, essencial para locking de estoque sem deadlocks
* Bom, porque JSONB permite armazenar itens do Orcamento com flexibilidade e consultas indexadas
* Bom, porque tem ecossistema maduro e gratuito
* Ruim, porque tem complexidade operacional maior que SQLite para ambiente de desenvolvimento local

### MySQL 8

Banco de dados relacional amplamente adotado, com suporte a JSON e transações InnoDB.

* Bom, porque é amplamente adotado e bem documentado
* Bom, porque suporta `SELECT FOR UPDATE` com InnoDB
* Ruim, porque o suporte a JSON é menos maduro que o JSONB do PostgreSQL (sem indexação GIN nativa)
* Ruim, porque tipos ENUM no MySQL têm limitações conhecidas (alteração requer ALTER TABLE)
* Ruim, porque o modelo de locking do InnoDB é menos previsível em cenários de alta concorrência

### SQLite

Banco de dados embarcado, sem servidor, ideal para prototipagem e testes.

* Bom, porque tem configuração zero, facilitando o desenvolvimento local
* Bom, porque é suficiente para o volume de dados do MVP
* Ruim, porque não suporta `SELECT FOR UPDATE NOWAIT`
* Ruim, porque não tem tipos ENUM nativos
* Ruim, porque tem limitações de concorrência em escrita (write lock global)
* Ruim, porque as diferenças de comportamento em relação ao PostgreSQL geram riscos em produção

### MongoDB

Banco de dados orientado a documentos, com modelo flexível de schema.

* Bom, porque o modelo de documentos é naturalmente flexível para dados semi-estruturados
* Bom, porque escala horizontalmente com facilidade
* Ruim, porque não oferece transações ACID multi-documento com a mesma robustez de um banco relacional
* Ruim, porque o modelo de documentos não se alinha com o mapeamento relacional do SQLAlchemy
* Ruim, porque adiciona complexidade operacional desnecessária para o escopo do projeto

## Consequências

### Positivas

* Tipos ENUM nativos mapeados diretamente para `StatusOrdemDeServico` e `Papel` via SQLAlchemy
* `SELECT FOR UPDATE NOWAIT` permite locking pessimista no `ItemEstoque` sem risco de deadlock
* JSONB armazena itens do `Orcamento` com flexibilidade, permitindo consultas indexadas
* Garantias ACID completas para todas as operações transacionais do domínio
* Ecossistema maduro com ferramentas de monitoramento, backup e migração bem estabelecidas
* Gratuito e open-source, sem custos de licenciamento

### Negativas

* Complexidade operacional maior que SQLite para desenvolvimento local (requer Docker ou instalação)
* Curva de aprendizado para funcionalidades avançadas (JSONB, locking, tuning)
* Testes de integração requerem instância PostgreSQL real ou container, aumentando o tempo de setup

## Decisões Relacionadas

- [ADR-005](005-estrategia-testes.md): Estratégia de testes — testcontainers com PostgreSQL real mitiga a consequência negativa de complexidade de testes
- [ADR-008](008-bloqueio-pessimista-estoque.md): Bloqueio pessimista — detalha o uso de SELECT FOR UPDATE NOWAIT com locks em ordem crescente
