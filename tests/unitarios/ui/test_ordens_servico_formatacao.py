"""Testa a formatacao de valores monetarios na pagina de ordem de servico.

Regressao pinada: backend retorna valores em centavos (int) sob chaves
``*_centavos`` (ex.: ``total_centavos``, ``preco_unitario_centavos``,
``subtotal_centavos``). A UI original lia ``orcamento.get("total", 0)``, que
nao existia no payload — resultado: orcamentos sempre mostravam R$ 0,00 (bug
1 da validacao manual). Os testes abaixo travam o contrato com o backend no
nome da chave e na aritmetica centavos -> reais.
"""

from __future__ import annotations

from ui.paginas.ordens_servico import (
    _centavos_para_reais_label,
    _total_orcamento_label,
)


class TestCentavosParaReaisLabel:
    def test_converte_centavos_para_reais_com_prefixo_default(self) -> None:
        assert _centavos_para_reais_label(28500) == "R$ 285.00"

    def test_prefixo_customizavel(self) -> None:
        assert _centavos_para_reais_label(5000, prefixo="= R$ ") == "= R$ 50.00"

    def test_zero_centavos(self) -> None:
        assert _centavos_para_reais_label(0) == "R$ 0.00"

    def test_valor_none_vira_zero(self) -> None:
        """Chave ausente no payload do backend → default 0, nao explode."""
        assert _centavos_para_reais_label(None) == "R$ 0.00"

    def test_valor_pequeno_mantem_duas_casas(self) -> None:
        """1 centavo = R$ 0.01 — confere arredondamento/formatacao."""
        assert _centavos_para_reais_label(1) == "R$ 0.01"

    def test_valor_com_uma_casa_decimal_em_reais(self) -> None:
        """10 centavos = R$ 0.10 (nao ``0.1``)."""
        assert _centavos_para_reais_label(10) == "R$ 0.10"


class TestTotalOrcamentoLabel:
    def test_le_chave_canonica_total_centavos(self) -> None:
        """Bug 1: backend usa chave ``total_centavos``. O codigo antigo lia
        ``orcamento.get("total", 0)`` — essa chave nunca existe no payload, e
        por isso todos os orcamentos apareciam como R$ 0,00."""
        assert _total_orcamento_label({"total_centavos": 28500}) == "Total: R$ 285.00"

    def test_chave_obsoleta_total_nao_afeta_resultado(self) -> None:
        """Regressao: se um desenvolvedor reintroduzir a leitura de ``total``
        (chave obsoleta/inexistente no backend), esse teste deve falhar. Um
        payload com ambas as chaves ainda deve usar ``total_centavos``, nunca
        ``total``."""
        payload = {"total_centavos": 28500, "total": 999}
        assert _total_orcamento_label(payload) == "Total: R$ 285.00"

    def test_total_centavos_ausente_vira_zero(self) -> None:
        """Orcamento recem-gerado sem itens ainda pode vir sem
        ``total_centavos``. Nao deve explodir, mostra zero."""
        assert _total_orcamento_label({}) == "Total: R$ 0.00"

    def test_ordens_com_item_unico_exibe_valor_coerente(self) -> None:
        """Shape realista do backend (um item, quantidade 1)."""
        payload = {
            "total_centavos": 5000,
            "itens": [
                {
                    "descricao": "Troca de oleo",
                    "quantidade": 1,
                    "preco_unitario_centavos": 5000,
                    "subtotal_centavos": 5000,
                }
            ],
        }
        assert _total_orcamento_label(payload) == "Total: R$ 50.00"
