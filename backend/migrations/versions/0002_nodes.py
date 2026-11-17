"""Add node inventory and telemetry."""
from alembic import op
import sqlalchemy as sa
revision = '0002_nodes'
down_revision = '0001_initial'
branch_labels = None
depends_on = None
def upgrade():
    op.create_table('nodes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(80), nullable=False, unique=True),
        sa.Column('fqdn', sa.String(255), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('cpu_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('memory_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('memory_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('disk_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('disk_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
def downgrade():
    op.drop_table('nodes')
