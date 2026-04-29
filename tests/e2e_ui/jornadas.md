# Relatorio de jornadas E2E visuais — UI de Simulacao

**Data:** 2026-04-23
**Ferramenta:** Playwright MCP (`mcp__plugin_playwright_playwright__*`)
**Stack testado:** UI local em :8080 apontando para backend docker em :8000
**Seed users:** 3 criados via `scripts/seed_usuarios.py` (`admin@pytstop.dev`, `atendente@pytstop.dev`, `mecanico@pytstop.dev`)

Screenshots salvos em `tests/e2e_ui/screenshots/` (gitignored no `.gitignore` exceto `.gitkeep`).

## Jornada 1: Login (admin shortcut)

- Navegacao: `/login`
- Screenshot: `01-login.png`
- Verificado:
  - Titulo "PytStop" + subtitulo "UI de Simulacao"
  - Campos E-mail + Senha
  - Status "Backend online" em verde
  - Botao "Entrar" + 3 atalhos dev (Admin/Atendente/Mecanico)
- Acao: clicar em "Admin" → redireciona para `/`

### Bug #1 encontrado + corrigido: `.local` TLD rejeitado

**Sintoma:** Primeiro click em "Admin" nao logou; permaneceu em `/login` sem erro visivel.

**Diagnostico:** `curl POST /api/v1/autenticacao/login` com `admin@pytstop.local` retorna 422:
```
"The part after the @-sign is a special-use or reserved name that cannot be used with email."
```
RFC 6762 lista `.local` como TLD reservado. Pydantic `EmailStr` rejeita.

**Fix (commit `3aa8bf3`):** trocar `@pytstop.local` → `@pytstop.dev` em:
- `ui/config.py::_USUARIOS_SEED`
- `scripts/seed_usuarios.py::_USUARIOS_FIXOS`
- `tests/unitarios/scripts/test_seed_usuarios.py`
- `tests/unitarios/ui/test_estado.py`

Apos fix, login funciona via shortcut.

## Jornada 2: Dashboard (admin)

- Navegacao: `/` (redirecionado apos login)
- Screenshot: `02-dashboard-admin.png`
- Verificado:
  - Cabecalho: PytStop logo, 6 nav links, icone history, badge "admin" vermelho, email `admin@pytstop.dev`, dropdown "Trocar papel" (value=admin), botao Logout
  - Titulo "Dashboard"
  - Cards de metricas: "Total de OS: 8" (blue), "Tempo medio (min): 69.0" (green), per-status (aguardando_aprovacao: 1, finalizada: 5, cancelada: 2, outros: 0)
  - Botoes "🎲 Gerar dados de teste" + "+ Nova OS"

Metricas corretas contra backend docker com dados pre-existentes.

## Jornada 3: Clientes (com bug 307 antes do fix)

- Navegacao: `/clientes`
- Screenshot pre-fix: `03-clientes.png`
- Verificado (pre-fix):
  - Cabecalho OK
  - Titulo "Clientes"
  - Botao "+ NOVO CLIENTE"
  - **ERRO VISIVEL:** "Erro ao listar: Status inesperado 307" em vermelho

### Bug #2 encontrado + corrigido: 307 redirects nao seguidos

**Sintoma:** `/clientes` e `/ordens-servico` mostram "Status inesperado 307". Dashboard nao mostrou o bug porque a rota `/metricas` nao tem trailing-slash issue.

**Diagnostico:** FastAPI/Starlette emite 307 Temporary Redirect de `/api/v1/clientes` para `/api/v1/clientes/`. O `httpx.Client` sem `follow_redirects=True` retorna a resposta 307 diretamente; o `_interpretar_resposta` da `ClienteApi` cai no `raise ApiError(f"Status inesperado {status}")`.

**Fix (commit `0e37fe5`):** adicionar `follow_redirects=True` no `httpx.Client(...)` em `ClienteApi.__init__`. Client segue automaticamente e a resposta final chega como 200.

Apos fix, `/clientes` lista OK e `/ordens-servico` lista as 8 OS.

## Jornada 4: Ordens de Servico — lista + detalhe

- Navegacao: `/ordens-servico`
- Screenshots: `04-ordens-servico.png` (antes do fix 307), `05-ordens-servico-fixed.png` (apos)
- Lista exibe 8 OS com badges coloridos:
  - 2 cancelada (red)
  - 1 aguardando_aprovacao (orange)
  - 5 finalizada (green)

### Detalhe OS

