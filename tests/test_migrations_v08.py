"""v0.8 structural upgrade and rollback smoke on disposable SQLite.

Deployment still needs a PostgreSQL rehearsal, identity provider and backup.
"""
import importlib
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_work_management_migration_upgrade_and_downgrade():
    names=['0001_initial','0002_workspace','0003_organization_directory','0004_work_management']
    revisions=[importlib.import_module('enterprise.migrations.versions.'+n) for n in names]
    engine=create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        ctx=MigrationContext.configure(connection)
        for revision in revisions[:3]:
            with Operations.context(ctx):
                revision.upgrade()
        connection.execute(text("INSERT INTO projects (id,title,currency,created_at) VALUES ('P','Existing Project','GHS',CURRENT_TIMESTAMP)"))
        with Operations.context(ctx):
            revisions[3].upgrade()
        inspector=inspect(connection)
        tables=set(inspector.get_table_names())
        assert {'work_items','work_dependencies','work_time_entries','work_comments'} <= tables
        assert {'projects','action_items','audit_events','directory_entries'} <= tables
        assert any(c['name']=='version' for c in inspector.get_columns('work_items'))
        assert len(inspector.get_foreign_keys('work_dependencies'))>=3
        assert connection.execute(text("SELECT title FROM projects WHERE id='P'")).scalar_one()=='Existing Project'
        with Operations.context(ctx):
            revisions[3].downgrade()
        assert 'work_items' not in inspect(connection).get_table_names()
        assert 'action_items' in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT title FROM projects WHERE id='P'")).scalar_one()=='Existing Project'
    engine.dispose()
