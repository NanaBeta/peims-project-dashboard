"""Persistent project-scoped work items and collaboration.

Revision ID: 0004_work_management
Revises: 0003_organization_directory

Data is not imported from the session-only demonstration. Backups are handled
separately; this migration must not publish historical browser data.
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_work_management'
down_revision = '0003_organization_directory'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('work_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(64), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reference', sa.String(64), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.String(2000), nullable=False),
        sa.Column('kind', sa.String(12), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('priority', sa.String(12), nullable=False),
        sa.Column('assigned_sub', sa.String(255), nullable=True),
        sa.Column('parent_id', sa.String(36), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('estimate_hours', sa.Numeric(10,2), nullable=False),
        sa.Column('progress_pct', sa.Numeric(5,2), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('updated_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('project_id','reference', name='uq_work_item_project_reference'),
        sa.UniqueConstraint('project_id','id', name='uq_work_item_project_id'),
        sa.ForeignKeyConstraint(['project_id','parent_id'], ['work_items.project_id','work_items.id'], ondelete='RESTRICT', name='fk_work_item_parent'),
        sa.ForeignKeyConstraint(['project_id','assigned_sub'], ['members.project_id','members.principal_sub'], ondelete='RESTRICT', name='fk_work_item_assignee'),
        sa.CheckConstraint("kind IN ('task','subtask','milestone')", name='work_item_kind'),
        sa.CheckConstraint("status IN ('todo','in_progress','blocked','done')", name='work_item_status'),
        sa.CheckConstraint("priority IN ('low','medium','high','critical')", name='work_item_priority'),
        sa.CheckConstraint('estimate_hours >= 0', name='work_item_hours_nonnegative'),
        sa.CheckConstraint('progress_pct >= 0 AND progress_pct <= 100', name='work_item_progress_range'),
        sa.CheckConstraint('due_date >= start_date', name='work_item_date_order'),
        sa.CheckConstraint("(kind = 'subtask' AND parent_id IS NOT NULL) OR (kind <> 'subtask' AND parent_id IS NULL)", name='work_item_parent_kind'),
        sa.CheckConstraint("(kind <> 'milestone') OR (due_date = start_date AND estimate_hours = 0)",name='work_item_milestone'),
        sa.CheckConstraint("(status <> 'done') OR progress_pct = 100", name='work_item_completed_progress'),
    )
    op.create_index('ix_work_item_project_status','work_items',['project_id','status'])
    op.create_index('ix_work_item_project_assignee','work_items',['project_id','assigned_sub'])
    op.create_table('work_dependencies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(64), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('predecessor_id', sa.String(36), nullable=False),
        sa.Column('successor_id', sa.String(36), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id','predecessor_id'], ['work_items.project_id','work_items.id'], ondelete='RESTRICT', name='fk_work_dep_predecessor'),
        sa.ForeignKeyConstraint(['project_id','successor_id'], ['work_items.project_id','work_items.id'], ondelete='RESTRICT', name='fk_work_dep_successor'),
        sa.UniqueConstraint('project_id','predecessor_id','successor_id',name='uq_work_dependency_edge'),
        sa.CheckConstraint('predecessor_id <> successor_id',name='work_dependency_no_self'),
    )
    op.create_index('ix_work_dep_successor','work_dependencies',['project_id','successor_id'])
    op.create_table('work_time_entries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(64), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('work_item_id', sa.String(36), nullable=False),
        sa.Column('actor_sub', sa.String(255), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('hours', sa.Numeric(5,2), nullable=False),
        sa.Column('note', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id','work_item_id'], ['work_items.project_id','work_items.id'], ondelete='RESTRICT', name='fk_work_time_item'),
        sa.CheckConstraint('hours > 0 AND hours <= 24',name='work_time_hours_range'),
    )
    op.create_index('ix_work_time_project_date','work_time_entries',['project_id','work_date'])
    op.create_table('work_comments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(64), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('work_item_id', sa.String(36), nullable=False),
        sa.Column('author_sub', sa.String(255), nullable=False),
        sa.Column('body', sa.String(2000), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id','work_item_id'], ['work_items.project_id','work_items.id'], ondelete='RESTRICT', name='fk_work_comment_item'),
    )
    op.create_index('ix_work_comment_project_item','work_comments',['project_id','work_item_id','created_at'])


def downgrade():
    # Destructive: intended ONLY for empty staging/testing; production rollback
    # should be via restore and forward correction with explicit authorization.
    op.drop_index('ix_work_comment_project_item',table_name='work_comments')
    op.drop_table('work_comments')
    op.drop_index('ix_work_time_project_date',table_name='work_time_entries')
    op.drop_table('work_time_entries')
    op.drop_index('ix_work_dep_successor',table_name='work_dependencies')
    op.drop_table('work_dependencies')
    op.drop_index('ix_work_item_project_assignee',table_name='work_items')
    op.drop_index('ix_work_item_project_status',table_name='work_items')
    op.drop_table('work_items')