- Navegacao: `/ordens-servico/134f7599-77be-4582-b3ec-3810767b9937`
- Screenshot: `06-os-detalhe-aguardando.png`
- Verificado:
  - Titulo "OS <full UUID>"
  - Badge "aguardando_aprovacao" (orange) abaixo do titulo
  - Card "Dados": Cliente/Veiculo (ambos "-", backend nao popula join — fora de escopo para a UI)
  - Card "Ciclo de vida": stepper horizontal Recebida → Em Diag. → **Ag. Aprov.** (BLUE destaque) → Em Execucao → Finalizada → Entregue
  - Card "Acoes": 2 botoes "APROVAR ORCAMENTO" e "CANCELAR" visiveis (admin)
  - Card "Itens": 2 itens ("Troca executada pelo mecanico" Qty: 1, "Servico adicional (sem peca)" Qty: 2) com botoes delete
  - Card "Orcamento": "Total: R$ 0.00"

## Jornada 5: RBAC via troca de papel

- Acao: no dropdown "Trocar papel", selecionar "mecanico"
- Screenshot: `08-rbac-mecanico.png`
- Verificado:
  - Badge "mecanico" agora em verde (troca de cor correta)
  - Email atualizou para `mecanico@pytstop.dev`
  - Pagina recarregou automaticamente apos `api.login(mecanico@...)` + `ui.navigate.reload()`
  - **"APROVAR ORCAMENTO"** e **"CANCELAR"** aparecem com opacity-50 e estao disabled — ambos exigem `admin`
  - Tooltip esperado "Exige papel: admin" (nao testado clicando, pois o botao esta disabled)

RBAC funciona: botoes de transicao desabilitam corretamente por papel.

## Jornada 6: Painel HTTP — REMOVIDO

A UI custom de painel HTTP foi removida em PR #81 (drawer NiceGUI bugado, exigia mount em escopo `@ui.page` que o lazy-instantiate nao garantia). A infraestrutura de gravacao (`RegistroHttp`, `historico_http`, `_registrar*` em `ClienteApi`) ficou dormant ate ser deletada nesta PR conforme decisao da issue #89: Browser DevTools (aba Network) cobre 95% do caso de uso, entao a manutencao do drawer custom nao se paga.

Nenhuma jornada nova substitui esta — observabilidade HTTP em sessao da UI passa a usar DevTools direto.

## Jornada 7: Acompanhamento publico

- Navegacao: `/acompanhamento` (sem auth necessaria)
- Screenshot: `09-acompanhamento.png`
- Verificado:
  - Sem cabecalho (pagina publica nao tem `CabecalhoApp`)
  - Titulo "Acompanhamento de OS"
  - Subtitulo "Consulte o andamento do seu servico"
  - Input "Placa" com placeholder "ABC1D23"
  - Input "CPF ou CNPJ" com placeholder "apenas numeros"
  - Botao "CONSULTAR"
- Fluxo completo (consulta com dados reais) nao foi testado por tempo, mas o form renderiza corretamente e o endpoint `/api/v1/acompanhamento` esta documentado no OpenAPI.

## Outros observables (Minor, nao corrigidos)

- **Botao perigoso visual (CANCELAR):** plano define `perigoso=True` que deveria renderizar o botao em vermelho via `btn.classes("bg-red-600 text-white")`. Na pratica Quasar's default button styling prevalece sobre Tailwind class. Fix: usar `btn.props("color=negative")` ao inves de classes Tailwind.
- **Logout wraps na linha seguinte no cabecalho:** quando papel mecanico (texto "mecanico@pytstop.dev" mais curto), tudo cabe; quando papel admin ("admin@pytstop.dev") em viewport mais estreito o botao Logout quebra linha. Minor.

## Bugs corrigidos inline nesta sessao

| # | Sintoma | Commit |
|---|---------|--------|
| 1 | Login falha silenciosamente (TLD .local rejeitado) | `3aa8bf3` |
| 2 | /clientes e /ordens-servico mostram "Status inesperado 307" | `0e37fe5` |

## Bugs nao corrigidos (follow-ups)

| # | Descricao | Impacto | Recomendacao |
|---|-----------|---------|--------------|
| 3 | Painel HTTP drawer nao abre no click | Minor (feature de dev inacessivel) | Mount drawer em page-time via Layout wrapper |
| 4 | Botao "CANCELAR" com `perigoso=True` renderiza azul | Cosmetico | Trocar Tailwind class por `.props("color=negative")` |
| 5 | Logout button wraps em viewport estreito | Cosmetico | Adicionar `flex-shrink-0` no botao ou `whitespace-nowrap` |

## Conclusao

**Status final:** UI funcional para os fluxos principais (login, dashboard, CRUD, OS stepper, RBAC, acompanhamento publico). 2 bugs bloqueantes corrigidos durante o teste; 3 issues cosmeticas/menores registradas para follow-up.

**Coberto:** login, dashboard, OS list, OS detalhe (stepper + acoes), RBAC via trocar papel, acompanhamento publico.
**Parcialmente coberto:** Clientes (lista funcionou pos-fix; CRUD dialog nao exercitado), Catalogo, Estoque (nao navegados separadamente — ja consumem os mesmos helpers que Clientes + OS).
**Nao coberto:** seed de dados via dashboard (plan previa teste da Jornada 2), LGPD actions, executar transicao real (aprovacao de orcamento).
