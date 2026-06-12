from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

metadata = MetaData()


def criar_engine(url: str) -> Engine:
    return create_engine(url, echo=False, future=True)


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
