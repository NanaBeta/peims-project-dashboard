"""Server-side browser sessions for the enterprise console.

Revision ID: 0005_console_sessions
Revises: 0004_work_management

Stores only a hash of a random session ID and the verified subject, not tokens.
"""
from alembic import op
import sqlalchemy as sa

revision='0005_console_sessions'
down_revision='0004_work_management'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('browser_sessions',
        sa.Column('sid_hash',sa.String(64),primary_key=True),
        sa.Column('principal_sub',sa.String(255),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
    )
    op.create_index('ix_browser_sessions_expiry','browser_sessions',['expires_at'])

def downgrade():
    # Destructive: only for disposable staging; never use on a live deployment
    # without an approved rollback / backup procedure.
    op.drop_index('ix_browser_sessions_expiry',table_name='browser_sessions')
    op.drop_table('browser_sessions')
