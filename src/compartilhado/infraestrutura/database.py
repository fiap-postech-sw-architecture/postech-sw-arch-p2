from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

metadata = MetaData()

# Dimensionamento do pool para escala horizontal (RNF-024). Os defaults sao
# os mesmos do SQLAlchemy (5 + 10), escolhidos para o pior caso do HPA: com
# maxReplicas=5 (k8s/hpa.yaml), (pool_size + max_overflow) * replicas =
# (5 + 10) * 5 = 75 conexoes, dentro do max_connections=100 do Postgres
# (postgres:16 default, infra/postgres.tf). Sobrescritiveis por env para
# outros dimensionamentos (k8s/configmap.yaml).
_DB_POOL_SIZE_PADRAO = "5"
_DB_MAX_OVERFLOW_PADRAO = "10"
# Recicla conexoes a cada 30min para evitar conexoes presas/stale em pods
# de vida longa sob o HPA.
_DB_POOL_RECYCLE_PADRAO = "1800"


def criar_engine(url: str) -> Engine:
    # pool_pre_ping valida a conexao no checkout (descarta conexoes mortas
    # apos restart do banco ou ociosidade) — aplicavel a qualquer pool.
    if url.startswith("postgresql"):
        # QueuePool (Postgres): dimensiona o pool para N replicas (RNF-024).
        return create_engine(
            url,
            echo=False,
            future=True,
            pool_pre_ping=True,
            pool_size=int(os.environ.get("DB_POOL_SIZE", _DB_POOL_SIZE_PADRAO)),
            max_overflow=int(
                os.environ.get("DB_MAX_OVERFLOW", _DB_MAX_OVERFLOW_PADRAO)
            ),
            pool_recycle=int(
                os.environ.get("DB_POOL_RECYCLE", _DB_POOL_RECYCLE_PADRAO)
            ),
        )
    # SQLite (testes) usa SingletonThreadPool e rejeita pool_size/max_overflow.
    return create_engine(url, echo=False, future=True, pool_pre_ping=True)


def criar_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False mantem atributos utilizaveis apos uow.commit().
    # Essencial porque use cases fazem: with uow: repo.salvar(x); uow.commit();
    # return _dto(x). Com expire_on_commit=True (padrao), acessar x.id apos o
    # commit dispara refresh em sessao ja fechada -> DetachedInstanceError.
    # Se reverter este flag, todos os use cases precisam ser refatorados para
    # ler os atributos ANTES do commit.
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
