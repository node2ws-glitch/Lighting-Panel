"""Add Stripe billing records and webhook idempotency."""
from alembic import op
import sqlalchemy as sa

revision = '0006_billing'
down_revision = '0005_server_subusers'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'billing_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('stripe_customer_id', sa.String(128), nullable=True, unique=True),
        sa.Column('stripe_subscription_id', sa.String(128), nullable=True, unique=True),
        sa.Column('stripe_price_id', sa.String(128), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='incomplete'),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_billing_subscriptions_user_id', 'billing_subscriptions', ['user_id'])
    op.create_table(
        'billing_invoices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(128), nullable=False, unique=True),
        sa.Column('amount_due', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('amount_paid', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(8), nullable=False, server_default='usd'),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('hosted_invoice_url', sa.String(2048), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_billing_invoices_user_id', 'billing_invoices', ['user_id'])
    op.create_table(
        'processed_billing_webhooks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('stripe_event_id', sa.String(128), nullable=False, unique=True),
        sa.Column('event_type', sa.String(128), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False),
    )

def downgrade():
    op.drop_table('processed_billing_webhooks')
    op.drop_index('ix_billing_invoices_user_id', table_name='billing_invoices')
    op.drop_table('billing_invoices')
    op.drop_index('ix_billing_subscriptions_user_id', table_name='billing_subscriptions')
    op.drop_table('billing_subscriptions')
