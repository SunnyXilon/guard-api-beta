"""Add assignee to review cases.

Revision ID: 0005_review_case_assignee
Revises: 0004_clerk_tenant_ownership
Create Date: 2026-05-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_review_case_assignee"
down_revision = "0004_clerk_tenant_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_cases", sa.Column("assignee", sa.String(length=120), nullable=True))
    op.create_index(op.f("ix_review_cases_assignee"), "review_cases", ["assignee"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_cases_assignee"), table_name="review_cases")
    op.drop_column("review_cases", "assignee")
