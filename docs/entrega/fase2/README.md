# Entrega — Fase 2

> [↑ Raiz do projeto](../../../README.md) · [↑ Entrega](../README.md)

> **Versão**: 1.0 — Fase 2.

Artefatos da entrega da Fase 2 do Tech Challenge FIAP. Os artefatos da fase 1 permanecem na [pasta pai](../README.md).

## Documentos

| Arquivo | Descrição |
|---------|-----------|
| [entrega-fase-2.md](entrega-fase-2.md) | Documento de entrega (origem do PDF) — grupo, repositório, vídeo, documentação e rastreabilidade requisito → evidência |
| [roteiro-video.md](roteiro-video.md) | Roteiro cronometrado do vídeo de demonstração (deploy, CI/CD, APIs, HPA, traces) |
| [postman_collection.json](postman_collection.json) | Collection Postman gerada do contrato OpenAPI vivo (46 requisições agrupadas por tag) |

## Regerar a collection

Com a stack local no ar (`make up-backend`):

```bash
curl -s localhost:8000/openapi.json > /tmp/openapi.json
npx -y openapi-to-postmanv2 -s /tmp/openapi.json \
  -o docs/entrega/fase2/postman_collection.json -p -O folderStrategy=Tags
```

## Gerar o PDF de submissão

Mesmo fluxo da fase 1, com um passo extra que renderiza o diagrama Mermaid em imagem (pandoc não renderiza Mermaid). Da raiz do repo:

```bash
bash scripts/build-entrega-pdf.sh
```

O script ([`scripts/build-entrega-pdf.sh`](../../../scripts/build-entrega-pdf.sh)) reescreve os links relativos para URLs absolutas do GitHub (`rewrite-md-links.py`), gera o PNG do diagrama via mermaid-cli e roda `pandoc --pdf-engine=weasyprint`; o artefato sai **fora do repo**, em `~/git/fiap/postech-sw-architecture/documento-entrega-fase-2.pdf`. Regerar após preencher o link do vídeo (marcador `VIDEO-LINK-FASE-2`).

## Relação com Outros Documentos

- [Desafio Tech Fase 2](../../requisitos/fase2/desafio-tech-fase-2.md) — enunciado original (entregáveis exigidos)
- [Gap analysis](../../requisitos/fase2/gap-analysis-fase-2.md) — requisitos RF-020–024, RNF-017–024, RN-018–020
- [RFC-002](../../arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) — desenho integrado e diagrama de referência
- [Entrega da Fase 1](../entrega-fase-1.md) — documento de entrega anterior

> [↑ Raiz do projeto](../../../README.md) · [↑ Entrega](../README.md)
