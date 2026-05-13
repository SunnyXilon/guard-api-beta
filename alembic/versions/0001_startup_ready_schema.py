"""startup ready schema

Revision ID: 0001_startup_ready_schema
Revises:
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_startup_ready_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=True)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True)
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"], unique=False)
    op.create_index(op.f("ix_api_keys_tenant_id"), "api_keys", ["tenant_id"], unique=False)

    op.create_table(
        "tenant_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("review_enabled", sa.Boolean(), nullable=False),
        sa.Column("protected_mode", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )

    op.create_table(
        "moderation_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("modality", sa.String(length=32), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_moderation_requests_created_at"), "moderation_requests", ["created_at"], unique=False)
    op.create_index(op.f("ix_moderation_requests_modality"), "moderation_requests", ["modality"], unique=False)
    op.create_index(op.f("ix_moderation_requests_tenant_id"), "moderation_requests", ["tenant_id"], unique=False)

    op.create_table(
        "moderation_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("category_scores", sa.JSON(), nullable=False),
        sa.Column("matched_policy_labels", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["moderation_requests.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index(op.f("ix_moderation_results_action"), "moderation_results", ["action"], unique=False)
    op.create_index(op.f("ix_moderation_results_request_id"), "moderation_results", ["request_id"], unique=True)
    op.create_index(op.f("ix_moderation_results_tenant_id"), "moderation_results", ["tenant_id"], unique=False)

    op.create_table(
        "review_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("submitted_text", sa.Text(), nullable=False),
        sa.Column("category_scores", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["moderation_requests.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index(op.f("ix_review_cases_created_at"), "review_cases", ["created_at"], unique=False)
    op.create_index(op.f("ix_review_cases_request_id"), "review_cases", ["request_id"], unique=True)
    op.create_index(op.f("ix_review_cases_status"), "review_cases", ["status"], unique=False)
    op.create_index(op.f("ix_review_cases_tenant_id"), "review_cases", ["tenant_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["moderation_requests.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_audit_events_request_id"), "audit_events", ["request_id"], unique=False)
    op.create_index(op.f("ix_audit_events_tenant_id"), "audit_events", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_tenant_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_request_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_event_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_created_at"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_review_cases_tenant_id"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_status"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_request_id"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_created_at"), table_name="review_cases")
    op.drop_table("review_cases")
    op.drop_index(op.f("ix_moderation_results_tenant_id"), table_name="moderation_results")
    op.drop_index(op.f("ix_moderation_results_request_id"), table_name="moderation_results")
    op.drop_index(op.f("ix_moderation_results_action"), table_name="moderation_results")
    op.drop_table("moderation_results")
    op.drop_index(op.f("ix_moderation_requests_tenant_id"), table_name="moderation_requests")
    op.drop_index(op.f("ix_moderation_requests_modality"), table_name="moderation_requests")
    op.drop_index(op.f("ix_moderation_requests_created_at"), table_name="moderation_requests")
    op.drop_table("moderation_requests")
    op.drop_table("tenant_policies")
    op.drop_index(op.f("ix_api_keys_tenant_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_table("tenants")
