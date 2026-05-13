"""billing fields

Revision ID: 0003_billing_fields
Revises: 0002_scoped_keys_and_quotas
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_billing_fields"
down_revision = "0002_scoped_keys_and_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("stripe_customer_id", sa.String(length=120), nullable=True))
    op.add_column("tenants", sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True))
    op.add_column("tenants", sa.Column("subscription_status", sa.String(length=40), nullable=False, server_default="trialing"))
    op.create_index(op.f("ix_tenants_stripe_customer_id"), "tenants", ["stripe_customer_id"], unique=False)
    op.create_index(op.f("ix_tenants_stripe_subscription_id"), "tenants", ["stripe_subscription_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_stripe_subscription_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_stripe_customer_id"), table_name="tenants")
    op.drop_column("tenants", "subscription_status")
    op.drop_column("tenants", "stripe_subscription_id")
    op.drop_column("tenants", "stripe_customer_id")
