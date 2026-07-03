"""Maquina de estados da OrdemDeServico na UI.

Fonte unica de verdade das transicoes visiveis. Deve espelhar o backend —
o teste em ``tests/unitarios/ui/test_drift_check.py`` quebra o build se
um novo estado for introduzido no backend sem ser adicionado aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ordem_servico.dominio.status import StatusOrdem


@dataclass(frozen=True)
class Transicao:
    acao: str
    rotulo: str
    endpoint: str
    papeis_autorizados: frozenset[str]
    confirma: bool = False
    pede_motivo: bool = False
    perigoso: bool = False


@dataclass(frozen=True)
class BotaoTransicao:
    transicao: Transicao
    habilitado: bool
    motivo_bloqueio: str | None = None

    @property
    def acao(self) -> str:
        return self.transicao.acao

    @property
    def rotulo(self) -> str:
        return self.transicao.rotulo


_CANCELAR = Transicao(
    acao="cancelar",
    rotulo="Cancelar",
    endpoint="/cancelamento",
    papeis_autorizados=frozenset({"admin"}),
    confirma=True,
    pede_motivo=True,
    perigoso=True,
)

# Valores em tuple: constante publica de modulo nao expoe lista mutavel
# (espelha a disciplina do frozenset da tabela de transicoes do dominio).
TRANSICOES_POR_STATUS: dict[StatusOrdem, tuple[Transicao, ...]] = {
    StatusOrdem.RECEBIDA: (
        Transicao(
            acao="diagnostico",
            rotulo="Iniciar diagnostico",
            endpoint="/diagnostico",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        _CANCELAR,
    ),
    StatusOrdem.EM_DIAGNOSTICO: (
        Transicao(
            acao="gerar_orcamento",
            rotulo="Gerar orcamento",
            endpoint="/orcamento",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        _CANCELAR,
    ),
    StatusOrdem.AGUARDANDO_APROVACAO: (
        Transicao(
            acao="aprovar",
            rotulo="Aprovar orcamento",
            endpoint="/aprovacao",
            papeis_autorizados=frozenset({"admin"}),
        ),
        _CANCELAR,
    ),
    StatusOrdem.EM_EXECUCAO: (
        Transicao(
            acao="finalizar",
            rotulo="Finalizar servico",
            endpoint="/finalizacao",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        Transicao(
            acao="gerar_complementar",
            rotulo="Gerar orcamento complementar",
            endpoint="/orcamento-complementar",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        _CANCELAR,
    ),
    StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: (
        Transicao(
            acao="aprovar_complementar",
            rotulo="Aprovar complementar",
            endpoint="/aprovacao-complementar",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        Transicao(
            acao="rejeitar_complementar",
            rotulo="Rejeitar complementar",
            endpoint="/rejeicao-complementar",
            papeis_autorizados=frozenset({"admin"}),
            confirma=True,
            perigoso=True,
        ),
        _CANCELAR,
    ),
    StatusOrdem.FINALIZADA: (
        Transicao(
            acao="entregar",
            rotulo="Registrar entrega",
            endpoint="/entrega",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
    ),
    StatusOrdem.ENTREGUE: (),
    StatusOrdem.CANCELADA: (),
}


def obter_transicoes_validas(
    status: StatusOrdem,
    papel_atual: str,
) -> list[BotaoTransicao]:
    """Retorna botoes com enable/disable ja calculado por papel."""
    botoes: list[BotaoTransicao] = []
    for transicao in TRANSICOES_POR_STATUS.get(status, []):
        if papel_atual in transicao.papeis_autorizados:
            botoes.append(BotaoTransicao(transicao=transicao, habilitado=True))
        else:
            papeis = " ou ".join(sorted(transicao.papeis_autorizados))
            botoes.append(
                BotaoTransicao(
                    transicao=transicao,
                    habilitado=False,
                    motivo_bloqueio=f"Exige papel: {papeis}",
                )
            )
    return botoes
