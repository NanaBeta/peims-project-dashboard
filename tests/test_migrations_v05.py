"""Upgrade/downgrade structural smoke test on disposable SQLite.

A real PostgreSQL migration + rollback rehearsal is still required before deployment.
"""
import importlib
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_migrations_apply_and_rollback_in_order():
    migrations = [
        importlib.import_module('enterprise.migrations.versions.0001_initial'),
        importlib.import_module('enterprise.migrations.versions.0002_workspace'),
    ]
    engine = create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operation = Operations(context)
        for revision in migrations:
            with Operations.context(context):
                revision.upgrade()
        inspector = inspect(connection)
        assert 'action_items' in inspector.get_table_names()
        assert 'document_records' in inspector.get_table_names()
        assert 'members' in inspector.get_table_names()
        assert 'version' in {c['name'] for c in inspector.get_columns('members')}
        connection.execute(text("INSERT INTO projects (id,title,currency,created_at) VALUES ('P','Demo','GHS',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO members (project_id,principal_sub,role) VALUES ('P','mgr','manager')"))
        assert connection.execute(text("SELECT version FROM members WHERE principal_sub='mgr'")).scalar_one() == 1
        with Operations.context(context):
            migrations[1].downgrade()
        inspector = inspect(connection)
        assert 'action_items' not in inspector.get_table_names()
        assert 'document_records' not in inspector.get_table_names()
        assert 'version' not in {c['name'] for c in inspector.get_columns('members')}
    engine.dispose()
