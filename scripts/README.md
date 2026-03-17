# Scripts

Scripts de build e conversão de artefatos para a entrega da Fase 1.

## export-egn-to-svg.js

Converte diagramas [egon.io](https://egon.io) (`.egn`) para SVG usando Puppeteer (headless Chrome). Usado na entrega da Fase 1 para incluir os diagramas Domain Storytelling no PDF.

### Pré-requisitos

- Node.js 18+
- Puppeteer: `npm install puppeteer`

O Puppeteer baixa automaticamente uma versão do Chromium (várias centenas de MB).

### Uso

```bash
# Padrão: lê de docs/arquitetura/domain-storytelling/, salva em docs/entrega/assets/
node scripts/export-egn-to-svg.js

# Diretórios customizados
node scripts/export-egn-to-svg.js --egn-dir path/to/egn --out-dir path/to/output
```

O script encerra com código 1 se o diretório ou arquivos `.egn` não existirem.

### Como funciona

Abre o egon.io em headless Chrome, carrega cada `.egn` pelo input de upload e extrai o SVG do DOM. Se a extração falhar, salva um screenshot PNG como fallback.

### Saída

Gera um `.svg` (ou `.png` em fallback) por `.egn` no diretório de saída, com o mesmo nome base.

### Alternativa manual

Se Puppeteer não estiver disponível, abrir cada `.egn` em https://egon.io, File → Export → SVG, salvar em `docs/entrega/assets/`.
