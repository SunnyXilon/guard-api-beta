"""clerk tenant ownership

Revision ID: 0004_clerk_tenant_ownership
Revises: 0003_billing_fields
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_clerk_tenant_ownership"
down_revision = "0003_billing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("clerk_user_id", sa.String(length=120), nullable=True))
    op.add_column("tenants", sa.Column("clerk_org_id", sa.String(length=120), nullable=True))
    op.create_index(op.f("ix_tenants_clerk_user_id"), "tenants", ["clerk_user_id"], unique=False)
    op.create_index(op.f("ix_tenants_clerk_org_id"), "tenants", ["clerk_org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_clerk_org_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_clerk_user_id"), table_name="tenants")
    op.drop_column("tenants", "clerk_org_id")
    op.drop_column("tenants", "clerk_user_id")
