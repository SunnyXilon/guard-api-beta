from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import Base
from app.policy import default_policy_configs
from app.repositories.tenants import TenantRepository
from app.settings import Settings


def init_db(engine) -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_runtime_columns(engine)


def _ensure_runtime_columns(engine) -> None:
    inspector = inspect(engine)
    if "tenants" not in inspector.get_table_names():
        return

    tenant_columns = {column["name"] for column in inspector.get_columns("tenants")}
    if "billing_scope" not in tenant_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE tenants ADD COLUMN billing_scope VARCHAR(20) NOT NULL DEFAULT 'account'"))


def bootstrap_defaults(db: Session, settings: Settings) -> None:
    if not settings.bootstrap_api_keys:
        return

    tenant_repo = TenantRepository(db)
    configured_keys = {}
    for item in settings.bootstrap_default_keys.split(","):
        slug, raw_key = item.split(":", 1)
        configured_keys[slug.strip()] = raw_key.strip()
    configured_admin_keys = {}
    for item in settings.bootstrap_admin_keys.split(","):
        if not item.strip():
            continue
        slug, raw_key = item.split(":", 1)
        configured_admin_keys[slug.strip()] = raw_key.strip()

    for policy in default_policy_configs():
        raw_key = configured_keys.get(policy.tenant_id, f"{policy.tenant_id}_dev_key")
        admin_key = configured_admin_keys.get(policy.tenant_id, f"{policy.tenant_id}_admin_dev_key")
        tenant_repo.create_tenant_with_policy(
            policy.tenant_id,
            policy,
            raw_key,
            name=policy.tenant_id,
            admin_key=admin_key,
            monthly_quota=settings.bootstrap_monthly_quota,
        )

    db.commit()
