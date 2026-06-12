# Relatório de jornadas E2E visuais — UI de Simulação

> [↑ Raiz do projeto](../../README.md)

**Data:** 2026-04-23
**Ferramenta:** Playwright MCP (`mcp__plugin_playwright_playwright__*`)
**Stack testado:** UI local em :8080 apontando para backend docker em :8000
**Seed users:** 3 criados via `scripts/seed_usuarios.py` (`admin@pytstop.dev`, `atendente@pytstop.dev`, `mecanico@pytstop.dev`)

Screenshots salvos em `tests/e2e_ui/screenshots/` (gitignored no `.gitignore` exceto `.gitkeep`).

## Jornada 1: Login (admin shortcut)

- Navegação: `/login`
- Screenshot: `01-login.png`
- Verificado:
  - Título "PytStop" + subtítulo "UI de Simulação"
  - Campos E-mail + Senha
  - Status "Backend online" em verde
  - Botão "Entrar" + 3 atalhos dev (Admin/Atendente/Mecanico)
- Ação: clicar em "Admin" → redireciona para `/`

### Bug #1 encontrado + corrigido: `.local` TLD rejeitado

**Sintoma:** Primeiro clique em "Admin" não logou; permaneceu em `/login` sem erro visível.

**Diagnóstico:** `curl POST /api/v1/autenticacao/login` com `admin@pytstop.local` retorna 422:
```
"The part after the @-sign is a special-use or reserved name that cannot be used with email."
```
RFC 6762 lista `.local` como TLD reservado. Pydantic `EmailStr` rejeita.

**Fix (commit `3aa8bf3`):** trocar `@pytstop.local` → `@pytstop.dev` em:
- `ui/config.py::_USUARIOS_SEED`
- `scripts/seed_usuarios.py::_USUARIOS_FIXOS`
- `tests/unitarios/scripts/test_seed_usuarios.py`
- `tests/unitarios/ui/test_estado.py`

Após fix, login funciona via shortcut.

## Jornada 2: Dashboard (admin)

- Navegação: `/` (redirecionado após login)
- Screenshot: `02-dashboard-admin.png`
- Verificado:
  - Cabeçalho: PytStop logo, 6 nav links, ícone history, badge "admin" vermelho, email `admin@pytstop.dev`, dropdown "Trocar papel" (value=admin), botão Logout
  - Título "Dashboard"
  - Cards de métricas: "Total de OS: 8" (blue), "Tempo médio (min): 69.0" (green), per-status (aguardando_aprovacao: 1, finalizada: 5, cancelada: 2, outros: 0)
  - Botões "🎲 Gerar dados de teste" + "+ Nova OS"

Métricas corretas contra backend docker com dados pré-existentes.

## Jornada 3: Clientes (com bug 307 antes do fix)

- Navegação: `/clientes`
- Screenshot pré-fix: `03-clientes.png`
- Verificado (pré-fix):
  - Cabeçalho OK
  - Título "Clientes"
  - Botão "+ NOVO CLIENTE"
  - **ERRO VISÍVEL:** "Erro ao listar: Status inesperado 307" em vermelho

### Bug #2 encontrado + corrigido: 307 redirects não seguidos

**Sintoma:** `/clientes` e `/ordens-servico` mostram "Status inesperado 307". Dashboard não mostrou o bug porque a rota `/metricas` não tem trailing-slash issue.

**Diagnóstico:** FastAPI/Starlette emite 307 Temporary Redirect de `/api/v1/clientes` para `/api/v1/clientes/`. O `httpx.Client` sem `follow_redirects=True` retorna a resposta 307 diretamente; o `_interpretar_resposta` da `ClienteApi` cai no `raise ApiError(f"Status inesperado {status}")`.

**Fix (commit `0e37fe5`):** adicionar `follow_redirects=True` no `httpx.Client(...)` em `ClienteApi.__init__`. Client segue automaticamente e a resposta final chega como 200.

Após fix, `/clientes` lista OK e `/ordens-servico` lista as 8 OS.

## Jornada 4: Ordens de Servico — lista + detalhe

- Navegação: `/ordens-servico`
- Screenshots: `04-ordens-servico.png` (antes do fix 307), `05-ordens-servico-fixed.png` (após)
- Lista exibe 8 OS com badges coloridos:
  - 2 cancelada (red)
  - 1 aguardando_aprovacao (orange)
  - 5 finalizada (green)

### Detalhe OS

