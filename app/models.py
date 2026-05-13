from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    billing_scope: Mapped[str] = mapped_column(String(20), default="account")
    plan_name: Mapped[str] = mapped_column(String(80), default="starter")
    monthly_quota: Mapped[int] = mapped_column(Integer, default=1000)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    subscription_status: Mapped[str] = mapped_column(String(40), default="trialing")
    clerk_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    clerk_org_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    policy: Mapped["TenantPolicy"] = relationship(back_populates="tenant", cascade="all, delete-orphan", uselist=False)
    connected_accounts: Mapped[list["ConnectedAccountRecord"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(32), index=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="api_keys")


class TenantPolicy(Base):
    __tablename__ = "tenant_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), unique=True)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    thresholds: Mapped[dict] = mapped_column(JSON, default=dict)
    review_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    protected_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_version: Mapped[str] = mapped_column(String(64), default="2026-04-mvp")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="policy")


class ModerationRequestRecord(Base):
    __tablename__ = "moderation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    modality: Mapped[str] = mapped_column(String(32), index=True)
    content_text: Mapped[str] = mapped_column(Text, default="")
    content_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class ModerationResultRecord(Base):
    __tablename__ = "moderation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("moderation_requests.id"), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    category_scores: Mapped[list] = mapped_column(JSON, default=list)
    matched_policy_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReviewCaseRecord(Base):
    __tablename__ = "review_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("moderation_requests.id"), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(Integer, default=40)
    submitted_text: Mapped[str] = mapped_column(Text, default="")
    category_scores: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class ConnectedAccountRecord(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    provider_account_id: Mapped[str] = mapped_column(String(160), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(60), default="business")
    status: Mapped[str] = mapped_column(String(40), default="connected", index=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="connected_accounts")


class SocialEventRecord(Base):
    __tablename__ = "social_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    connected_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("connected_accounts.id"),
        nullable=True,
        index=True,
    )
    moderation_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("moderation_requests.id"),
        nullable=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(40), index=True)
    external_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="comment", index=True)
    actor_handle: Mapped[str | None] = mapped_column(String(160), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, default="")
    content_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    decision_action: Mapped[str] = mapped_column(String(20), default="allow", index=True)
    triggered_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SocialActionRecord(Base):
    __tablename__ = "social_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    social_event_id: Mapped[str] = mapped_column(ForeignKey("social_events.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    actor_type: Mapped[str] = mapped_column(String(40), default="tenant_admin")
    external_action_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("moderation_requests.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="system")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
