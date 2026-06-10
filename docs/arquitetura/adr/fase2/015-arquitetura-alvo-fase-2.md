# Clean Architecture como arquitetura alvo da fase 2

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Proposta
* Data: 2026-06-10

## Contexto e Problema

O Tech Challenge da fase 2 exige refatorar o código da fase 1 aplicando "**Clean Architecture** ou **Arquitetura Hexagonal** (separação adequada de camadas e dependências)" — ver [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md). O requisito RNF-017 do [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md) traduz a exigência em critério de aceite: ADR registrando a escolha, nenhuma importação de `infraestrutura` em `dominio`/`aplicacao` e regra verificada por lint ou teste de arquitetura.

O estado atual é o DDD com Arquitetura Onion do [ADR-003](../003-arquitetura-ddd-onion.md): cada contexto delimitado organiza-se em `dominio/`, `aplicacao/`, `infraestrutura/` e `interfaces/`, com ports (interfaces de repositório, UnitOfWork e ports cross-context) declarados em `aplicacao/` e adapters concretos em `infraestrutura/`. Na prática a estrutura já é ports & adapters; o que falta é a decisão formal entre as duas abordagens aceitas pelo challenge — manter a Onion sem essa formalização não atende o RNF-017.

Critério de decisão adotado pela equipe, fixado antes do estudo do material da disciplina para evitar viés de confirmação: **a Arquitetura Hexagonal só seria adotada se (a) o material da disciplina a aceitasse com o mesmo peso que a Clean Architecture e (b) ela fosse equivalente ou melhor para o codebase atual; em qualquer outro cenário, adota-se a Clean Architecture.** A fonte de evidência é a disciplina Clean Architecture da fase 2 (FIAP Pos Tech, Aulas 01–08), fichada aula a aula antes desta decisão.

**Qual das duas abordagens — Clean Architecture ou Arquitetura Hexagonal — deve guiar a refatoração da fase 2?**

## Decisão

Adotar **Clean Architecture** como arquitetura alvo da refatoração da fase 2.

A decisão aplica o critério acima: o material aceita a Hexagonal como referência legítima, mas não com o mesmo peso — a condição (a) falha. Três evidências sustentam essa leitura:

1. **O único juízo comparativo do material favorece a Clean.** A Aula 02 apresenta os dois diagramas lado a lado ("os dois são muito usados como referência e citados em desenhos de projetos"), avisa que "elas não são a mesma coisa" e conclui que a Clean "implementa uma estrutura de camadas com mais elementos e mais regras, que permitem uma melhor organização do código". É a única comparação valorativa entre as duas abordagens em toda a disciplina.
2. **O diagrama consolidado na revisão é o de Robert Martin.** A Aula 08 (revisão da disciplina) fixa como referência o diagrama da Arquitetura Limpa (Martin, adaptado pela FIAP), com Entidades, Casos de Uso, Adaptadores de Interface e Frameworks & Drivers. Das Aulas 03 a 08, o detalhamento normativo — camadas, componentes, regras de dependência — é exclusivamente da Clean.
3. **O vocabulário treinado e cobrado é o da Clean.** As Aulas 04, 05 e 08 exercitam Casos de Uso, Controllers, Gateways e Presenters/Adapters — não as portas primárias/secundárias da Hexagonal.

A Hexagonal aparece como base conceitual de partida ("a Arquitetura Limpa e a Arquitetura Hexagonal definem pontos comuns cruciais para um bom projeto de software desde a sua base", Aula 02), não como modelo de referência da disciplina.

**A decisão não implica rewrite.** O núcleo ports/adapters existente permanece integralmente válido: tudo que o material trata como crucial — núcleo de Entidades e Casos de Uso isolado, comunicação externa por abstrações, regra de dependência com interfaces definidas pela camada interna mais injeção de dependência, mundo exterior como detalhe — já existe no codebase. A refatoração adota a **nomenclatura** e a **subdivisão de camadas** da Clean, em particular a separação da borda em Adaptadores de Interface e Frameworks & Drivers, apontada na Aula 02 como a diferença fundamental entre as duas abordagens.

