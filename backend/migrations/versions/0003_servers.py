"""Add Minecraft server records and queued node tasks."""
from alembic import op
import sqlalchemy as sa

revision = '0003_servers'
down_revision = '0002_nodes'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'game_servers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('node_id', sa.Integer(), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(48), nullable=False),
        sa.Column('game', sa.String(24), nullable=False, server_default='minecraft'),
        sa.Column('version', sa.String(24), nullable=False, server_default='LATEST'),
        sa.Column('memory_mb', sa.Integer(), nullable=False),
        sa.Column('cpu_limit', sa.Float(), nullable=False),
        sa.Column('allocation_port', sa.Integer(), nullable=False, unique=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='installing'),
        sa.Column('docker_id', sa.String(128), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_game_servers_node_id', 'game_servers', ['node_id'])
    op.create_table(
        'node_tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('node_id', sa.Integer(), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('server_id', sa.Integer(), sa.ForeignKey('game_servers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(24), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_node_tasks_node_id', 'node_tasks', ['node_id'])
    op.create_index('ix_node_tasks_status', 'node_tasks', ['status'])

def downgrade():
    op.drop_index('ix_node_tasks_status', table_name='node_tasks')
    op.drop_index('ix_node_tasks_node_id', table_name='node_tasks')
    op.drop_table('node_tasks')
    op.drop_index('ix_game_servers_node_id', table_name='game_servers')
    op.drop_table('game_servers')
