import os

from sqlalchemy import create_engine, pool

from alembic import context
from visionguard.core.config import Settings
from visionguard.db import models  # noqa: F401
from visionguard.db.base import Base

config = context.config
url = (
    context.get_x_argument(as_dictionary=True).get("database_url")
    or config.attributes.get("database_url")
    or os.getenv("ALEMBIC_DATABASE_URL")
    or Settings().database_url
)
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
