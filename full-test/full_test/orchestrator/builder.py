"""Builder: expande um ``PlanoDeExecucao`` em instancias concretas de ``UserJourney``.

Responsavel por mapear cada ``DescritorDeJourney`` em N instancias com kwargs
corretos - pegando credenciais do seed, ids de servicos/itens, ordens
pre-criadas para a ``MecanicoJourney``. Esta logica esta separada do
``executar.py`` para manter aquele arquivo focado em coordenacao de
threads e coleta.

Cada entrada retornada por ``construir_instancias`` e um dict:
    {"journey": UserJourney, "timeout_s": float}
O orchestrator (ver ``executar.py``) consome esse shape direto no
``pool.submit(...)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from full_test.journeys.cliente_fluxos_alternativos import TODOS_CENARIOS

if TYPE_CHECKING:
    from uuid import UUID

    from full_test.orchestrator.planos import PlanoDeExecucao
    from full_test.seeders.config import FullTestConfig


def construir_instancias(
    *,
    plano: PlanoDeExecucao,
    config: FullTestConfig,
    recursos_seed: dict[str, Any],
) -> list[dict[str, Any]]:
    """Retorna lista de dicts ``{'journey': UserJourney, 'timeout_s': float}``.

    Cada journey class reconhecida e instanciada N vezes com os parametros
    apropriados. Classes nao mapeadas disparam ``RuntimeError`` - o builder
    e deliberadamente exaustivo para evitar submissao silenciosa de uma
    journey sem os kwargs corretos.
    """
    from full_test.journeys.admin_concurrency import AdminConcurrencyJourney
    from full_test.journeys.atendente import AtendenteJourney
    from full_test.journeys.cliente_fluxo_completo import (
        ClienteFluxoCompletoJourney,
    )
    from full_test.journeys.cliente_fluxo_completo import (
        RecursosSeed as RSFluxoCompleto,
    )
    from full_test.journeys.cliente_fluxos_alternativos import (
        ClienteFluxosAlternativosJourney,
    )
    from full_test.journeys.cliente_fluxos_alternativos import (
        RecursosSeed as RSFluxosAlternativos,
    )
    from full_test.journeys.mecanico import MecanicoJourney
    from full_test.journeys.metricas_fixture import MetricasFixtureJourney
    from full_test.journeys.rbac_matrix import RbacMatrixJourney

    creds = recursos_seed["credenciais"]
    servicos = recursos_seed["servicos"]
    itens_estoque = recursos_seed["itens_estoque"]
    admin_token = recursos_seed.get("admin_access_token")
    if not servicos or not itens_estoque:
        msg = "seed incompleto: faltam servicos ou itens_estoque"
        raise RuntimeError(msg)
    servico_id: UUID = servicos[0].id
    item_id: UUID = itens_estoque[0].id

    atendente = next((c for c in creds if c.papel.value == "atendente"), None)
    mecanico = next((c for c in creds if c.papel.value == "mecanico"), None)
    if atendente is None or mecanico is None:
        msg = "seed de usuarios faltou ATENDENTE ou MECANICO"
        raise RuntimeError(msg)

    instancias: list[dict[str, Any]] = []

    for descritor in plano.descritores:
        cls = descritor.journey_class
        timeout_s = descritor.timeout_s

        if cls is ClienteFluxoCompletoJourney:
            recursos_fc = RSFluxoCompleto(
                servico_id=servico_id, item_estoque_id=item_id
            )
            for i in range(descritor.n_instancias):
                journey_fc = ClienteFluxoCompletoJourney(
                    config=config,
                    instance_id=f"clf-{i:03d}",
                    recursos=recursos_fc,
                    admin_access_token=admin_token,
                )
                instancias.append({"journey": journey_fc, "timeout_s": timeout_s})

        elif cls is ClienteFluxosAlternativosJourney:
            recursos_alt = RSFluxosAlternativos(
                servico_id=servico_id, item_estoque_id=item_id
            )
            # Um cenario por instancia. Se ``n_instancias`` for menor que o
            # numero total de cenarios, prefixos de ``TODOS_CENARIOS`` sao
            # usados - isso permite reduzir cobertura no modo CI sem duplicar
            # logica.
            for i, cenario in enumerate(TODOS_CENARIOS[: descritor.n_instancias]):
                journey_alt = ClienteFluxosAlternativosJourney(
                    config=config,
                    instance_id=f"alt-{i:03d}",
                    recursos=recursos_alt,
                    cenario=cenario,
                    admin_access_token=admin_token,
                )
                instancias.append({"journey": journey_alt, "timeout_s": timeout_s})

        elif cls is AtendenteJourney:
            for i in range(descritor.n_instancias):
                journey_atd = AtendenteJourney(
                    config=config,
                    instance_id=f"atd-{i:03d}",
                    atendente_email=atendente.email,
                    atendente_senha=atendente.senha,
                )
                instancias.append({"journey": journey_atd, "timeout_s": timeout_s})

        elif cls is MecanicoJourney:
            # Pre-requisito: ordem em RECEBIDA criada com credencial admin.
            # Feita sincrona antes do submit ao pool para que o futuro da
            # journey nao precise esperar por outra thread.
            for i in range(descritor.n_instancias):
                ordem_id = _criar_ordem_para_mecanico(
                    config=config,
                    servico_id=servico_id,
                    item_id=item_id,
                    indice=i,
                    admin_access_token=admin_token,
                )
                journey_mec = MecanicoJourney(
                    config=config,
                    instance_id=f"mec-{i:03d}",
                    mecanico_email=mecanico.email,
                    mecanico_senha=mecanico.senha,
                    ordem_id=ordem_id,
                    servico_id=servico_id,
                    item_estoque_id=item_id,
                )
                instancias.append({"journey": journey_mec, "timeout_s": timeout_s})

        elif cls is AdminConcurrencyJourney:
            for i in range(descritor.n_instancias):
                journey_adm = AdminConcurrencyJourney(
                    config=config,
                    instance_id=f"adm-{i:03d}",
                    admin_access_token=admin_token,
                )
                instancias.append({"journey": journey_adm, "timeout_s": timeout_s})

        elif cls is MetricasFixtureJourney:
            for i in range(descritor.n_instancias):
                journey_met = MetricasFixtureJourney(
                    config=config,
                    instance_id=f"met-{i:03d}",
                    servico_id=servico_id,
                    item_estoque_id=item_id,
                    admin_access_token=admin_token,
                )
                instancias.append({"journey": journey_met, "timeout_s": timeout_s})

        elif cls is RbacMatrixJourney:
            for i in range(descritor.n_instancias):
                journey_rbac = RbacMatrixJourney(
                    config=config,
                    instance_id=f"rbac-{i:03d}",
                    atendente_email=atendente.email,
                    atendente_senha=atendente.senha,
                    mecanico_email=mecanico.email,
                    mecanico_senha=mecanico.senha,
                    admin_access_token=admin_token,
                )
                instancias.append({"journey": journey_rbac, "timeout_s": timeout_s})

        else:
            msg = f"Journey class nao suportada pelo builder: {cls!r}"
            raise RuntimeError(msg)

    return instancias


def _criar_ordem_para_mecanico(
    *,
    config: FullTestConfig,
    servico_id: UUID,
    item_id: UUID,
    indice: int,
    admin_access_token: str | None = None,
) -> UUID:
    """Cria uma ordem em ``RECEBIDA`` para o ``MecanicoJourney`` consumir.

    Feita via admin, sincrona, antes do submit ao pool. Retorna ``ordem_id``.
    Documentos sao gerados com ``rng`` semeado por ``config.seed + indice``
    para manter reproducibilidade entre runs quando o seed e fixo. Quando
    ``admin_access_token`` e passado, reusa o token compartilhado em vez de
    fazer login novo (evita rate limit /login).
    """
    import random

    from full_test.client.system_client import SystemClient
    from full_test.support.documentos import gerar_cpf, gerar_placa

    # ``S311`` liberado aqui: RNG de dado de teste, nunca cripto.
    rng = random.Random((config.seed or 0) + indice)  # noqa: S311
    with SystemClient(config.base_url, timeout=config.http_timeout) as c:
        if admin_access_token is not None:
            c.set_token(admin_access_token)
        else:
            c.login(email=config.admin_email, senha=config.admin_password)
        cliente = c.criar_cliente(
            nome=f"Cli MecPrep {indice:03d}",
            documento=gerar_cpf(rng),
            tipo_documento="cpf",
            contato="+55 11 900000000",
        )
        veiculo = c.adicionar_veiculo(
            cliente.id,
            placa=gerar_placa(rng),
            marca="F",
            modelo="U",
            ano=2019,
        )
        ordem = c.criar_ordem(cliente_id=cliente.id, veiculo_id=veiculo.id)
        # Nao fechamos logout aqui - o context manager do SystemClient fecha
        # o httpx.Client. O token expira naturalmente e nao vale o custo de
        # rodar logout para cada ordem pre-criada.
        return ordem.id
