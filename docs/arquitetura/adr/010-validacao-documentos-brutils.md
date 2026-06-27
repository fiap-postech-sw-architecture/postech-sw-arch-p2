# Usar BrUtils para validação de CPF e CNPJ (Placa via regex própria)

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-03-20

## Contexto e Problema

Os Value Objects CPF, CNPJ e Placa exigem validação algorítmica na criação (RF-001: cadastro de cliente; RF-002: cadastro de veículo). CPF e CNPJ requerem cálculo de dígitos verificadores; Placa requer reconhecer formato antigo (AAA-0000) e Mercosul (AAA0A00). Devemos implementar esses algoritmos manualmente ou adotar uma biblioteca externa? O brutils cobre apenas CPF e CNPJ; a validação de placa fica fora do escopo da biblioteca e precisa ser resolvida à parte.

## Decisão

Adotar `brutils` (`>=2.3.0,<3`) como dependência para validação de **CPF e CNPJ**. A biblioteca fornece `is_valid_cpf` e `is_valid_cnpj` — usados em `src/cliente_veiculo/dominio/cpf.py` e `cnpj.py`. A **Placa** fica fora do escopo do brutils e é validada por **regex própria** em `src/cliente_veiculo/dominio/placa.py`, cobrindo o formato antigo (`ABC1234`) e o Mercosul (`ABC1D23`).

Os Value Objects (`Cpf`, `Cnpj`, `Placa`) continuam como classes de domínio puras: a validação acontece em `__post_init__` — brutils para CPF/CNPJ, regex para Placa — enquanto os métodos `formatado()` e `mascarado()` do protocolo `Documento` são implementados no próprio Value Object. O valor interno é armazenado normalizado — apenas dígitos para CPF/CNPJ; letras maiúsculas sem hífen para Placa — para garantir igualdade estrutural correta.

Importar brutils no domínio viola a regra de isolar dependências externas (ADR-003), mas a exceção é justificada: a biblioteca é algorítmica pura (sem I/O, sem side effects, sem estado), equivalente a importar `re` ou `math` — assim como a Placa usa `re` diretamente. Adapter pattern não se aplica.

## Alternativas Consideradas

* brutils
* Implementação manual
* validate-docbr

### brutils

Biblioteca open source (MIT) da organização `brazilian-utils`. Cobre **CPF e CNPJ** (validação de dígitos verificadores). Não valida placas — a Placa fica a cargo de regex própria. Extras opcionais: `generate_cpf`/`generate_cnpj` para fixtures de teste.

* Bom, porque cobre CPF e CNPJ com uma única dependência algorítmica
* Bom, porque expõe `generate_*` como recurso opcional para fixtures (não adotado até o momento)
* Bom, porque Production/Stable, mantida ativamente, sem vulnerabilidades conhecidas
* Ruim, porque não cobre Placa — exige regex própria de qualquer forma
* Ruim, porque comunidade moderada (~400 stars)
* Ruim, porque adiciona dependência externa ao domínio
* Ruim, porque carrega dependências transitivas (`holidays`, `num2words`)

### Implementação manual

Algoritmos de dígitos verificadores para CPF e CNPJ, regex para placas.

* Bom, porque zero dependências externas
* Bom, porque controle total sobre a lógica
* Ruim, porque duplica código já testado e estável
* Ruim, porque risco de bugs em algoritmos de dígitos verificadores
* Ruim, porque requer manter regex de ambos os formatos de placa

### validate-docbr

Biblioteca para validação de documentos brasileiros. Suporta CPF, CNPJ, CNH, RENAVAM, mas não valida formatos de placa (antigo/Mercosul).

* Bom, porque API consistente entre tipos de documento
* Ruim, porque, assim como brutils, não cobre validação de placa nos formatos exigidos (regex própria seria necessária de qualquer forma)
* Ruim, porque não traz vantagem decisiva sobre brutils para o escopo CPF/CNPJ

## Consequências

### Positivas

* Validação algorítmica de CPF/CNPJ pronta e testada pela biblioteca; Placa validada por regex própria simples e auditável
* `generate_*` está disponível como recurso opcional para fixtures, alinhado com a estratégia de dados de teste do ADR-005 — ainda não utilizado no código atual
* Casos de borda de CPF/CNPJ tratados pela biblioteca: dígitos repetidos (000…0, 111…1), CNPJ zerado; placas com letras minúsculas são normalizadas pela própria `Placa` (`upper()` + remoção de hífen) antes da checagem por regex

### Negativas

* Dependência externa no domínio — se abandonada, fork necessário (MIT permite)
* Dependências transitivas (`holidays`, `num2words`) aumentam superfície de atualização
* Nomes de API em inglês (`is_valid_cpf`) no meio de código em português — mitigado pelo encapsulamento nos Value Objects, que expõem apenas a interface em português (ADR-009)

## Decisões Relacionadas

- [ADR-003](003-arquitetura-ddd-onion.md): DDD com Arquitetura Onion — exceção justificada à regra de isolar dependências externas do domínio
- [ADR-005](005-estrategia-testes.md): Estratégia de testes — `generate_cpf`/`generate_cnpj` do brutils alinhados com a estratégia de dados de teste
- [ADR-009](009-decisao-de-idioma.md): Modelo híbrido de idioma — API em inglês do brutils encapsulada por Value Objects com interface em português

## Notas

* PyPI: https://pypi.org/project/brutils/
* GitHub: https://github.com/brazilian-utils/brutils-python
* Licença: MIT
* Versão: `>=2.3.0,<3` em `pyproject.toml`

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
