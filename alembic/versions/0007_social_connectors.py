"""add social connector tables

Revision ID: 0007_social_connectors
Revises: 0006_billing_scope
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_social_connectors"
down_revision = "0006_billing_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("provider_account_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("account_type", sa.String(length=60), nullable=False, server_default="business"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="connected"),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_connected_accounts_tenant_id", "connected_accounts", ["tenant_id"])
    op.create_index("ix_connected_accounts_platform", "connected_accounts", ["platform"])
    op.create_index("ix_connected_accounts_provider_account_id", "connected_accounts", ["provider_account_id"])
    op.create_index("ix_connected_accounts_status", "connected_accounts", ["status"])
    op.create_index("ix_connected_accounts_created_at", "connected_accounts", ["created_at"])

    op.create_table(
        "social_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("connected_account_id", sa.String(length=36), sa.ForeignKey("connected_accounts.id"), nullable=True),
        sa.Column("moderation_request_id", sa.String(length=36), sa.ForeignKey("moderation_requests.id"), nullable=True),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("external_event_id", sa.String(length=200), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="comment"),
        sa.Column("actor_handle", sa.String(length=160), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_url", sa.String(length=500), nullable=True),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("decision_action", sa.String(length=20), nullable=False, server_default="allow"),
        sa.Column("triggered_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_social_events_tenant_id", "social_events", ["tenant_id"])
    op.create_index("ix_social_events_connected_account_id", "social_events", ["connected_account_id"])
    op.create_index("ix_social_events_moderation_request_id", "social_events", ["moderation_request_id"])
    op.create_index("ix_social_events_platform", "social_events", ["platform"])
    op.create_index("ix_social_events_external_event_id", "social_events", ["external_event_id"])
    op.create_index("ix_social_events_source_type", "social_events", ["source_type"])
    op.create_index("ix_social_events_decision_action", "social_events", ["decision_action"])
    op.create_index("ix_social_events_status", "social_events", ["status"])
    op.create_index("ix_social_events_created_at", "social_events", ["created_at"])

    op.create_table(
        "social_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("social_event_id", sa.String(length=36), sa.ForeignKey("social_events.id"), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="completed"),
        sa.Column("actor_type", sa.String(length=40), nullable=False, server_default="tenant_admin"),
        sa.Column("external_action_id", sa.String(length=200), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_social_actions_tenant_id", "social_actions", ["tenant_id"])
    op.create_index("ix_social_actions_social_event_id", "social_actions", ["social_event_id"])
    op.create_index("ix_social_actions_action_type", "social_actions", ["action_type"])
    op.create_index("ix_social_actions_status", "social_actions", ["status"])
    op.create_index("ix_social_actions_created_at", "social_actions", ["created_at"])


def downgrade() -> None:
    op.drop_table("social_actions")
    op.drop_table("social_events")
    op.drop_table("connected_accounts")
