"""Add per-server network allocations."""
from alembic import op
import sqlalchemy as sa

revision = '0009_server_allocations'
down_revision = '0008_server_type'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'server_allocations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('server_id', sa.Integer(), sa.ForeignKey('game_servers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, unique=True),
        sa.Column('container_port', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.String(8), nullable=False, server_default='tcp'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_server_allocations_server_id', 'server_allocations', ['server_id'])

def downgrade():
    op.drop_index('ix_server_allocations_server_id', table_name='server_allocations')
    op.drop_table('server_allocations')
