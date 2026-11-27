"""Add managed database service records."""
from alembic import op
import sqlalchemy as sa

revision = '0012_database_services'
down_revision = '0011_sftp_access'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'database_services',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('server_id', sa.Integer(), sa.ForeignKey('game_servers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_id', sa.Integer(), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('db_type', sa.String(16), nullable=False),
        sa.Column('database_name', sa.String(64), nullable=False),
        sa.Column('username', sa.String(32), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, unique=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='provisioning'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_database_services_server_id', 'database_services', ['server_id'])
    op.create_index('ix_database_services_node_id', 'database_services', ['node_id'])

def downgrade():
    op.drop_index('ix_database_services_node_id', table_name='database_services')
    op.drop_index('ix_database_services_server_id', table_name='database_services')
    op.drop_table('database_services')
