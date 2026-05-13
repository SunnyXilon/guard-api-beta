from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ApiKey, Tenant, TenantPolicy
from app.schemas import TenantPolicyConfig
from app.security import api_key_prefix, generate_api_key, hash_api_key


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        return self.db.query(Tenant).filter(Tenant.slug == slug).one_or_none()

    def active_account_scope_tenants(self, tenant: Tenant) -> list[Tenant]:
        if tenant.clerk_org_id:
            tenants = (
                self.db.query(Tenant)
                .filter(
                    Tenant.clerk_org_id == tenant.clerk_org_id,
                    Tenant.is_active.is_(True),
                    Tenant.billing_scope == "account",
                )
                .order_by(Tenant.created_at.asc())
                .all()
            )
            if tenants:
                return tenants
        if tenant.clerk_user_id:
            return (
                self.db.query(Tenant)
                .filter(
                    Tenant.clerk_user_id == tenant.clerk_user_id,
                    Tenant.is_active.is_(True),
                    Tenant.billing_scope == "account",
                )
                .order_by(Tenant.created_at.asc())
                .all()
            )
        return []

    def get_tenant_by_clerk_owner(self, clerk_user_id: str, clerk_org_id: str | None = None) -> Tenant | None:
        if clerk_org_id:
            tenant = self.db.query(Tenant).filter(Tenant.clerk_org_id == clerk_org_id, Tenant.is_active.is_(True)).first()
            if tenant:
                return tenant
        return self.db.query(Tenant).filter(Tenant.clerk_user_id == clerk_user_id, Tenant.is_active.is_(True)).first()

    def list_tenants_by_clerk_owner(self, clerk_user_id: str, clerk_org_id: str | None = None) -> list[Tenant]:
        if clerk_org_id:
            tenants = (
                self.db.query(Tenant)
                .filter(Tenant.clerk_org_id == clerk_org_id, Tenant.is_active.is_(True))
                .order_by(Tenant.created_at.asc())
                .all()
            )
            if tenants:
                return tenants
        return (
            self.db.query(Tenant)
            .filter(Tenant.clerk_user_id == clerk_user_id, Tenant.is_active.is_(True))
            .order_by(Tenant.created_at.asc())
            .all()
        )

    def get_tenant_by_clerk_owner_and_slug(
        self,
        clerk_user_id: str,
        slug: str,
        clerk_org_id: str | None = None,
    ) -> Tenant | None:
        query = self.db.query(Tenant).filter(Tenant.slug == slug, Tenant.is_active.is_(True))
        if clerk_org_id:
            tenant = query.filter(Tenant.clerk_org_id == clerk_org_id).one_or_none()
            if tenant:
                return tenant
        return query.filter(Tenant.clerk_user_id == clerk_user_id).one_or_none()

    def deactivate_workspace(self, tenant: Tenant) -> Tenant:
        tenant.is_active = False
        self.db.add(tenant)
        for api_key in self.db.query(ApiKey).filter(ApiKey.tenant_id == tenant.id).all():
            api_key.is_active = False
            self.db.add(api_key)
        self.db.flush()
        return tenant

    def quota_scope_for_tenant(self, tenant: Tenant) -> tuple[list[str], int, str]:
        if tenant.billing_scope == "workspace":
            return [tenant.id], tenant.monthly_quota, tenant.plan_name
        if tenant.clerk_org_id or tenant.clerk_user_id:
            tenants = self.active_account_scope_tenants(tenant)
            if tenants:
                quota_owner = max(tenants, key=lambda row: row.monthly_quota)
                return [row.id for row in tenants], quota_owner.monthly_quota, quota_owner.plan_name
        return [tenant.id], tenant.monthly_quota, tenant.plan_name

    def set_billing_scope(self, tenant: Tenant, billing_scope: str) -> Tenant:
        tenant.billing_scope = billing_scope
        if billing_scope == "account":
            account_tenants = [row for row in self.active_account_scope_tenants(tenant) if row.id != tenant.id]
            if account_tenants:
                quota_owner = max(account_tenants, key=lambda row: row.monthly_quota)
                tenant.plan_name = quota_owner.plan_name
                tenant.monthly_quota = quota_owner.monthly_quota
                tenant.stripe_customer_id = quota_owner.stripe_customer_id
                tenant.stripe_subscription_id = quota_owner.stripe_subscription_id
                tenant.subscription_status = quota_owner.subscription_status
        self.db.add(tenant)
        self.db.flush()
        return tenant

    def get_policy_by_slug(self, slug: str) -> TenantPolicy | None:
        tenant = self.get_tenant_by_slug(slug)
        if not tenant:
            return None
        return self.db.query(TenantPolicy).filter(TenantPolicy.tenant_id == tenant.id).one_or_none()

    def get_api_key(self, raw_key: str) -> ApiKey | None:
        hashed = hash_api_key(raw_key)
        prefix = api_key_prefix(raw_key)
        return (
            self.db.query(ApiKey)
            .filter(ApiKey.key_hash == hashed, ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
            .one_or_none()
        )

    def create_api_key(self, tenant: Tenant, raw_key: str, name: str, scopes: list[str]) -> ApiKey:
        existing = self.get_api_key(raw_key)
        if existing:
            existing.scopes = scopes
            existing.name = name
            self.db.add(existing)
            self.db.flush()
            return existing

        api_key = ApiKey(
            tenant_id=tenant.id,
            name=name,
            key_prefix=api_key_prefix(raw_key),
            key_hash=hash_api_key(raw_key),
            scopes=scopes,
        )
        self.db.add(api_key)
        self.db.flush()
        return api_key

    def create_generated_api_key(self, tenant: Tenant, name: str, scopes: list[str]) -> tuple[ApiKey, str]:
        raw_key = generate_api_key()
        api_key = self.create_api_key(tenant, raw_key, name, scopes)
        return api_key, raw_key

    def list_api_keys(self, tenant_id: str) -> list[ApiKey]:
        return (
            self.db.query(ApiKey)
            .filter(ApiKey.tenant_id == tenant_id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )

    def deactivate_api_key(self, tenant_id: str, api_key_id: str) -> ApiKey | None:
        api_key = (
            self.db.query(ApiKey)
            .filter(ApiKey.tenant_id == tenant_id, ApiKey.id == api_key_id)
            .one_or_none()
        )
        if not api_key:
            return None
        api_key.is_active = False
        self.db.add(api_key)
        self.db.flush()
        return api_key

    def rotate_api_key(self, tenant_id: str, api_key_id: str) -> tuple[ApiKey, str] | None:
        api_key = (
            self.db.query(ApiKey)
            .filter(ApiKey.tenant_id == tenant_id, ApiKey.id == api_key_id)
            .one_or_none()
        )
        if not api_key:
            return None

        api_key.is_active = False
        self.db.add(api_key)
        replacement, raw_key = self.create_generated_api_key(
            api_key.tenant,
            api_key.name,
            list(api_key.scopes or []),
        )
        self.db.flush()
        return replacement, raw_key

    def create_tenant_with_policy(
        self,
        slug: str,
        policy: TenantPolicyConfig,
        raw_key: str | None,
        name: str | None = None,
        admin_key: str | None = None,
        monthly_quota: int = 1000,
        plan_name: str = "starter",
        clerk_user_id: str | None = None,
        clerk_org_id: str | None = None,
    ) -> Tenant:
        tenant = self.get_tenant_by_slug(slug)
        if tenant:
            tenant.monthly_quota = monthly_quota
            tenant.plan_name = plan_name
            tenant.clerk_user_id = clerk_user_id or tenant.clerk_user_id
            tenant.clerk_org_id = clerk_org_id or tenant.clerk_org_id
            self.db.add(tenant)
            if raw_key:
                self.create_api_key(tenant, raw_key, f"{slug}-moderation", ["moderation"])
            if admin_key:
                self.create_api_key(tenant, admin_key, f"{slug}-admin", ["dashboard", "policy:write"])
            return tenant

        tenant = Tenant(
            slug=slug,
            name=name or slug,
            monthly_quota=monthly_quota,
            plan_name=plan_name,
            clerk_user_id=clerk_user_id,
            clerk_org_id=clerk_org_id,
        )
        self.db.add(tenant)
        self.db.flush()

        policy_row = TenantPolicy(
            tenant_id=tenant.id,
            labels=policy.labels,
            thresholds={k.value: v.model_dump(exclude_none=True) for k, v in policy.thresholds.items()},
            review_enabled=policy.review_enabled,
            protected_mode=policy.protected_mode,
        )
        self.db.add(policy_row)
        if raw_key:
            self.create_api_key(tenant, raw_key, f"{slug}-moderation", ["moderation"])
        if admin_key:
            self.create_api_key(tenant, admin_key, f"{slug}-admin", ["dashboard", "policy:write"])
        self.db.flush()
        return tenant
