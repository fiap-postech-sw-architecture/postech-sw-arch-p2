# Plano de finalização — Fase 2

> [↑ Raiz do projeto](../../../README.md) · [↑ Pai](README.md)

Issue índice: [#128](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/128). Guia operacional para o agente executor: [guia-agente-executor.md](guia-agente-executor.md).

Objetivo: fechar a fase 2 com nota máxima e um pacote **melhor que o da fase 1** (que tirou 10). Este plano consolida a auditoria de 2026-07-01 — quatro frentes independentes — em issues rastreáveis, ordem de ataque e critério de pronto.

## 1. Método da auditoria

| Frente | Escopo | Resultado |
|---|---|---|
| Rastreabilidade | Enunciado oficial (fonte: `local/postech-bootstrap/.../Phase2_Tech_Challenge.txt`) × código, item a item | 10/12 OK com evidência `file:line`; 2 parciais (cauda de submissão) |
| Baseline fase 1 | PDF nota-10 + repo p1 × pacote atual da fase 2 | Corpo do doc já supera a fase 1; PDF final sai "seco" (sem capa/anexos/segurança) |
| Caça-bugs | Fluxos críticos: máquina de estados, concorrência, outbox, auth, LGPD | 7 bugs confirmados + 1 provável |
| Ledger | 13 issues abertas, PR #55/#116, `docs/tech-debt/` | 4 issues resolvidas-esquecidas; ledger íntegro (26/26 verificados) |

Triagem: **todas as findings foram aceitas** — viraram issues, comentários propostos ou entradas de tech debt (TD-032/TD-033). Nenhuma rejeitada; nenhuma ignorada.

## 2. Estado atual (2026-07-01)

- Requisitos obrigatórios do enunciado: **todos implementados** — as 5 APIs, Docker/compose, `/k8s` completo (Deploy/Svc/CM/Secret/HPA), `/infra` Terraform (cluster+banco+docs), CI/CD de ponta a ponta. Evidências na [entrega-fase-2.md](entrega-fase-2.md) §5.
- Cobertura: 97,52% src + 98,48% ui na main (gate ≥95); 1544 unit + 149 integração verdes.
- PR [#116](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/116) (gates de segurança + Dependabot, fecha #75): CI 11/11 verde, aguardando decisão de merge.
- Pendências exclusivamente humanas: vídeo, convite `soat-architecture` (hoje **404**, sem convite pendente), PDF final, portal.

## 3. Inventário de issues

### Bugs de código (auditoria 2026-07-01)

| Issue | Sev. | Título | Depende de |
|---|---|---|---|
| [#117](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/117) | ALTA | `com_lock` devolve instância stale do identity map (falta `populate_existing`) | — |
| [#111](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/111) | CRÍTICA | Rejeitar orçamento complementar não reverte orçamento (causa raiz: sobrescrita em `gerar_orcamento_complementar`; escopo real inclui itens não removidos + reserva de estoque nunca liberada) | — |
| [#122](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/122) | MÉDIA | `finalizar_servico` aceita itens sem complementar aprovado (PROVÁVEL — confirmar por TDD) | desenhar com #111 |
| [#118](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/118) | ALTA | Logout não revoga refresh token (CWE-613) | — |
| [#121](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/121) | MÉDIA | Logout duplo → 500 (UNIQUE de jti) | — |
| [#119](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/119) | MÉDIA | Recusa externa cancela OS em execução (guard TOCTOU) | #117 |
| [#120](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/120) | MÉDIA | Item desativado pode ser reservado em OS nova | — |

### Entrega nota-10

| Issue | Título |
|---|---|
| [#113](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/113) | Collection Postman — **quebraria na banca**: request `decisao-orcamento` ainda usa `X-Webhook-Token`; código exige HMAC (TD-027); faltam 2 endpoints admin de outbox (46 requests vs 48 rotas) |
| [#124](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/124) | Seção de segurança no doc + re-scan da HEAD final (cobrindo relay/redis/pós-#116) + SonarQube de fechamento |
| [#125](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/125) | Apêndice de funcionalidades extras (≥15, formato da fase 1) |
| [#123](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/123) | PDF nota-10: capa ABNT + Anexos A–C + filtrar §8 Pendências |
| [#93](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/93) | Roteiro do vídeo: beat de Prometheus no bloco 6 (+ workloads completos no bloco 1, encerramento com a postura de segurança pós-#116) |
| [#44](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/44) | Preview da entrega — refresh do corpo (v1.0 lista só ADR-015–021; hoje existem ADR-022/023/024) |

### Housekeeping e qualidade

| Issue | Título |
|---|---|
| [#90](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/90) | README diz Python 3.12; runtime é 3.13 |
| [#95](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/95) | `seed_admin.py` não rejeita a senha demo pública |
| [#96](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/96) | Coluna `usuarios.papel` ainda com `default="admin"` no mapping |
| [#99](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/99) | Scrubber não mascara telefone BR sem espaço |
| [#126](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/126) | Mensagens de `ValueError` ecoadas cruas no 422 (TD-033) |
| [#127](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/127) | `EncryptionService` singleton entre testes (TD-032) |

### Para fechar (resolvidas em main, esquecidas abertas — decisão pendente)

| Issue | Resolvida por |
|---|---|
| [#83](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/83) | PR #101 (`com_lock` FOR UPDATE + ordem por id + `test_concorrencia_lock.py`) |
| [#35](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/35) | PR #50 (ports de hasher/JWT + contrato forbidden global) |
| [#33](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/33) | PR #64 (Job dedicado de migração) |
| [#31](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/31) | PR #62 (rate limiter Redis compartilhado) |

[#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/75) fecha com o merge do PR #116.

## 4. Ordem de ataque

Racional: bugs de código primeiro (a banca lê o código e o doc **vende** as defesas de concorrência — elas precisam ser reais), depois o pacote de entrega (collection → scans → apêndice → PDF), housekeeping em paralelo, e a cauda humana por último porque o PDF só é regenerado após o vídeo.

**P0 — código**
1. #117 `populate_existing` — cirúrgico (2 linhas + testes), protege a narrativa #82/#83 já vendida no doc de entrega
2. #111 + #122 — bundle no agregado `OrdemDeServico`: snapshot do orçamento aprovado, remoção dos itens não aprovados, liberação das reservas, guard de finalização
3. #118 + #121 — sessão de auth: logout revoga refresh + idempotência
4. #119 — guard pós-lock no caminho `recusada` (após o #117)
5. #120 — `ativo` no `ItemEstoqueDTO` + rejeição de peça inativa

**P1 — entrega**
6. #113 collection (bloqueia a avaliação prática das APIs)
7. #124 re-scan + SonarQube + seção de segurança
8. #125 apêndice de extras
9. #93 roteiro sincronizado
10. #90/#95/#96 + import-fix do PR #55 (bundle housekeeping)
11. #123 pipeline do PDF (capa/anexos/filtro) — deixar PRONTO; gerar o PDF final só depois do vídeo

**P2 — qualidade (fazer se não atrasar P0/P1)**
12. #99, #126, #127

**P3 — humano (fora do repo)**
13. Decidir merge do #116 · fechar/comentar as issues da seção 3.4 · decidir PR #55
14. Gravar vídeo (roteiro ~14min30s) → publicar (YouTube/Vimeo, não listado) → preencher os 2 marcadores `VIDEO-LINK-FASE-2`
15. Convidar `soat-architecture` (Settings → Collaborators) — **hoje não é colaborador nem tem convite**
16. Regerar PDF (seção 6) → conferir → submeter no portal

## 5. PRs esperados

Um PR por linha; nenhum merge automático — o usuário revisa cada um. Todo PR de código segue TDD (teste red primeiro) e os gates da seção 3 do guia.

| PR | Issues | Escopo resumido |
|---|---|---|
| A | #117 | `populate_existing=True` no branch `com_lock` dos 2 repositórios + teste de integração de releitura + unit do statement |
| B | #111 #122 | Reversão completa da rejeição do complementar (snapshot orçamento + remover itens + liberar reservas) + guard de finalização; asserts novos em `test_fluxo_rejeitar` |
| C | #118 #121 | Logout revoga refresh (opção A ou B da issue) + logout idempotente; OpenAPI atualizado |
| D | #119 | Revalidação dos estados de espera dentro da tx com lock no caminho `recusada` |
| E | #120 | `ativo` no DTO/port/adapter + rejeição em `_montar_item` + defesa em `reservar` |
| F | #113 | Collection regenerada do OpenAPI vivo + pre-request script HMAC + variáveis base |
| G | #124 | scan-fase-2.md v1.1 (HEAD final) + SonarQube fechamento + seção "Segurança na fase 2" + justificativa de cobertura |
| H | #125 | `apendice-funcionalidades-extras.md` (≥15 entradas ancoradas) |
| I | #93 | Roteiro: Prometheus no bloco 6, workloads no bloco 1, encerramento de segurança |
| J | #90 #95 #96 (+ import de `test_repository_os.py` do PR #55) | Bundle housekeeping de 1-liners |
| K | #123 | Capa ABNT + anexos + filtro §8 no `build-entrega-pdf.sh` |
| L | #99 #126 #127 | Qualidade P2 (opcional pré-entrega) |

Dependências: D depois de A; B independente; K depois de G e H (anexos existirem); PDF final depois de K + vídeo.

## 6. Como gerar o PDF de submissão

Pré-requisitos: `pandoc`, `weasyprint`, `npx` (mermaid-cli on-demand), `python3`.

1. **Preencher o link do vídeo** nos 2 marcadores `VIDEO-LINK-FASE-2`: [README.md](../../../README.md) (linha ~211) e [entrega-fase-2.md](entrega-fase-2.md) (§3).
2. Conferir que não sobrou marcador: `git grep -n "VIDEO-LINK"` deve retornar só os comentários de instrução, nenhum placeholder ativo.
3. Da raiz do repo: `bash scripts/build-entrega-pdf.sh` (pipeline canônico do repo: reescreve links relativos → URLs absolutas do GitHub via `rewrite-md-links.py`, renderiza o Mermaid em PNG via mermaid-cli e roda `pandoc --pdf-engine=weasyprint`). O artefato sai **fora do repo**: `~/git/fiap/postech-sw-architecture/documento-entrega-fase-2.pdf`.
4. Conferir no PDF: capa presente; diagrama como IMAGEM (não bloco de código); links abrem no GitHub (owner `fiap-postech-sw-architecture`); §8 Pendências ausente; anexos A–C presentes (pós-#123).
5. **Regenerar sempre** após qualquer edição no markdown — o PDF não se atualiza sozinho.
6. Warnings do weasyprint (`@media`, `text-rendering`, `overflow-x`) são inócuos.

Os 3 itens do enunciado no PDF: link do repo **compartilhado com `soat-architecture`** + desenho da arquitetura + link do vídeo (≤15min).

## 7. Critério de pronto (definition of done)

- [ ] P0 inteiro mergeado; `make test` + `make test-integ` verdes; cobertura ≥95% mantida
- [ ] PR #116 decidido (recomendação: merge — fecha #75)
- [ ] Collection Postman funcional contra a stack (`decisao-orcamento` autentica via HMAC)
- [ ] scan-fase-2.md v1.1 da HEAD final sem ressalvas + SonarQube registrado
- [ ] Doc de entrega com seção de segurança + apêndice de extras linkado
- [ ] Vídeo publicado e marcadores preenchidos
- [ ] `soat-architecture` colaborador confirmado
- [ ] PDF regenerado após o último edit, com capa/anexos/diagrama/links verificados
- [ ] Submissão no portal

> [↑ Raiz do projeto](../../../README.md) · [↑ Pai](README.md)
