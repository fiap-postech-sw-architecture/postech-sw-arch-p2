# Modelo híbrido de idioma para código e documentação

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-03-20

## Contexto e Problema

O DDD exige que o código reflita a Linguagem Ubíqua do domínio. O domínio é uma oficina mecânica brasileira, onde os termos de negócio são em português: CPF, CNPJ, Ordem de Servico, Orcamento, Peca. Ao mesmo tempo, padrões técnicos como Repository, Service, Event e Port são universalmente reconhecidos em inglês. Qual idioma usar no código?

## Decisão

Adotar um modelo híbrido: termos de negócio em português (sem acentos), padrões técnicos em inglês.

**Regras de nomeação:**

| Categoria | Idioma | Exemplos |
|---|---|---|
| Entidades e agregados | Português | `OrdemDeServico`, `Cliente`, `ItemEstoque` |
| Classes base técnicas | Inglês | `Entity`, `AggregateRoot`, `ValueObject`, `DomainEvent` |
| Nomes híbridos (domínio + sufixo técnico) | Misto | `OrdemDeServicoRepository`, `OrcamentoAprovadoEvent`, `EstoquePort` |
| Métodos de domínio | Português | `iniciar_diagnostico()`, `aprovar_orcamento()` |
| Arquivos técnicos | Inglês | `entity.py`, `repository.py`, `events.py`, `exceptions.py` |
| Arquivos de módulo de negócio | Português | `cliente.py`, `veiculo.py`, `cpf.py`, `dinheiro.py` |
| Pastas de camada | Português | `dominio/`, `aplicacao/`, `infraestrutura/`, `interfaces/` |
| Documentação | Português | ADRs, guias, comentários de domínio |
| Arquivos de configuração de IA | Inglês | `.claude/`, regras de agentes |

**Fundamentação teórica:**

Eric Evans (Domain-Driven Design, 2003): "O código deve ser baseado na mesma linguagem usada para escrever os requisitos." Os requisitos deste projeto são em português. Forçar `WorkOrder` em vez de `OrdemDeServico` quebraria a correspondência direta com os especialistas do domínio.

**Validação externa:**

Prof. Matheus Llobregat confirmou a adequação desta abordagem em mensagem no Discord da FIAP em 10/03/2026.

## Alternativas Consideradas

* Modelo híbrido (português para domínio, inglês para padrões)
* Tudo em inglês
* Tudo em português

### Modelo híbrido (português para domínio, inglês para padrões)

Termos de negócio em português sem acentos, sufixos e padrões técnicos em inglês.

* Bom, porque reflete a Linguagem Ubíqua do domínio brasileiro
* Bom, porque stakeholders não-técnicos reconhecem os termos de negócio no código
* Bom, porque padrões técnicos (Repository, Event, Port) são reconhecíveis por qualquer desenvolvedor
* Ruim, porque a mistura de idiomas pode confundir novos desenvolvedores (mitigado por glossário e CONTRIBUTING.md)

### Tudo em inglês

Todo o código, nomes de classes, métodos e módulos em inglês.

* Bom, porque segue a convenção mais comum em projetos open source
* Bom, porque não mistura idiomas no código
* Ruim, porque desconecta o código dos especialistas do domínio — `WorkOrder` não significa nada para o dono da oficina
* Ruim, porque termos como CPF, CNPJ e Ordem de Servico não têm tradução natural para inglês
* Ruim, porque viola o princípio fundamental do DDD de usar a linguagem dos especialistas

### Tudo em português

Todo o código em português, incluindo padrões técnicos: `RepositorioOrdemDeServico`, `EventoOrcamentoAprovado`.

* Bom, porque elimina a mistura de idiomas
* Bom, porque é totalmente alinhado com o domínio brasileiro
* Ruim, porque `RepositorioOrdemDeServico` e `ServicoDeAplicacao` são estranhos para padrões universais
* Ruim, porque dificulta busca por documentação técnica — ninguém procura "Repositorio" no Stack Overflow
* Ruim, porque padrões traduzidos perdem o vínculo com a literatura técnica de referência

## Consequências

### Positivas

* O código reflete a Linguagem Ubíqua conforme preconizado pelo DDD
* Stakeholders brasileiros reconhecem os termos de negócio diretamente no código
* Padrões técnicos em inglês mantêm a legibilidade para qualquer desenvolvedor, independente do idioma nativo
* Termos sem tradução natural (CPF, CNPJ, OS) ficam no idioma original, sem adaptações forçadas

### Negativas

* A mistura de idiomas exige disciplina e convenções claras para manter a consistência
* Novos desenvolvedores precisam consultar o glossário para entender a convenção (mitigado por documentação em CONTRIBUTING.md)
* Ferramentas de linting e spell-check podem sinalizar falsos positivos com palavras em português

## Decisões Relacionadas

- [ADR-010](010-validacao-documentos-brutils.md): Validação com brutils — encapsula API em inglês da biblioteca dentro de Value Objects com interface em português, seguindo este ADR

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
