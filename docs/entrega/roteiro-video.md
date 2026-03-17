# Roteiro do Vídeo — Fase 1

Duração alvo: ~14 minutos (1 min de folga dentro do limite de 15 min).

## Estrutura

### 1. Introdução (1 min)

- Apresentação: nome, turma 15SOAT, projeto do grupo PytStop
- Visão geral: MVP back-end de oficina mecânica com DDD
- Stack: Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL 16
- Objetivo: demonstrar domínio de DDD, qualidade e segurança

### 2. Arquitetura (1.5 min)

- Monolito modular com DDD e Onion Architecture
- 5 contextos delimitados: mostrar mapa de contextos (Mermaid renderizado)
  - Ordem de Serviço e Estoque (principais), Cliente+Veículo, Catálogo, Autenticação
- 4 camadas por contexto: domínio, aplicação, infraestrutura, interfaces
- Comunicação via portas e adaptadores (in-process)
- Mostrar diagrama de classes do agregado OrdemDeServico

### 3. Linguagem Ubíqua (0.5 min)

- Modelo híbrido (ADR-009): negócio em PT, padrões em EN
- Exemplos no código: `OrdemDeServicoRepository`, `aprovar_orcamento()`, `EstoquePort`
- Mostrar glossário brevemente

### 4. Event Storming (2 min)

- Walkthrough do fluxo 1: ciclo de vida da OS
  - Recebida → EmDiagnostico → AguardandoAprovacao → EmExecucao → Finalizada → Entregue
  - Cancelamento como caminho alternativo
- Walkthrough do fluxo 2: gestão de estoque
  - Reserva na aprovação, liberação no cancelamento
  - Bloqueio pessimista (SELECT FOR UPDATE NOWAIT)
- Mostrar diagramas de Event Storming na documentação (Mermaid renderizado)

### 5. Demo ao Vivo (5 min)

Demonstrar o fluxo completo via Swagger UI:

1. **Login**: `POST /autenticacao/login` → obter JWT
2. **Cadastrar cliente**: `POST /clientes` com CPF
3. **Adicionar veículo**: `POST /clientes/{id}/veiculos`
4. **Cadastrar serviço**: `POST /servicos`
5. **Cadastrar item estoque**: `POST /estoque`
6. **Criar OS**: `POST /ordens-de-servico`
7. **Adicionar item à OS**: `POST /ordens-de-servico/{id}/itens`
8. **Iniciar diagnóstico**: `POST /ordens-de-servico/{id}/diagnostico`
9. **Gerar orçamento**: `POST /ordens-de-servico/{id}/orcamento`
10. **Aprovar orçamento**: `POST /ordens-de-servico/{id}/aprovacao` (verificar estoque decrementado)
11. **Finalizar**: `POST /ordens-de-servico/{id}/finalizacao`
12. **Entregar**: `POST /ordens-de-servico/{id}/entrega`
13. **Consulta pública**: `GET /acompanhamento?placa=ABC1D23&documento=12345678901`
14. **Métricas**: `GET /ordens-de-servico/metricas`

Demonstrar cancelamento (segunda OS):

15. **Criar segunda OS** e avançar até EmExecucao (verificar estoque decrementado)
16. **Cancelar OS em execução**: `POST /ordens-de-servico/{id}/cancelamento` (verificar estoque restaurado)

### 6. Code Walkthrough (2 min)

- Agregado `OrdemDeServico`: mostrar métodos de domínio, `MaquinaDeStatus`
- Objeto de valor `Dinheiro`: imutabilidade, precisão
- Mapeamento imperativo: `iniciar_mapeamentos()` separado das entidades
- Repository: interface no domínio, implementação na infraestrutura
- Portas: `EstoquePort.reservar()` com `UnitOfWork` compartilhada

### 7. DevOps + Segurança (1.5 min)

- `docker-compose up` com migrações automáticas (Alembic)
- Testes: `make test` com cobertura por faixa
- Scans: SonarQube, OWASP ZAP, bandit, pip-audit, gitleaks, trivy
- Mostrar relatório de cobertura (pytest-cov)
- Mostrar output do bandit (sem vulnerabilidades críticas)
- Setup: `README.md` com instruções completas

### 8. Encerramento (0.5 min)

- Resumo das decisões técnicas (ADRs)
- Documentação completa em `docs/`
- Repositório privado com `soat-architecture` como colaborador

## Notas de Produção

- Gravar com tela compartilhada + câmera (opcional)
- Terminal com fonte grande (14pt+) para legibilidade
- Swagger UI em tela cheia durante a demo
- Ter dados de teste pré-preparados para evitar digitação ao vivo
- Verificar que `docker-compose up` funciona antes de gravar