Mapeamento das camadas atuais para as camadas da Clean:

| Camada atual (ADR-003) | Camada Clean (Martin) | Conteúdo no PytStop |
|---|---|---|
| `dominio/` | Entidades | Entidades, agregados, value objects, eventos e exceções de domínio |
| `aplicacao/` | Casos de Uso | Use cases com responsabilidade única, DTOs, ports e UnitOfWork |
| `interfaces/` | Adaptadores de Interface | Controllers (routers FastAPI) e Presenters (schemas Pydantic de request/response) |
| `infraestrutura/` | Frameworks & Drivers | Implementações dos Gateways (repositórios SQLAlchemy), mapeamento ORM, conexão com PostgreSQL |

Sobre os Gateways: a abstração é definida pela camada interna — os ports em `aplicacao/` fazem esse papel, consumidos pelos casos de uso via injeção de dependência (Aulas 04, 08) — e a implementação concreta vive na borda. Isolar todo o acesso a dados via ORM em uma camada usada como Gateway é exatamente o que a Aula 07 aponta como caminho de "alta aderência" às ideias da Clean, e a própria Aula 05 observa que a camada Frameworks & Drivers "em muitos artigos e livros também é chamada de camada de infraestrutura" — o que ancora o mapeamento de `infraestrutura/` nessa camada.

Este ADR **evolui o [ADR-003](../003-arquitetura-ddd-onion.md) e o substitui parcialmente**: a regra de dependência, o isolamento do domínio e a organização por contextos delimitados permanecem; a nomenclatura de camadas da Onion dá lugar à da Clean, e a borda passa a distinguir formalmente Adaptadores de Interface de Frameworks & Drivers.

## Alternativas Consideradas

* Arquitetura Hexagonal formalizada sobre a estrutura atual
* Clean Architecture canônica

### Arquitetura Hexagonal formalizada sobre a estrutura atual

Formalizar como Hexagonal o desenho que o código já pratica: ports em `aplicacao/`, adapters em `infraestrutura/`, núcleo isolado. A refatoração seria mínima — documentação e auditoria de dependências, sem mudança de nomenclatura.

* Bom, porque é o caminho de menor esforço: o gap analysis registra que a estrutura já é ports & adapters (RNF-017)
* Bom, porque é equivalente à Clean nos pontos que o material trata como cruciais: núcleo de Entidades e Casos de Uso isolado (Aulas 02–04), comunicação externa por ports e adapters (Aula 02), regra de dependência com interfaces da camada interna mais injeção (Aula 08) e mundo exterior como detalhe (Aula 07)
* Bom, porque é aceita explicitamente pelo enunciado do challenge
* Ruim, porque o material a trata como base conceitual de partida, não como modelo de referência: das Aulas 03 a 08 o detalhamento normativo é exclusivamente da Clean — falha a condição de "mesmo peso" do critério de decisão
* Ruim, porque o vocabulário de avaliação da disciplina (Casos de Uso, Controllers, Gateways, Presenters — Aulas 04, 05, 08) não é o da Hexagonal; entregar a refatoração nomeada em portas primárias/secundárias criaria atrito entre o código e o vocabulário cobrado
* Ruim, porque não há evidência no material que a aponte como melhor para este codebase: a única vantagem que o material atribui a uma das duas é da Clean ("melhor organização do código", Aula 02)

### Clean Architecture canônica

Adotar o modelo de referência de Robert C. Martin como arquitetura alvo, mapeando as camadas atuais para Entidades, Casos de Uso, Adaptadores de Interface e Frameworks & Drivers, com refatoração de nomenclatura e subdivisão formal da borda.

