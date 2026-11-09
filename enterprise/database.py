"""Database connection: no production database defaults or automatic schema changes."""
import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

@lru_cache(maxsize=1)
def session_factory():
    url = os.environ.get('PEIMS_DATABASE_URL','')
    if not url:
        raise RuntimeError('PEIMS_DATABASE_URL is required for the enterprise API')
    if not url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Enterprise API only accepts PostgreSQL with psycopg')
    if make_url(url).query.get('sslmode') not in {'require', 'verify-ca', 'verify-full'}:
        raise RuntimeError('Enterprise PostgreSQL requires an encrypted sslmode')
    engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()
