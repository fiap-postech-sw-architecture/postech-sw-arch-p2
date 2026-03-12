# Modelo hibrido de idioma para codigo e documentacao

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O DDD exige que o codigo reflita a Linguagem Ubiqua do dominio. O dominio e uma oficina mecanica brasileira, onde os termos de negocio sao em portugues: CPF, CNPJ, Ordem de Servico, Orcamento, Peca. Ao mesmo tempo, padroes tecnicos como Repository, Service, Event e Port sao universalmente reconhecidos em ingles. Qual idioma usar no codigo?

## Decisao

Adotar um modelo hibrido: termos de negocio em portugues (sem acentos), padroes tecnicos em ingles.

**Regras de nomeacao:**

| Categoria | Idioma | Exemplos |
|---|---|---|
| Entidades e agregados | Portugues | `OrdemDeServico`, `Cliente`, `ItemEstoque` |
| Classes base tecnicas | Ingles | `Entity`, `AggregateRoot`, `ValueObject`, `DomainEvent` |
| Nomes hibridos (dominio + sufixo tecnico) | Misto | `OrdemDeServicoRepository`, `OrcamentoAprovadoEvent`, `EstoquePort` |
| Metodos de dominio | Portugues | `iniciar_diagnostico()`, `aprovar_orcamento()` |
| Arquivos tecnicos | Ingles | `entity.py`, `repository.py`, `events.py`, `exceptions.py` |
| Arquivos de modulo de negocio | Portugues | `cliente.py`, `veiculo.py`, `cpf.py`, `dinheiro.py` |
| Pastas de camada | Portugues | `dominio/`, `aplicacao/`, `infraestrutura/`, `interfaces/` |
| Documentacao | Portugues | ADRs, guias, comentarios de dominio |
| Arquivos de configuracao de IA | Ingles | `.claude/`, regras de agentes |

**Fundamentacao teorica:**

Eric Evans (Domain-Driven Design, 2003): "O codigo deve ser baseado na mesma linguagem usada para escrever os requisitos." Os requisitos deste projeto sao em portugues. Forcar `WorkOrder` em vez de `OrdemDeServico` quebraria a correspondencia direta com os especialistas do dominio.

**Validacao externa:**

Prof. Matheus Llobregat confirmou a adequacao desta abordagem em mensagem no Discord da FIAP em 10/03/2026.

## Alternativas Consideradas

* Modelo hibrido (portugues para dominio, ingles para padroes)
* Tudo em ingles
* Tudo em portugues

### Modelo hibrido (portugues para dominio, ingles para padroes)

Termos de negocio em portugues sem acentos, sufixos e padroes tecnicos em ingles.

* Bom, porque reflete a Linguagem Ubiqua do dominio brasileiro
* Bom, porque stakeholders nao-tecnicos reconhecem os termos de negocio no codigo
* Bom, porque padroes tecnicos (Repository, Event, Port) sao reconheciveis por qualquer desenvolvedor
* Ruim, porque a mistura de idiomas pode confundir novos desenvolvedores (mitigado por glossario e CONTRIBUTING.md)

### Tudo em ingles

Todo o codigo, nomes de classes, metodos e modulos em ingles.

* Bom, porque segue a convencao mais comum em projetos open source
* Bom, porque nao mistura idiomas no codigo
* Ruim, porque desconecta o codigo dos especialistas do dominio — `WorkOrder` nao significa nada para o dono da oficina
* Ruim, porque termos como CPF, CNPJ e Ordem de Servico nao tem traducao natural para ingles
* Ruim, porque viola o principio fundamental do DDD de usar a linguagem dos especialistas

### Tudo em portugues

Todo o codigo em portugues, incluindo padroes tecnicos: `RepositorioOrdemDeServico`, `EventoOrcamentoAprovado`.

* Bom, porque elimina a mistura de idiomas
* Bom, porque e totalmente alinhado com o dominio brasileiro
* Ruim, porque `RepositorioOrdemDeServico` e `ServicoDeAplicacao` sao estranhos para padroes universais
* Ruim, porque dificulta busca por documentacao tecnica — ninguem procura "Repositorio" no Stack Overflow
* Ruim, porque padroes traduzidos perdem o vinculo com a literatura tecnica de referencia

## Consequencias

### Positivas

* O codigo reflete a Linguagem Ubiqua conforme preconizado pelo DDD
* Stakeholders brasileiros reconhecem os termos de negocio diretamente no codigo
* Padroes tecnicos em ingles mantem a legibilidade para qualquer desenvolvedor, independente do idioma nativo
* Termos sem traducao natural (CPF, CNPJ, OS) ficam no idioma original, sem adaptacoes forcadas

### Negativas

* A mistura de idiomas exige disciplina e convencoes claras para manter a consistencia
* Novos desenvolvedores precisam consultar o glossario para entender a convencao (mitigado por documentacao em CONTRIBUTING.md)
* Ferramentas de linting e spell-check podem sinalizar falsos positivos com palavras em portugues
