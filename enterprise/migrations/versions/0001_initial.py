"""PEIMS enterprise initial schema

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision='0001_initial'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('projects',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('title',sa.String(200),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('members',
        sa.Column('project_id',sa.String(64),sa.ForeignKey('projects.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('principal_sub',sa.String(255),primary_key=True),
        sa.Column('role',sa.String(12),nullable=False),
        sa.CheckConstraint("role IN ('viewer','engineer','manager')",name='member_role'))
    op.create_table('activities',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('project_id',sa.String(64),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('external_id',sa.String(64),nullable=False),
        sa.Column('title',sa.String(200),nullable=False),
        sa.Column('actual_pct',sa.Numeric(5,2),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.UniqueConstraint('project_id','external_id',name='uq_activity_project_external'),
        sa.CheckConstraint('actual_pct >= 0 AND actual_pct <= 100',name='activity_progress'))
    op.create_table('rfis',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('project_id',sa.String(64),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('reference',sa.String(64),nullable=False),
        sa.Column('subject',sa.String(300),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.UniqueConstraint('project_id','reference',name='uq_rfi_reference'),
        sa.CheckConstraint("status IN ('open','in_review','answered','closed')",name='rfi_status'))
    op.create_table('cost_lines',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('project_id',sa.String(64),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('description',sa.String(300),nullable=False),
        sa.Column('category',sa.String(16),nullable=False),
        sa.Column('amount',sa.Numeric(18,2),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.CheckConstraint("category IN ('budget','actual','commitment')",name='cost_category'),
        sa.CheckConstraint('amount >= 0',name='cost_nonnegative'))
    op.create_table('audit_events',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('project_id',sa.String(64),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('actor_sub',sa.String(255),nullable=False),
        sa.Column('event_type',sa.String(80),nullable=False),
        sa.Column('entity_id',sa.String(80),nullable=False),
        sa.Column('changed_fields',sa.JSON(),nullable=False),
        sa.Column('happened_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_audit_project_time','audit_events',['project_id','happened_at'])

def downgrade():
    op.drop_index('ix_audit_project_time',table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_table('cost_lines')
    op.drop_table('rfis')
    op.drop_table('activities')
    op.drop_table('members')
    op.drop_table('projects')
