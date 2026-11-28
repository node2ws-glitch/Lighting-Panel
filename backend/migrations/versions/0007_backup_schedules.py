"""Add recurring backup schedules."""
from alembic import op
import sqlalchemy as sa

revision = '0007_backup_schedules'
down_revision = '0006_billing'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'backup_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('server_id', sa.Integer(), sa.ForeignKey('game_servers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('frequency', sa.String(16), nullable=False),
        sa.Column('retention', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_backup_schedules_server_id', 'backup_schedules', ['server_id'])
    op.create_index('ix_backup_schedules_next_run_at', 'backup_schedules', ['next_run_at'])

def downgrade():
    op.drop_index('ix_backup_schedules_next_run_at', table_name='backup_schedules')
    op.drop_index('ix_backup_schedules_server_id', table_name='backup_schedules')
    op.drop_table('backup_schedules')
