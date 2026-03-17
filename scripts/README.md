# Scripts

Scripts utilitários para o projeto.

## export-egn-to-svg.js

Converte diagramas [egon.io](https://egon.io) (`.egn`) para SVG usando Puppeteer (headless Chrome).

### Pré-requisitos

- Node.js 18+
- Puppeteer: `npm install puppeteer`

### Uso

```bash
# Padrão: lê de docs/arquitetura/domain-storytelling/, salva em docs/entrega/assets/
node scripts/export-egn-to-svg.js

# Diretórios customizados
node scripts/export-egn-to-svg.js --egn-dir path/to/egn --out-dir path/to/output
```

### Como funciona

1. Abre o egon.io em headless Chrome via Puppeteer
2. Carrega cada arquivo `.egn` pelo input de upload da página
3. Extrai o SVG renderizado diretamente do DOM
4. Se a extração SVG falhar, salva um PNG como fallback

### Saída

Um arquivo `.svg` por `.egn` no diretório de saída:

| Entrada | Saída |
|---|---|
| `oficina-recepcao-os.egn` | `oficina-recepcao-os.svg` |
| `oficina-diagnostico-orcamento.egn` | `oficina-diagnostico-orcamento.svg` |
| `oficina-execucao-entrega.egn` | `oficina-execucao-entrega.svg` |
| `oficina-gestao-estoque.egn` | `oficina-gestao-estoque.svg` |
| `oficina-acompanhamento-cliente.egn` | `oficina-acompanhamento-cliente.svg` |
