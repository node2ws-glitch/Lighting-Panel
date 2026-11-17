"""Add per-server subusers and permission grants."""
from alembic import op
import sqlalchemy as sa

revision = '0005_server_subusers'
down_revision = '0004_task_leases'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'server_subusers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('server_id', sa.Integer(), sa.ForeignKey('game_servers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('permissions', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('server_id', 'user_id', name='uq_server_subuser'),
    )
    op.create_index('ix_server_subusers_server_id', 'server_subusers', ['server_id'])
    op.create_index('ix_server_subusers_user_id', 'server_subusers', ['user_id'])

def downgrade():
    op.drop_index('ix_server_subusers_user_id', table_name='server_subusers')
    op.drop_index('ix_server_subusers_server_id', table_name='server_subusers')
    op.drop_table('server_subusers')
