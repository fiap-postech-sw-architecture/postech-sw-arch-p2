#!/usr/bin/env python3
"""Linter mecanico de cara-de-IA (subconjunto automatizavel do #17).

Uso: python lint_ai_trace.py <arquivo.md> [...]
Exit 0 = limpo; exit 1 = achados (linha + motivo no stdout).

Cobre so o que regex pega (frases banidas + densidade de enfase); os itens de
JULGAMENTO do #17 (explicar o obvio, paralelismo mecanico, referencia
alucinada) continuam com o agente. Fonte da regra "automatize o que e
mecanico": superpowers/writing-skills + guia oficial de skills da Anthropic
(padrao "Step N: Verify output — run script; if it fails, return").
"""

import re
import sys
from pathlib import Path

# ponytail: lista curta e curada > taxonomia completa; adicione so padrao que
# ja escapou numa revisao real (mesma regra do Copilot Gap Analysis).
FRASES_BANIDAS = [
    r"vale ressaltar",
    r"vale destacar",
    r"e importante (notar|ressaltar|destacar)",
    r"alem disso,",
    r"ademais",
    r"em suma",
    r"no cenario atual",
    r"desempenha um papel",
    r"it'?s worth noting",
    r"in conclusion",
    r"certainly",
    r"comprehensive",
    r"delve",
    r"robusto?a?s?\b",
    r"abrangente",
]
# Densidade por 100 linhas (calibrado nos docs nota-10 da fase 1/2).
MAX_NEGRITO_POR_100 = 16
MAX_TRAVESSAO_POR_100 = 18

padrao = re.compile("|".join(f"({p})" for p in FRASES_BANIDAS), re.IGNORECASE)
achados = 0

for arquivo in sys.argv[1:]:
    linhas = Path(arquivo).read_text(encoding="utf-8").splitlines()
    dentro_fence = False
    negrito = travessao = 0
    for i, linha in enumerate(linhas, 1):
        if linha.lstrip().startswith("```"):
            dentro_fence = not dentro_fence
        if dentro_fence:
            continue
        m = padrao.search(linha)
        if m:
            print(f"{arquivo}:{i}: frase banida: {m.group(0)!r}")
            achados += 1
        # Enfase FUNCIONAL nao conta: rotulo lead-in ("**X**: ..." / "- **X** —")
        # e o padrao aceito pelo proprio #17; travessao em linha de tabela e
        # separador de celula, nao pontuacao decorativa.
        if not re.match(r"^\s*[-*>|#]*\s*\*\*[^*]+\*\*\s*[:—]", linha):
            negrito += linha.count("**") // 2
        if not linha.lstrip().startswith("|"):
            travessao += linha.count(" — ")
    fator = max(len(linhas), 1) / 100
    if negrito / fator > MAX_NEGRITO_POR_100:
        print(f"{arquivo}: densidade de **negrito** alta ({negrito} em {len(linhas)} linhas)")
        achados += 1
    if travessao / fator > MAX_TRAVESSAO_POR_100:
        print(f"{arquivo}: densidade de travessao alta ({travessao} em {len(linhas)} linhas)")
        achados += 1

if achados:
    print(f"\n{achados} achado(s) — rode o #17 (agente) no diff antes de fechar.")
sys.exit(1 if achados else 0)
