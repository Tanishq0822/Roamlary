"""Alembic environment - runs on every alembic command.

Plain language: this file answers two questions for Alembic:
1. WHICH database?  -> from our Settings class (environment / .env),
   so credentials never appear in alembic.ini or in migration files.
2. WHICH tables?    -> by importing `app.models`, every model registers
   its table, so `alembic revision --autogenerate` can compare the code
   with the real database and propose an accurate migration.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the backend package importable when alembic runs from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402,F401  (importing registers all tables)
from app.core.config import settings  # noqa: E402
from app.db.base_class import Base  # noqa: E402

config = context.config

# Interpolate '%' so passwords containing it survive ConfigParser.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting (for review/dry-runs)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # batch mode is required for schema edits on SQLite; it is a
        # no-op for PostgreSQL.
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against the live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
