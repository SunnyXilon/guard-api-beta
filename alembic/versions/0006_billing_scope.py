"""add billing scope to tenants

Revision ID: 0006_billing_scope
Revises: 0005_review_case_assignee
Create Date: 2026-05-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_billing_scope"
down_revision = "0005_review_case_assignee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("billing_scope", sa.String(length=20), nullable=False, server_default="account"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "billing_scope")
