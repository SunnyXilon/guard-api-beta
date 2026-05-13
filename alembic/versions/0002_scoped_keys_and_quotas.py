"""scoped keys and tenant quotas

Revision ID: 0002_scoped_keys_and_quotas
Revises: 0001_startup_ready_schema
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_scoped_keys_and_quotas"
down_revision = "0001_startup_ready_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("plan_name", sa.String(length=80), nullable=False, server_default="starter"))
    op.add_column("tenants", sa.Column("monthly_quota", sa.Integer(), nullable=False, server_default="1000"))
    op.add_column("api_keys", sa.Column("scopes", sa.JSON(), nullable=False, server_default='["moderation"]'))

    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect == "sqlite":
        connection.execute(sa.text("UPDATE api_keys SET scopes = '[\"moderation\", \"dashboard\", \"policy:write\"]'"))
    else:
        connection.execute(sa.text("UPDATE api_keys SET scopes = '[\"moderation\", \"dashboard\", \"policy:write\"]'"))


def downgrade() -> None:
    op.drop_column("api_keys", "scopes")
    op.drop_column("tenants", "monthly_quota")
    op.drop_column("tenants", "plan_name")
