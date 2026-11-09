from __future__ import annotations
import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url
from enterprise.models import Base

config=context.config
if config.config_file_name: fileConfig(config.config_file_name)
target_metadata=Base.metadata
url=os.environ.get('PEIMS_DATABASE_URL','')
if not url.startswith('postgresql+psycopg://'):
    raise RuntimeError('PEIMS_DATABASE_URL with postgresql+psycopg:// is required for migrations')
if make_url(url).query.get('sslmode') not in {'require', 'verify-ca', 'verify-full'}:
    raise RuntimeError('Encrypted sslmode required for migrations')

def run_migrations_online():
    engine=create_engine(url,poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn,target_metadata=target_metadata,compare_type=True)
        with context.begin_transaction():context.run_migrations()
    engine.dispose()

run_migrations_online()
