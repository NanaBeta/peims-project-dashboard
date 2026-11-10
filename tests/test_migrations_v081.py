"""Disposable SQLite schema smoke test for console-session Alembic migration.
Production requires a separate PostgreSQL staging migration exercise.
"""
from importlib import import_module
from sqlalchemy import create_engine, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_console_session_migration_table_index_and_rollback():
    revision=import_module('enterprise.migrations.versions.0005_console_sessions')
    assert revision.revision=='0005_console_sessions'
    assert revision.down_revision=='0004_work_management'
    engine=create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as conn:
        ops=Operations(MigrationContext.configure(conn))
        old=revision.op
        try:
            revision.op=ops
            revision.upgrade()
            inspector=inspect(conn)
            assert 'browser_sessions' in inspector.get_table_names()
            cols={col['name'] for col in inspector.get_columns('browser_sessions')}
            assert cols=={'sid_hash','principal_sub','created_at','expires_at'}
            assert 'ix_browser_sessions_expiry' in {idx['name'] for idx in inspector.get_indexes('browser_sessions')}
            revision.downgrade()
            assert 'browser_sessions' not in inspect(conn).get_table_names()
        finally:
            revision.op=old
    engine.dispose()
