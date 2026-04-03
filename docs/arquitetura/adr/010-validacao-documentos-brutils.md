# Usar BrUtils para validação de CPF, CNPJ e Placa

* Status: Aceita
* Data: 2026-03-20

## Contexto e Problema

Os Value Objects CPF, CNPJ e Placa exigem validação algorítmica na criação (RF-001: cadastro de cliente; RF-002: cadastro de veículo). CPF e CNPJ requerem cálculo de dígitos verificadores; Placa requer reconhecer formato antigo (AAA-0000) e Mercosul (AAA0A00). Devemos implementar esses algoritmos manualmente ou adotar uma biblioteca externa?

## Decisão

Adotar `brutils` (`>=2.3.0,<3`) como dependência para validação de documentos brasileiros. A biblioteca fornece `is_valid_cpf`, `is_valid_cnpj` e `is_valid_license_plate` com suporte aos dois formatos de placa.

Os Value Objects (`Cpf`, `Cnpj`, `Placa`) continuam como classes de domínio puras: brutils é chamado em `__post_init__` exclusivamente para validação, enquanto os métodos `formatado()` e `mascarado()` do protocolo `Documento` são implementados no próprio Value Object. O valor interno é armazenado normalizado — apenas dígitos para CPF/CNPJ; letras maiúsculas sem hífen para Placa — para garantir igualdade estrutural correta.

Importar brutils no domínio viola a regra de isolar dependências externas (ADR-003), mas a exceção é justificada: a biblioteca é algorítmica pura (sem I/O, sem side effects, sem estado), equivalente a importar `re` ou `math`. Adapter pattern não se aplica.

## Alternativas Consideradas

* brutils
* Implementação manual
* validate-docbr

### brutils

Biblioteca open source (MIT) da organização `brazilian-utils`. Cobre CPF, CNPJ e Placa (formato antigo + Mercosul). Extras úteis: `generate_cpf`/`generate_cnpj` para testes, `convert_license_plate_to_mercosul`.

* Bom, porque cobre os 3 Value Objects com uma única dependência
* Bom, porque `generate_*` simplifica fixtures de teste
* Bom, porque Production/Stable, mantida ativamente, sem vulnerabilidades conhecidas
* Ruim, porque comunidade moderada (~400 stars)
* Ruim, porque adiciona dependência externa ao domínio
* Ruim, porque carrega dependências transitivas (`holidays`, `num2words`)

### Implementação manual

Algoritmos de dígitos verificadores para CPF e CNPJ, regex para placas.

* Bom, porque zero dependências externas
* Bom, porque controle total sobre a lógica
* Ruim, porque duplica código já testado e estável
* Ruim, porque risco de bugs em algoritmos de dígitos verificadores
* Ruim, porque requer manter regex de ambos formatos de placa

### validate-docbr

Biblioteca para validação de documentos brasileiros. Suporta CPF, CNPJ, CNH, RENAVAM, mas não valida formatos de placa (antigo/Mercosul).

* Bom, porque API consistente entre tipos de documento
* Ruim, porque não cobre validação de placa nos formatos exigidos
* Ruim, porque exigiria brutils ou regex manual para placa de qualquer forma

## Consequências

### Positivas

* Validação algorítmica de CPF/CNPJ/Placa pronta e testada
* `generate_*` facilita criação de dados válidos em testes sem fixtures hardcoded, alinhado com a estratégia de dados de teste definida em ADR-005
* Casos de borda tratados pela biblioteca: CPFs com dígitos repetidos (000…0, 111…1), CNPJ zerado, placa com letras minúsculas

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
