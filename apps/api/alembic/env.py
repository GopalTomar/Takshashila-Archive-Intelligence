"""Alembic environment.

The database URL comes from the application settings (DATABASE_URL). On
PostgreSQL, the pgvector extension is ensured before migrations run so the
Vector column type resolves.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.config import get_settings
from app.db.base import Base, engine

# Import models so metadata is populated.
from app.db import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