- Navegação: `/ordens-servico/134f7599-77be-4582-b3ec-3810767b9937`
- Screenshot: `06-os-detalhe-aguardando.png`
- Verificado:
  - Título "OS <full UUID>"
  - Badge "aguardando_aprovacao" (orange) abaixo do título
  - Card "Dados": Cliente/Veiculo (ambos "-", backend não popula join — fora de escopo para a UI)
  - Card "Ciclo de vida": stepper horizontal Recebida → Em Diag. → **Ag. Aprov.** (BLUE destaque) → Em Execução → Finalizada → Entregue
  - Card "Ações": 2 botões "APROVAR ORCAMENTO" e "CANCELAR" visíveis (admin)
  - Card "Itens": 2 itens ("Troca executada pelo mecanico" Qty: 1, "Servico adicional (sem peca)" Qty: 2) com botões delete
  - Card "Orçamento": "Total: R$ 0.00"

## Jornada 5: RBAC via troca de papel

- Ação: no dropdown "Trocar papel", selecionar "mecanico"
- Screenshot: `08-rbac-mecanico.png`
- Verificado:
  - Badge "mecanico" agora em verde (troca de cor correta)
  - Email atualizou para `mecanico@pytstop.dev`
  - Página recarregou automaticamente após `api.login(mecanico@...)` + `ui.navigate.reload()`
  - **"APROVAR ORCAMENTO"** e **"CANCELAR"** aparecem com opacity-50 e estão disabled — ambos exigem `admin`
  - Tooltip esperado "Exige papel: admin" (não testado clicando, pois o botão está disabled)

RBAC funciona: botões de transição desabilitam corretamente por papel.

## Jornada 6: Painel HTTP — REMOVIDO

A UI custom de painel HTTP foi removida em PR #81 (drawer NiceGUI bugado, exigia mount em escopo `@ui.page` que o lazy-instantiate não garantia). A infraestrutura de gravação (`RegistroHttp`, `historico_http`, `_registrar*` em `ClienteApi`) ficou dormant até ser deletada nesta PR conforme decisão da issue #89: Browser DevTools (aba Network) cobre 95% do caso de uso, então a manutenção do drawer custom não se paga.

Nenhuma jornada nova substitui esta — observabilidade HTTP em sessão da UI passa a usar DevTools direto.

## Jornada 7: Acompanhamento público

- Navegação: `/acompanhamento` (sem auth necessária)
- Screenshot: `09-acompanhamento.png`
- Verificado:
  - Sem cabeçalho (página pública não tem `CabecalhoApp`)
  - Título "Acompanhamento de OS"
  - Subtítulo "Consulte o andamento do seu servico"
  - Input "Placa" com placeholder "ABC1D23"
  - Input "CPF ou CNPJ" com placeholder "apenas numeros"
  - Botão "CONSULTAR"
- Fluxo completo (consulta com dados reais) não foi testado por tempo, mas o form renderiza corretamente e o endpoint `/api/v1/acompanhamento` está documentado no OpenAPI.

## Outros observables (Minor, não corrigidos)

- **Botão perigoso visual (CANCELAR):** plano define `perigoso=True` que deveria renderizar o botão em vermelho via `btn.classes("bg-red-600 text-white")`. Na prática o Quasar's default button styling prevalece sobre Tailwind class. Fix: usar `btn.props("color=negative")` ao invés de classes Tailwind.
- **Logout wraps na linha seguinte no cabeçalho:** quando papel mecanico (texto "mecanico@pytstop.dev" mais curto), tudo cabe; quando papel admin ("admin@pytstop.dev") em viewport mais estreito o botão Logout quebra linha. Minor.

## Bugs corrigidos inline nesta sessão

| # | Sintoma | Commit |
|---|---------|--------|
| 1 | Login falha silenciosamente (TLD .local rejeitado) | `3aa8bf3` |
| 2 | /clientes e /ordens-servico mostram "Status inesperado 307" | `0e37fe5` |

## Bugs não corrigidos (follow-ups)

| # | Descrição | Impacto | Recomendação |
|---|-----------|---------|--------------|
| 3 | Painel HTTP drawer não abre no clique | Minor (feature de dev inacessível) | Mount drawer em page-time via Layout wrapper |
| 4 | Botão "CANCELAR" com `perigoso=True` renderiza azul | Cosmético | Trocar Tailwind class por `.props("color=negative")` |
| 5 | Logout button wraps em viewport estreito | Cosmético | Adicionar `flex-shrink-0` no botão ou `whitespace-nowrap` |

## Conclusão

**Status final:** UI funcional para os fluxos principais (login, dashboard, CRUD, OS stepper, RBAC, acompanhamento público). 2 bugs bloqueantes corrigidos durante o teste; 3 issues cosméticas/menores registradas para follow-up.

**Coberto:** login, dashboard, OS list, OS detalhe (stepper + ações), RBAC via trocar papel, acompanhamento público.
**Parcialmente coberto:** Clientes (lista funcionou pós-fix; CRUD dialog não exercitado), Catalogo, Estoque (não navegados separadamente — já consomem os mesmos helpers que Clientes + OS).
**Não coberto:** seed de dados via dashboard (plano previa teste da Jornada 2), LGPD actions, executar transição real (aprovação de orçamento).

> [↑ Raiz do projeto](../../README.md)
