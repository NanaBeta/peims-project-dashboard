"""Tenant-scoped approved directory with explicit project opt-in.

Revision ID: 0003_organization_directory
Revises: 0002_workspace

Existing projects keep NULL organization_id and directory_enabled=FALSE.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_organization_directory'
down_revision = '0002_workspace'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table('organization_members',
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('principal_sub', sa.String(255), primary_key=True),
        sa.Column('role', sa.String(12), nullable=False),
        sa.CheckConstraint("role IN ('admin','member')", name='organization_member_role'),
    )
    op.create_table('directory_entries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('value', sa.String(160), nullable=False),
        sa.Column('normalized_value', sa.String(160), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('submitted_by', sa.String(255), nullable=False),
        sa.Column('reviewed_by', sa.String(255), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('organization_id','kind','normalized_value', name='uq_directory_org_kind_value'),
        sa.CheckConstraint("kind IN ('contractor','supplier','discipline','person','category','document_type')",name='directory_kind'),
        sa.CheckConstraint("status IN ('pending','approved','rejected','archived')", name='directory_status'),
    )
    op.create_index('ix_directory_approved_lookup', 'directory_entries', ['organization_id','kind','status'])
    op.create_table('organization_audit_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_sub', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(80), nullable=False),
        sa.Column('entity_id', sa.String(80), nullable=False),
        sa.Column('changed_fields', sa.JSON(), nullable=False),
        sa.Column('happened_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_organization_audit_time', 'organization_audit_events', ['organization_id','happened_at'])
    # Batch migration is PostgreSQL-safe and supports disposable SQLite migration tests.
    with op.batch_alter_table('projects') as batch:
        batch.add_column(sa.Column('organization_id', sa.String(36), nullable=True))
        batch.add_column(sa.Column('directory_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('directory_version', sa.Integer(), nullable=False, server_default='1'))
        batch.create_foreign_key('fk_project_organization', 'organizations', ['organization_id'], ['id'], ondelete='RESTRICT')


def downgrade():
    with op.batch_alter_table('projects') as batch:
        batch.drop_constraint('fk_project_organization', type_='foreignkey')
        batch.drop_column('directory_version')
        batch.drop_column('directory_enabled')
        batch.drop_column('organization_id')
    op.drop_index('ix_organization_audit_time', table_name='organization_audit_events')
    op.drop_table('organization_audit_events')
    op.drop_index('ix_directory_approved_lookup', table_name='directory_entries')
    op.drop_table('directory_entries')
    op.drop_table('organization_members')
    op.drop_table('organizations')
