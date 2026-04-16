> Documento original transcrito do PDF fornecido pela FIAP em mar/2026.
> Cópia verbatim — nenhuma edição foi feita no conteúdo abaixo.

# Tech Challenge - Fase 1

## Sobre o Tech Challenge

Tech Challenge é o projeto da fase que englobará os conhecimentos obtidos em todas as disciplinas da fase. Esta é uma atividade que, em princípio, deve ser desenvolvida em grupo. Importante atentar-se ao prazo de entrega, pois trata-se de uma atividade obrigatória, uma vez que vale 90% da nota desta fase.

## Desafio

Uma oficina mecânica de médio porte, especializada em manutenção de veículos, tem enfrentado desafios para expandir seus serviços com qualidade e eficiência.

Atualmente, o processo de atendimento, diagnóstico, execução de serviços e entrega dos veículos é feito de forma desorganizada, utilizando anotações manuais e planilhas, o que gera alguns problemas, como:

- Erros na priorização dos atendimentos;
- Falhas no controle de peças e insumos;
- Dificuldade em acompanhar o status dos serviços;
- Perda de histórico de clientes e veículos;
- Ineficiência no fluxo de orçamentos e autorizações.

Diante disso, a oficina decidiu investir em um **Sistema Integrado de Atendimento e Execução de Serviços**, que permitirá aos clientes acompanhar em tempo real o andamento do serviço, autorizar reparos adicionais via aplicativo e garantir uma gestão interna eficiente e segura.

## Proposta

Desenvolver a primeira versão (**MVP**) do back-end do sistema da oficina, com foco em gestão de ordens de serviço, clientes e peças, aplicando **Domain-Driven Design (DDD)** e garantindo boas práticas de **Qualidade de Software e Segurança**.

## Funcionalidades obrigatórias

### Fluxos principais

**Criação da Ordem de Serviço (OS):**

- Identificação do cliente por CPF/CNPJ;
- Cadastro de veículo (placa, marca, modelo, ano);
- Inclusão dos serviços solicitados (exemplo: troca de óleo, alinhamento);
- Possibilidade de incluir peças e insumos necessários;
- Orçamento gerado automaticamente com base nos serviços e peças;
- Envio do orçamento ao cliente para aprovação.

**Acompanhamento da OS:**

- Status da OS:
  - Recebida;
  - Em diagnóstico;
  - Aguardando aprovação;
  - Em execução;
  - Finalizada;
  - Entregue.
- Alteração automática dos status conforme ações no sistema;
- Permitir consulta por parte do cliente via API para acompanhar o progresso.

**Gestão administrativa:**

- CRUD de clientes;
- CRUD de veículos;
- CRUD de serviços;
- CRUD de peças e insumos, com controle de estoque;
- Listagem e detalhamento de ordens de serviço;
- Monitoramento do tempo médio de execução dos serviços.

**Segurança e qualidade:**

- Implementação de autenticação JWT para APIs administrativas;
- Validação dos dados sensíveis (CPF/CNPJ, placa de veículo);
- Testes unitários e de integração para os principais fluxos.

## Requisitos técnicos

- **Back-end monolítico.**
- **Como será um MVP, é possível criar um Monolito utilizando a arquitetura em camadas.**
- A escolha do banco de dados é livre, mas é necessário justificar a preferência pelo banco utilizado.
- APIs RESTful documentadas via Swagger ou similar.
- **Dockerfile** para build da aplicação.
- **docker-compose.yml** para orquestrar ambiente completo.
- Testes automatizados com cobertura mínima de 80% nos domínios críticos.
- Configuração para execução local simples (README.md explicativo).
- Organização em repositório privado com acesso ao usuário `soat-architecture`

## Entregáveis da Fase 1

- **Vídeo de até 15 minutos** demonstrando todos os pontos (pode ser em grupo ou individual);
- **Documentação DDD** (Miro ou equivalente), com:
  - Event Storming completo dos fluxos:
    - Criação e acompanhamento da OS;
    - Gestão de peças e insumos;
  - Diagramas conforme apresentado na disciplina de DDD;
  - Linguagem Ubíqua aplicada.
- **Código-fonte** no repositório privado, incluindo:
  - APIs conforme requisitos;
  - Dockerfile e `docker-compose.yml` configurados;
  - README.md completo com instruções de uso e objetivos.
- **Relatório com análise de vulnerabilidades:**
  - Adicionar no relatório a análise do scan realizado no código.
- **Documento de entrega (PDF)** com:
  - Nome do grupo;
  - Participantes e usernames no Discord;
  - Link da documentação;
  - Link do repositório;
  - Relatório com análise de vulnerabilidades encontradas no sistema.
