from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from visionguard.core.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(bind=create_db_engine(settings), expire_on_commit=False)
