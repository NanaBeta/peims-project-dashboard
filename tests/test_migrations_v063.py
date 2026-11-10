"""Migration 0003 must protect existing projects and downgrade on SQLite.

Production deployment still requires an isolated PostgreSQL upgrade rehearsal.
"""
import importlib
from sqlalchemy import create_engine, inspect, text
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_organization_directory_migration_defaults_and_downgrade():
    files=['0001_initial','0002_workspace','0003_organization_directory']
    revisions=[importlib.import_module(f'enterprise.migrations.versions.{n}') for n in files]
    engine=create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        ctx=MigrationContext.configure(connection)
        for rev in revisions[:2]:
            with Operations.context(ctx):
                rev.upgrade()
        connection.execute(text("INSERT INTO projects (id,title,currency,created_at) VALUES ('P','Legacy Demo','GHS',CURRENT_TIMESTAMP)"))
        with Operations.context(ctx):
            revisions[2].upgrade()
        i=inspect(connection)
        for t in ('organizations','organization_members','directory_entries','organization_audit_events'):
            assert t in i.get_table_names()
        project_fields={c['name'] for c in i.get_columns('projects')}
        assert {'organization_id','directory_enabled','directory_version'} <= project_fields
        row=connection.execute(text("SELECT organization_id,directory_enabled,directory_version FROM projects WHERE id='P'")).one()
        assert row[0] is None and row[1] in (False,0) and row[2]==1
        with Operations.context(ctx):
            revisions[2].downgrade()
        assert 'organizations' not in inspect(connection).get_table_names()
        assert 'organization_id' not in {c['name'] for c in inspect(connection).get_columns('projects')}
        assert connection.execute(text("SELECT title FROM projects WHERE id='P'")).scalar_one()=='Legacy Demo'
    engine.dispose()
