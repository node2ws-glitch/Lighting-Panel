"""Add per-server SFTP access records."""
from alembic import op
import sqlalchemy as sa

revision = '0011_sftp_access'
down_revision = '0010_api_keys'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'sftp_access',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('server_id', sa.Integer(), sa.ForeignKey('game_servers.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('node_id', sa.Integer(), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('username', sa.String(64), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, unique=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='provisioning'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_sftp_access_server_id', 'sftp_access', ['server_id'])
    op.create_index('ix_sftp_access_node_id', 'sftp_access', ['node_id'])

def downgrade():
    op.drop_index('ix_sftp_access_node_id', table_name='sftp_access')
    op.drop_index('ix_sftp_access_server_id', table_name='sftp_access')
    op.drop_table('sftp_access')
