from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from visionguard.core.config import Settings, get_settings


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(bind=create_db_engine(settings), expire_on_commit=False)


@lru_cache
def get_session_factory():
    return create_session_factory(get_settings())


def get_session():
    with get_session_factory()() as session:
        try:
            yield session
            if session.in_transaction():
                session.commit()
        except Exception:
            session.rollback()
            raise
