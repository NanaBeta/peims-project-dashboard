"""Persistent workspace registers and versioned project membership.

Revision ID: 0002_workspace
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_workspace'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('members', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.create_table(
        'action_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(64), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reference', sa.String(64), nullable=False),
        sa.Column('summary', sa.String(300), nullable=False),
        sa.Column('assigned_sub', sa.String(255), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('priority', sa.String(12), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.UniqueConstraint('project_id', 'reference', name='uq_action_project_reference'),
        sa.CheckConstraint("priority IN ('low','medium','high','critical')", name='action_priority'),
        sa.CheckConstraint("status IN ('open','in_progress','blocked','done')", name='action_status'),
    )
    op.create_index('ix_action_project_status', 'action_items', ['project_id', 'status'])
    op.create_table(
        'document_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(64), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reference', sa.String(64), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('revision', sa.String(32), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.UniqueConstraint('project_id', 'reference', name='uq_document_project_reference'),
        sa.CheckConstraint("status IN ('draft','in_review','approved','superseded')", name='document_status'),
    )
    op.create_index('ix_document_project_status', 'document_records', ['project_id', 'status'])


def downgrade():
    op.drop_index('ix_document_project_status', table_name='document_records')
    op.drop_table('document_records')
    op.drop_index('ix_action_project_status', table_name='action_items')
    op.drop_table('action_items')
    op.drop_column('members', 'version')
