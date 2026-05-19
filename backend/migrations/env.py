"""Alembic env.py configured to autogenerate from app.database.models.Base.metadata"""
from __future__ import with_statement
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.database.models import Base
target_metadata = Base.metadata

# Prefer DATABASE_URL from environment or app db module
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    try:
        from app.database.db import DATABASE_URL as _db_url
        DATABASE_URL = _db_url
    except Exception:
        DATABASE_URL = 'sqlite:///searches.db'

config.set_main_option('sqlalchemy.url', DATABASE_URL)


def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
