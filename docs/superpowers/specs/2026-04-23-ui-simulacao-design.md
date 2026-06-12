# UI de Simulacao para Testes Manuais — Design

- **Data**: 2026-04-23
- **Status**: Implementado (referencia historica) — ver PR #81 para a verdade do que foi entregue
- **Escopo**: Fase 1 (postech-sw-arch-p1)
- **Autor**: Joao Amaral (com apoio do brainstorming Claude)

> **Nota de reconciliacao (apos merge do PR #81)**
>
> Este documento captura o design original. Algumas decisoes evoluiram
> durante a implementacao com base em testes E2E e revisoes:
>
> - **Mascaramento de token**: spec previa `Authorization: Bearer ****` no
>   painel HTTP. Estrategia final: headers NUNCA sao registrados em
>   ``RegistroHttp`` (zero-trust por omissao). Ver `ui/cliente_api.py:91-96`.
> - **Coverage gate de UI**: spec falava em 60%. Final: 95% (cobertura real
>   ficou em ~98% nos modulos puros).
> - **Seed de dados**: spec dimensionava ~3 clientes, 5 veiculos, 5 servicos,
>   10 itens, 4 OS. Final: 7/10/8/14/8 com OS em 7 estados diferentes.
> - **Endpoints LGPD no painel HTTP**: response body de
>   `/dados-pessoais/exportar` e redacted (PII consolidada nao entra no
>   historico).
>
> Para o estado atual entregue, ver: ui/README.md, README raiz secao "UI",
> e a description do PR #81.

## 1. Contexto e objetivo

O backend FastAPI da Fase 1 (PytStop) expoe ~40 endpoints distribuidos em 5 contextos delimitados (cliente_veiculo, catalogo_servicos, estoque, ordem_servico, autenticacao) mais o endpoint publico de acompanhamento. Hoje a unica forma de exercita-los e via Swagger UI (`/docs`) ou curl/httpie.

Para testes manuais integrados — abrir o sistema, clicar a esmo por diferentes papeis, ver OS atravessando a maquina de estados, validar RBAC e LGPD — a experiencia Swagger e desconfortavel: precisa copiar UUIDs manualmente, alternar tokens a mao, sem visibilidade do estado atual da OS.

Este documento especifica uma **UI de simulacao** dedicada a testes manuais aleatorios, rodando lado a lado com o backend, sem substitui-lo nem alterar nada do codigo existente em `src/`.

### Objetivos

- Sandbox integrado que permita exercitar o sistema inteiro sem sair da UI.
- Troca rapida entre os 3 papeis (admin, atendente, mecanico) sem login manual.
- Pickers de recursos em vez de campos de UUID.
- Geracao de dados de teste com um clique, em massa coerente.
- Painel de request/response pra validar contratos da API durante o teste.
- Visualizacao da maquina de estados da OS com botoes condicionais.
- Acesso tanto local (`uv run python -m ui`) quanto via docker (`docker compose up`).

### Nao-objetivos

- Nao e artefato de producao. Nao entra no Dockerfile do backend. Nao e promovida a entregavel da Fase 1.
- Nao substitui o Swagger UI — ambos coexistem. Swagger e referencia crua da API; UI e sandbox integrado.
- Nao re-implementa validacao de negocio client-side. Formularios submetem e renderizam o erro do backend.
- Sem dark mode, i18n, mobile responsivo, graficos alem de cards de metricas.
- Sem testes E2E automatizados em CI (overhead alto pra ROI baixo numa ferramenta de dev).

### Entregas de apoio fora do escopo desta UI

- `scripts/seed_usuarios.py` (novo): cria admin + atendente + mecanico no banco, idempotente. Pre-condicao pro switcher de papel funcionar. Escreve direto no banco (mesma abordagem que o `scripts/seed_admin.py` existente usa) porque o endpoint `POST /api/v1/autenticacao/registrar` do backend hoje nao aceita `papel` como parametro e sempre cria com papel default. Credenciais dev-only ficam fixas em `ui/config.py`.
- `scripts/seed_admin.py` (existente) nao e alterado — segue sendo o bootstrap oficial do admin via env vars (`ADMIN_EMAIL`, `ADMIN_PASSWORD`). Os dois scripts podem compartilhar utilitarios internamente (detalhe pro `writing-plans`).

## 2. Arquitetura

### 2.1 Processo e deploy

Dois processos Python independentes:

| Processo | URL local | URL docker | Porta |
|---|---|---|---|
| Backend FastAPI (existente) | http://localhost:8001 | http://localhost:8000 | 8001 (dev) / 8000 (docker) |
| UI NiceGUI (novo) | http://localhost:8080 | http://localhost:8080 | 8080 |

O browser fala com a UI NiceGUI. A UI (em Python server-side) consome o backend via `httpx`. **O browser nunca fala direto com o backend**, o que tem duas consequencias importantes:

1. Zero alteracao em CORS — `CORS_ORIGINS` do backend nao precisa incluir a URL da UI.
2. O "painel de request/response" registra os pares que o processo UI trocou com o backend, nao o Network tab do browser. E mais preciso pra validar contratos.

### 2.2 Tecnologia

**NiceGUI** como framework de UI em Python puro. Produz SPA reativa (Quasar+Vue sob o capo) mas o desenvolvedor so escreve Python. Suporte nativo a routing, state via WebSocket, componentes de dashboard (tabs, tables, dropdowns, dialogs, drawers).

Dependencias novas (extra opcional `ui` no `pyproject.toml`):
- `nicegui >= 2.0`
- `httpx >= 0.27` (se ainda nao estiver presente)

Nao pesa no container de producao (`ui` nao entra no Dockerfile do backend). Nao entra no CI principal do backend, mas entra em um job paralelo (lint + mypy + tests do diretorio `ui/`).

### 2.3 Estrutura de diretorios

```
postech-sw-arch-p1/
├── src/                      # backend FastAPI (existente, intocado)
├── ui/                       # nova UI NiceGUI
│   ├── __init__.py
│   ├── __main__.py           # entrypoint: uv run python -m ui
│   ├── app.py                # NiceGUI setup + roteamento
│   ├── config.py             # BACKEND_URL, UI_PORT, credenciais seed
│   ├── cliente_api.py        # httpx wrapper + captura req/res + refresh auto
│   ├── estado.py             # acesso tipado a app.storage (sessao, historico)
│   ├── paginas/
│   │   ├── login.py
│   │   ├── dashboard.py
│   │   ├── clientes.py
│   │   ├── catalogo.py
│   │   ├── estoque.py
│   │   ├── ordens_servico.py
│   │   └── acompanhamento.py
│   ├── componentes/
│   │   ├── cabecalho.py      # role switcher + logout
│   │   ├── painel_http.py    # drawer req/res
│   │   ├── maquina_estados.py # stepper + botoes de transicao
│   │   ├── picker_recurso.py  # generico (clientes, veiculos, etc)
│   │   └── dialogo_confirmacao.py
│   ├── seed.py               # gerador de dados de teste
│   ├── Dockerfile            # imagem dedicada, dev-only
│   └── README.md             # docs tecnicas da UI
├── scripts/
│   └── seed_usuarios.py      # cria admin+atendente+mecanico (novo)
├── tests/
│   └── unitarios/
│       └── ui/               # testes pytest da UI
├── docker-compose.yml        # passa a incluir servico `ui`
├── Makefile                  # novos targets: ui, seed-users, up-backend
├── pyproject.toml            # novo extra [ui]
└── README.md                 # nova secao "UI de Simulacao"
```

### 2.4 Convencoes (ADR-009)

Mesmas regras do backend:

- Arquivos tecnicos em EN: `app.py`, `config.py`, `cliente_api.py`, `estado.py`, `seed.py`
- Arquivos de negocio em PT: `clientes.py`, `veiculos.py`, `catalogo.py`, `ordens_servico.py`, `acompanhamento.py`
- Classes: `ClienteApi`, `RegistroHttp`, `Transicao`, `StepperOs`, `ClientesPage`, `OrdensServicoPage`
- Metodos/variaveis: snake_case PT para dominio (`papel_atual`, `token_atual`, `listar_clientes`)
- Mensagens visiveis ao usuario: PT
- Logs: EN
- Identifiers tecnicos: EN (httpx, async, Pydantic, etc.)

## 3. Paginas e componentes

### 3.1 Shell da app

Layout persistente em paginas autenticadas:

```
+----------------------------------------------------------+
| CABECALHO: nav · [role switcher] · email · logout        |
+--------------------------------------------+-------------+
|                                            |             |
|              CONTEUDO DA PAGINA            | PAINEL HTTP |
|                                            | (colapsavel)|
|                                            |             |
+--------------------------------------------+-------------+
```

- **Cabecalho fixo**: nav horizontal com `Dashboard · Clientes · Catalogo · Estoque · OS · Acompanhamento`, role switcher a direita como `ui.select` com 3 opcoes, email do usuario atual, badge colorido do papel, botao logout.
- **Painel HTTP**: `ui.drawer` a direita, colapsavel via icone. Consumir os eventos publicados por `cliente_api.py`.
- **Conteudo**: troca por rota NiceGUI (`@ui.page('/clientes')`, `@ui.page('/ordens-servico/{id}')` etc).

Exceptions ao shell:
- `/login`: tela cheia, sem shell.
- `/acompanhamento`: tela cheia, simula visao do cliente final (sem auth).

### 3.2 Paginas

**Login (`/login`)**
Formulario email+senha. Botoes de atalho "Entrar como admin / atendente / mecanico" preenchem credenciais do `config.py`. Indicador de health do backend (`/api/v1/saude`) visivel. Se os 3 usuarios seed nao existirem, mostra instrucoes inline em vez de so "credenciais invalidas".

**Dashboard (`/`)**
Cards com metricas (quando papel=admin, via `/ordens-de-servico/metricas`): total de OS, contagem por status, tempo medio de execucao. Botao destacado "🎲 Gerar dados de teste" (desabilitado se papel != admin, tooltip explica). Atalho "Nova OS" pro fluxo mais comum.

**Clientes (`/clientes`)**
Tabela paginada via `/clientes?offset&limit`. Linha expansivel lista os veiculos do cliente. Dialog pra criar/editar. Menu kebab com acoes LGPD (consentimento, exportar dados, excluir dados).

**Catalogo (`/catalogo`)**
Tabela paginada via `/servicos`. Dialog criar/editar. Desativar com confirmacao.

**Estoque (`/estoque`)**
Tabela paginada via `/estoque`. Coluna quantidade com controle inline (+/− + input) que dispara `PATCH /estoque/{id}/quantidade`. Itens com quantidade < 5 destacados em amarelo.

**Ordens de Servico (`/ordens-servico` e `/ordens-servico/{id}`)**

Lista: paginada, filtro client-side por status, coluna status colorida.

Detalhe (3 paineis empilhados):
1. Cabecalho da OS (id, cliente, veiculo, datas, badge grande de status).
2. Stepper da maquina de estados (secao 4) + grid de botoes das transicoes validas.
3. Itens da OS (tabela + botao "Adicionar item" via dialog com pickers). Orcamento exibido quando presente.

Criacao: dialog com `ClientePicker` e `VeiculoPicker` (o segundo filtra pelos veiculos do cliente escolhido).

**Acompanhamento (`/acompanhamento`)**
Tela publica sem auth. Dois campos: placa + documento. Botao consulta `/api/v1/acompanhamento`. Resultado mostra status e timestamps. Util pra testar o fluxo publico e o rate limiting (10/min por IP).

### 3.3 Componentes reutilizaveis

| Componente | Proposito |
|---|---|
| `PickerRecurso[T]` | Dropdown generico populado via endpoint de listagem, cache de 30s por sessao |
| `CabecalhoApp` | Topo fixo, le `estado.papel_atual()` |
| `PainelHttp` | Drawer req/res com filtro por faixa de status e busca |
| `StepperOs` | Desenha os 7 estados e highlight do atual |
| `BotoesTransicao` | Grid de botoes calculado por (status, papel) |
| `DialogoConfirmacao` | Confirm generico pra deletes e cancelamentos |

## 4. Fluxo de dados, autenticacao e captura HTTP

### 4.1 State management (`ui/estado.py`)

Uso intencional dos 3 escopos de storage do NiceGUI:

| Dado | Escopo | Justificativa |
|---|---|---|
| `access_token`, `refresh_token`, email, papel | `app.storage.user` | Persiste entre reloads (cookie assinado); evita relogar a cada F5 |
| Historico do painel HTTP (ultimos 50) | `app.storage.tab` | Por aba; reload limpa (comportamento esperado) |
| Cache de pickers (TTL 30s) | modulo in-memory | Evita flood de GETs ao abrir dropdowns |

Acesso exclusivamente via funcoes tipadas — nenhuma pagina toca `app.storage.*` diretamente.

### 4.2 Fluxo de autenticacao

**Login manual**
1. Email+senha → `POST /api/v1/autenticacao/login`
2. Resposta com `access_token`+`refresh_token` armazenada em `estado.salvar_sessao()`
3. JWT decodificado sem verificar assinatura apenas pra extrair `email` e `papel` para exibicao
4. Redireciona pro dashboard

**Troca de papel (requisito A)**

```
switcher.on_change('atendente'):
  → api.logout()                    # best-effort, ignora erro
  → api.login(cred['atendente'])    # credenciais do config.py
  → estado.salvar_sessao(novos_tokens, email, 'atendente')
  → ui.navigate.reload()
```

Requer que os 3 usuarios existam no banco (`scripts/seed_usuarios.py`).

**Refresh automatico**

Em 401 de qualquer endpoint que nao seja `/refresh` nem `/login`:
1. Tenta `POST /refresh` com o refresh_token armazenado
2. Sucesso → atualiza tokens e retenta a chamada original **uma vez**
3. Falha → limpa sessao, redireciona pra `/login`, toast "Sessao expirada"

Retry unico evita loop se o refresh_token tambem for invalido.

**Logout**

`POST /autenticacao/logout` → `estado.limpar_sessao()` → redirect `/login`. Best-effort: erro do backend nao impede limpeza local.

### 4.3 Cliente HTTP (`ui/cliente_api.py`)

Classe unica `ClienteApi` envolve `httpx.Client`. **Toda chamada a API passa por aqui.** Responsabilidades:

1. Injecao automatica de `Authorization: Bearer <token>` via `estado.token_atual()`
2. Base URL de `config.BACKEND_URL` (env var, default `http://localhost:8001`)
3. Captura de request/response → `estado.registrar_chamada_http(RegistroHttp)`
4. Refresh automatico no 401 (secao 4.2)
5. Mapeamento de erros HTTP → excecoes tipadas:

| Status | Excecao |
|---|---|
| 401 apos refresh falhar | `NaoAutenticadoError` |
| 403 | `AcessoNegadoError(papel_necessario)` |
| 422 | `ValidacaoError(detalhes)` (preserva array `detail` do FastAPI) |
| 429 | `RateLimitExcedidoError(retry_after)` |
| 5xx | `BackendIndisponivelError` |
| ConnectionError | `BackendInacessivelError(url)` |

**Formato do registro HTTP**:

```python
@dataclass(frozen=True)
class RegistroHttp:
    timestamp: datetime
    metodo: str                 # "POST"
    caminho: str                # "/api/v1/ordens-de-servico/<uuid>/aprovacao"
    status: int
    duracao_ms: int
    request_body: str | None    # JSON pretty-printed, None se vazio
    response_body: str          # JSON pretty-printed, truncado em 10KB
    papel_no_momento: str       # snapshot pra diagnosticar RBAC
```

**Mascaramento de token**: o header `Authorization` armazenado no registro e sempre `Bearer ****`. Previne compartilhamento acidental de token via screenshot.

### 4.4 Painel HTTP (`componentes/painel_http.py`)

Drawer a direita, colapsavel via icone no cabecalho. Recebe eventos de novos `RegistroHttp` e insere no topo. Cada entrada mostra:

```
[POST] /api/v1/ordens-de-servico/xyz/aprovacao    [200 · 142ms · admin]
  ▶ clicar pra expandir request/response
```

Expandida: request body e response body em blocos com syntax highlight JSON.

Controles: filtro por faixa de status (Tudo · 2xx · 4xx · 5xx), busca por substring no caminho, botao "Limpar". Maximo 50 entradas (descarta mais antigas ao ultrapassar). Nao persiste entre reloads.

### 4.5 Tratamento de erros visivel

Alem do painel (que sempre registra tudo), toast por tipo:

| Erro | Toast | Acao adicional |
|---|---|---|
| 401 apos refresh | "Sessao expirada" (amarelo) | Redirect /login |
| 403 | "Seu papel ({papel}) nao permite essa acao. Exige {papel_necessario}." | Permanece |
| 422 | mensagens inline abaixo dos campos | Form aberto |
| 429 | "Rate limit. Aguarde {retry_after}s." (laranja) | Botao disable temporario |
| 5xx | "Erro no servidor — veja o painel HTTP" (vermelho) | Permanece |
| Connection | "Backend inacessivel em {URL}. Esta rodando?" (vermelho) | Permanece |

## 5. Seed de dados de teste (requisito C)

### 5.1 Estrategia

O seed usa a propria API do backend (nao toca direto no banco). Vantagens: respeita regras de negocio, e o proprio seed funciona como smoke test visivel (~25 chamadas no painel HTTP).

### 5.2 Conteudo

Em ordem, usando token admin:

| Etapa | Endpoint | Qtd | Observacao |
|---|---|---|---|
| Clientes | `POST /clientes` | 3 | 2 PF + 1 PJ, CPFs/CNPJs validos no checksum |
| Veiculos | `POST /clientes/{id}/veiculos` | 5 | distribuidos entre os 3 clientes |
| Servicos | `POST /servicos` | 5 | nomes realistas (troca de oleo, alinhamento, etc) |
| Itens estoque | `POST /estoque` | 10 | 1 com qty < 5 pra testar destaque |
| Ordens servico | fluxo completo | 4 | em estados variados (abaixo) |

As 4 OS sao criadas em estados diferentes, por design:

| OS | Estado final | Como e alcancado |
|---|---|---|
| #1 | RECEBIDA | criada, sem itens |
| #2 | EM_DIAGNOSTICO | criada → 1 item → `/diagnostico` |
| #3 | AGUARDANDO_APROVACAO | criada → 2 itens → `/diagnostico` → `/orcamento` |
| #4 | EM_EXECUCAO | criada → 3 itens → `/diagnostico` → `/orcamento` → `/aprovacao` |

Dados coerentes (amostra):
- Joao Silva (CPF 111.444.777-35) · Gol 2015 `ABC1D23` · Civic 2020 `DEF2E34`
- Maria Santos (CPF 987.654.321-00) · Corolla 2018 `GHI3F45`
- Oficina Boa Vida LTDA (CNPJ 12.345.678/0001-90) · Strada 2019 `JKL4G56` · HR 2022 `MNO5H67`

### 5.3 Pre-condicao

Botao desabilitado quando papel != admin. Tooltip: *"Troque pra admin no switcher do topo pra poder gerar dados."* Sem auto-troca silenciosa.

### 5.4 Idempotencia parcial

Antes de criar clientes/servicos/itens, faz GET e verifica duplicata por chave natural:
- Cliente por documento (CPF/CNPJ)
- Servico por nome
- Item de estoque por nome

Se existem, skippa com contador `existentes`. **OS sempre sao criadas novas** — clicar 3 vezes gera 12 OS em estados variados, util pra ter massa pra paginacao/filtros/metricas.

### 5.5 Feedback visual

Dialog modal durante execucao:
```
Gerando dados de teste...
[████████░░░░░░░] 47%
Criando OS #3: gerando orcamento...
```

Relatorio final:
```
✓ 3 clientes criados (0 ja existiam)
✓ 5 veiculos adicionados
✓ 5 servicos criados (0 ja existiam)
✓ 10 itens de estoque criados (0 ja existiam)
✓ 4 ordens de servico criadas
⚠ 1 aviso: OS #4 nao aprovou orcamento — estoque insuficiente de "Amortecedor"
```

Erro fatal mostra progresso parcial, erro, botao "Tentar continuar do ponto que falhou".

## 6. Maquina de estados visual (requisito E)

### 6.1 Modelo canonico

Fonte unica de verdade no UI em `ui/componentes/maquina_estados.py`:

```python
@dataclass(frozen=True)
class Transicao:
    acao: str
    rotulo: str
    endpoint: str
    papeis_autorizados: frozenset[str]
    confirma: bool = False       # dialog "tem certeza?"
    pede_motivo: bool = False    # textarea obrigatoria

TRANSICOES_POR_STATUS: dict[StatusOrdem, list[Transicao]] = {
    StatusOrdem.RECEBIDA: [
        Transicao("diagnostico", "Iniciar diagnostico", "/diagnostico",
                  {"admin", "mecanico"}),
        Transicao("cancelar", "Cancelar", "/cancelamento",
                  {"admin"}, confirma=True, pede_motivo=True),
    ],
    StatusOrdem.EM_DIAGNOSTICO: [
        Transicao("gerar_orcamento", "Gerar orcamento", "/orcamento",
                  {"admin", "mecanico"}),
        Transicao("cancelar", "Cancelar", "/cancelamento",
                  {"admin"}, confirma=True, pede_motivo=True),
    ],
    StatusOrdem.AGUARDANDO_APROVACAO: [
        Transicao("aprovar", "Aprovar orcamento", "/aprovacao",
                  {"admin"}),
        Transicao("cancelar", ...),
    ],
    StatusOrdem.EM_EXECUCAO: [
        Transicao("finalizar", "Finalizar servico", "/finalizacao",
                  {"admin", "mecanico"}),
        Transicao("gerar_complementar", "Gerar orcamento complementar",
                  "/orcamento-complementar", {"admin", "mecanico"}),
        Transicao("cancelar", ...),
    ],
    StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: [
        Transicao("aprovar_complementar", "Aprovar complementar",
                  "/aprovacao-complementar", {"admin", "mecanico"}),
        Transicao("rejeitar_complementar", "Rejeitar complementar",
                  "/rejeicao-complementar", {"admin"}),
        Transicao("cancelar", ...),
    ],
    StatusOrdem.FINALIZADA: [
        Transicao("entregar", "Registrar entrega", "/entrega",
                  {"admin", "mecanico"}),
    ],
    StatusOrdem.ENTREGUE: [],    # terminal
    StatusOrdem.CANCELADA: [],   # terminal
}
```

Teste de drift-check importa `StatusOrdem` do backend e garante que todas as chaves estao presentes.

### 6.2 Stepper visual

Linha horizontal com happy path + branches:

```
[●] Recebida → [●] Em Diag. → [●] Ag. Aprov. → [○] Em Exec. → [ ] Final. → [ ] Entregue
                                                     │
                                                     └──→ [ ] Cancelada
```

- Estado atual: circulo preenchido azul, label bold
- Passados: circulo preenchido cinza claro (usa timestamps `diagnostico_iniciado_em`, `orcamento_gerado_em`, etc. da `OrdemDeServicoResponse`)
- Futuros: circulo vazado, label cinza
- Terminais (Cancelada, Entregue): destacados em vermelho/verde quando alcancados; escondidos ate entrarem no caminho

### 6.3 Grid de botoes

Abaixo do stepper, `ui.row` com os botoes das transicoes validas **do estado atual**. Nada mais aparece. Se OS em ENTREGUE/CANCELADA, grid vazio com mensagem *"Estado final — nenhuma transicao disponivel."*

Cada botao em 3 estados visuais:
- **Habilitado** (azul): papel atual autorizado
- **Desabilitado** (cinza com cadeado): papel nao autorizado, tooltip "Exige papel: admin" (ou "admin ou mecanico")
- **Perigoso** (vermelho): cancelamento, rejeicao complementar

Click em botao com `confirma=True` → `DialogoConfirmacao`. Click em `pede_motivo=True` → dialog com textarea (min 10 chars).

Apos submissao:
- Sucesso → toast verde "OS agora em {novo_status}" → recarrega dados inline (stepper + grid se auto-atualizam)
- 409 (transicao invalida) → toast "Transicao nao permitida. Estado pode ter mudado em outra aba" → recarrega
- 422 (regra de negocio, ex: OS sem itens nao pode ir pra orcamento) → toast vermelho com `detail` do backend
- 403 (papel insuficiente, se o backend discordar do disable client-side) → toast "Papel insuficiente" → recarrega (estado pode ter mudado)
- 5xx → toast vermelho "Erro no servidor — veja o painel HTTP" → permanece na pagina

### 6.4 Funcao central testavel

```python
def obter_transicoes_validas(
    status: StatusOrdem,
    papel_atual: str,
) -> list[BotaoTransicao]:
    """Retorna botoes com enable/disable ja calculado."""
```

Testavel isoladamente pela matriz 7 estados × 3 papeis = 21 casos.

## 7. Desenvolvimento, testes e CI

### 7.1 Workflow local

```bash
# Terminal 1: backend
docker compose up -d postgres
uv run alembic upgrade head
uv run python scripts/seed_usuarios.py   # primeira vez
./scripts/run-dev.sh                     # FastAPI :8001

# Terminal 2: UI
uv run python -m ui                      # NiceGUI :8080
```

NiceGUI tem reload nativo — edit Python, browser refresh sozinho.

### 7.2 Workflow docker

`docker compose up -d` passa a subir 3 servicos: `postgres`, `app`, `ui`.
- Backend: `http://localhost:8000` (Swagger em `/docs` segue la)
- UI: `http://localhost:8080`
- UI container chama `http://app:8000` internamente

Seed nao roda automaticamente. Comando separado:

```bash
make up
make seed-users-docker   # docker compose exec app python scripts/seed_usuarios.py
```

Novos Makefile targets:

| Target | Acao |
|---|---|
| `make ui` | `uv run python -m ui` (local) |
| `make seed-users` | `uv run python scripts/seed_usuarios.py` (local) |
| `make seed-users-docker` | `docker compose exec app python scripts/seed_usuarios.py` |
| `make up-backend` | Sobe so `postgres + app` (pra quem quer UI local contra backend docker) |

### 7.3 Estrategia de testes

Todos em pytest em `tests/unitarios/ui/`:

**Camada 1 — modulos puros (sem UI)**:

| Modulo | Teste | Como |
|---|---|---|
| `cliente_api.py` | headers, refresh 401, mapeamento de erros, ring buffer | `httpx.MockTransport` |
| `estado.py` | get/set sessao, limpeza, historico | storage mockado |
| `maquina_estados.py` | matriz 7×3 → botoes esperados | tabela de casos |
| `seed.py` | sequencia de chamadas, idempotencia, relatorio | API mockada |

**Camada 2 — componentes NiceGUI**: `nicegui.testing.Screen` (browser headless via playwright). Cobre login, role switcher, painel HTTP, botoes condicionais.

**Camada 3 — drift-check**: importa `StatusOrdem` do backend, compara com chaves de `TRANSICOES_POR_STATUS`.

**Coverage**: 60% total, 80% nos 4 modulos criticos da camada 1. Documentado via `.coveragerc` com threshold por path.

### 7.4 CI

Extensao de `.github/workflows/ci.yml`:

- `ruff check src/ ui/ tests/`
- `mypy src/ ui/`
- `bandit -r src/ ui/`
- `pytest tests/unitarios/ --no-lint` (inclui `tests/unitarios/ui/`)

Threshold de coverage por path via `.coveragerc`.

Overrides mypy se NiceGUI tiver stubs incompletos (preferir overrides tight, evitar `ignore_errors` global):
```toml
[[tool.mypy.overrides]]
module = "nicegui.*"
ignore_missing_imports = true
```

Sem testes E2E em CI (overhead alto, ROI baixo numa ferramenta de dev). Se precisar depois, job separado `ui-e2e` opcional.

### 7.5 Documentacao

**README.md (raiz)** ganha secao `## UI de Simulacao`:
- Proposito (1 paragrafo)
- Pre-requisito (`make seed-users`)
- Como rodar local (2 comandos)
- Como rodar via docker (1 comando)
- Tabela de URLs (UI, Swagger, health)
- Nota explicita: "Nao e artefato de producao"

Tabela de env vars ganha linhas:

| Variavel | Descricao | Default |
|---|---|---|
| `BACKEND_URL` | URL do backend consumida pela UI | `http://localhost:8001` local / `http://app:8000` docker |
| `UI_PORT` | Porta da UI NiceGUI | `8080` |

**`ui/README.md`**: docs tecnicas internas da UI (arquitetura, como adicionar pagina, como adicionar endpoint ao `cliente_api`, como testar).

**Sem ADR**: a UI e ferramenta interna, fora do dominio de decisoes de producao. Se for promovida a entregavel no futuro, ai sim se formaliza via ADR.

## 8. Riscos e mitigacoes

| Risco | Mitigacao |
|---|---|
| UI imprestavel se `seed_usuarios.py` nao rodou | Tela de login detecta ausencia dos 3 usuarios e mostra instrucoes inline em vez de erro generico |
| Drift entre maquina de estados UI e backend | Teste de drift-check quebra CI quando backend adiciona estado |
| NiceGUI em producao acidental | `ui/Dockerfile` com comment header `# NOT FOR PRODUCTION DEPLOY — dev/testing tool only`; porta 8080 separada da porta do backend; UI fora do Dockerfile do backend |
| Token JWT exposto em screenshots do painel HTTP | `Authorization` mascarado como `Bearer ****` no RegistroHttp |
| Seed gera dados nao-deterministicos em runs concorrentes | Escopo dev-only; race conditions entre 2 admins rodando seed ao mesmo tempo produzem duplicatas aceitaveis (idempotencia por chave natural resolve) |

## 9. Plano de entrega em alto nivel

Detalhamento fica pro `writing-plans`, mas o design comporta ~5 PRs incrementais:

1. **Infra**: pyproject extra, estrutura de diretorios, `ui/Dockerfile`, servico docker-compose, Makefile targets, README inicial.
2. **Fundacao**: `scripts/seed_usuarios.py` + `cliente_api.py` + `estado.py` + pagina `/login` + shell basico.
3. **CRUD simples**: paginas `/clientes`, `/catalogo`, `/estoque` (sem acoes LGPD ainda).
4. **Ordens de servico**: `/ordens-servico` lista + detalhe + `StepperOs` + `BotoesTransicao` + `maquina_estados.py`.
5. **Polimento**: seed de dados (C), painel HTTP (D), LGPD nas acoes de cliente, acompanhamento publico, testes finais de drift-check e coverage.

Cada PR fecha um ciclo utilizavel ponta-a-ponta (ex. PR 2 ja permite login/logout/switcher sem o resto funcionando).

## 10. Referencias

- ADR-003 (DDD+Onion), ADR-004 (JWT), ADR-009 (idioma hibrido) em `docs/arquitetura/adr/`
- Routers existentes: `src/{contexto}/interfaces/router.py`
- Swagger: `http://localhost:8000/docs` quando backend estiver rodando
- NiceGUI: https://nicegui.io/
- httpx `MockTransport`: https://www.python-httpx.org/advanced/transports/
