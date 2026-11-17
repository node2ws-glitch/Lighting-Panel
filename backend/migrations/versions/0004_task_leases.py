"""Add node task claim lease timestamp."""
from alembic import op
import sqlalchemy as sa
revision = '0004_task_leases'
down_revision = '0003_servers'
branch_labels = None
depends_on = None
def upgrade():
    op.add_column('node_tasks', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
def downgrade():
    op.drop_column('node_tasks', 'claimed_at')
