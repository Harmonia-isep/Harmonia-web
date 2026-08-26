"""Alembic migration environment.

The database URL is resolved through backend.models.database, the same path
create_app uses, so the app and migrations share one config source. Batch mode is
on so SQLite migrations that ALTER a table (for example adding ondelete in a later
phase) work, since SQLite performs those by recreating the table.
"""

from logging.config import fileConfig

from sqlalchemy.engine import Connection, Engine

from alembic import context
from backend.models.database import create_database_engine, resolve_database_url
from backend.models.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=resolve_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # A caller (e.g. the test fixture) may inject a live Connection; otherwise
    # build an engine from the resolved DATABASE_URL.
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        connectable = create_database_engine()

    if isinstance(connectable, Engine):
        with connectable.connect() as connection:
            _configure(connection)
            with context.begin_transaction():
                context.run_migrations()
    else:
        _configure(connectable)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
