"""Alembic migration environment.

Wired to the app's own engine + metadata so migrations and the ORM can never drift:
- URL comes from db.engine.DATABASE_URL ($DATABASE_URL) — never hardcoded here.
- target_metadata = db.models.Base.metadata, so `alembic revision --autogenerate` diffs
  the live DB against the models. (Autogenerate has blind spots — server defaults, some
  constraint/enum changes — so generated scripts are ALWAYS eyeballed, never blind-applied.)
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Repo root on path so `db` imports when alembic runs from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.engine import DATABASE_URL  # noqa: E402
from db.models import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
