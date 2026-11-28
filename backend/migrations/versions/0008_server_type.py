"""Add Minecraft server type selection."""
from alembic import op
import sqlalchemy as sa

revision = '0008_server_type'
down_revision = '0007_backup_schedules'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('game_servers', sa.Column('server_type', sa.String(16), nullable=False, server_default='paper'))

def downgrade():
    op.drop_column('game_servers', 'server_type')