* Bom, porque o único juízo comparativo do material favorece a Clean: "mais elementos e mais regras, que permitem uma melhor organização do código" (Aula 02)
* Bom, porque alinha o código ao diagrama consolidado na revisão da disciplina (Martin, Aula 08) e ao vocabulário treinado e cobrado nas aulas (Aulas 04, 05, 08)
* Bom, porque o núcleo existente já satisfaz os pré-requisitos que o material trata como inegociáveis: entidades puras sem ORM via mapeamento imperativo ([ADR-006](../006-mapeamento-imperativo-sqlalchemy.md)) — a Aula 03 declara "impossível" implementar a Clean com acoplamento um-pra-um entre entidades e banco —, casos de uso com injeção de dependência e linguagem ubíqua
* Bom, porque a Aula 01 descreve as camadas da Clean com a metáfora das "camadas de uma cebola": o modelo Onion do ADR-003 já respeita as regras de dependência, e a adaptação é de nomenclatura e granularidade, não de capacidade arquitetural
* Ruim, porque a refatoração de nomenclatura e estrutura gera churn em imports e testes em todos os contextos
* Ruim, porque a subdivisão formal da borda em duas camadas adiciona granularidade — e disciplina de revisão — que a Onion atual não exige

## Consequências

### Positivas

* Código e documentação passam a falar o vocabulário avaliado pela disciplina (Casos de Uso, Controllers, Gateways, Presenters), reduzindo atrito na correção do Tech Challenge
* Organização mais granular da borda: a distinção formal entre Adaptadores de Interface e Frameworks & Drivers explicita o que hoje fica implícito entre `interfaces/` e `infraestrutura/`
* O RNF-017 ganha critério auditável: nenhuma importação de `infraestrutura` em `dominio`/`aplicacao`, verificada por lint ou teste de arquitetura
* Núcleo preservado: entidades, casos de uso, ports e a regra de dependência do ADR-003 permanecem — a refatoração é de nomenclatura e subdivisão, não rewrite

### Negativas

* A refatoração de nomenclatura/estrutura concentra-se na primeira onda da refatoração da fase 2 e gera churn em imports e testes de todos os contextos — mitigado pelo gate de cobertura de 95% (`.coveragerc`) e pela suíte de integração, que acusam regressões durante a movimentação
* Risco de a mudança ser tratada como cosmética (renomear sem auditar dependências); a auditoria de imports e a verificação automática exigidas pelo RNF-017 são parte do escopo, não opcionais

### Neutras

* O escopo detalhado da refatoração — ordem dos contextos, movimentações arquivo a arquivo, alocação fina de componentes de borda (ex.: middlewares de autenticação, que a Aula 05 situa em Frameworks & Drivers) e ferramenta de verificação de arquitetura — fica para o plano de execução da refatoração, fora deste ADR

## Decisões Relacionadas

- [ADR-003](../003-arquitetura-ddd-onion.md): DDD com Arquitetura Onion — este ADR o evolui e o substitui parcialmente; quando este ADR for aceito, o ADR-003 recebe a marcação de substituição parcial
- [ADR-005](../005-estrategia-testes.md): Estratégia de testes — o gate de cobertura é a principal mitigação do churn da refatoração
- [ADR-006](../006-mapeamento-imperativo-sqlalchemy.md): Mapeamento imperativo do SQLAlchemy — realiza o pré-requisito de entidades desacopladas do banco (Aula 03); nada a mudar
- [ADR-007](../007-organizacao-contextos-delimitados.md): Contextos delimitados — o agrupamento de casos de uso por contexto segue a "regra de organização coerente" exigida pela Aula 04; a refatoração preserva as fronteiras
- [ADR-009](../009-decisao-de-idioma.md): Modelo híbrido de idioma — os nomes introduzidos pela Clean seguem a convenção PT/EN (domínio em português, sufixos técnicos como `Controller` e `Gateway` em inglês)

## Notas

* Fonte das evidências: disciplina Clean Architecture da fase 2 (FIAP Pos Tech, Aulas 01–08, Erick Muller). As citações por aula referem-se ao material oficial da disciplina
* Requisito formal: RNF-017 ([gap-analysis-fase-2.md](../../../requisitos/fase2/gap-analysis-fase-2.md)); exigência original em [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md)
* O critério de decisão (Hexagonal somente se aceita com o mesmo peso e equivalente ou melhor) foi definido no processo de planejamento da fase 2, antes do fichamento do material

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
