"""Create users and audit log tables."""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('email', sa.String(254), nullable=False), sa.Column('username', sa.String(32), nullable=False), sa.Column('password_hash', sa.String(255), nullable=False), sa.Column('role', sa.String(16), nullable=False, server_default='user'), sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint('email'), sa.UniqueConstraint('username'))
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_table('audit_events', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True), sa.Column('action', sa.String(80), nullable=False), sa.Column('detail', sa.Text(), nullable=False, server_default=''), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_audit_events_action', 'audit_events', ['action'])

def downgrade():
    op.drop_index('ix_audit_events_action', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
