from __future__ import annotations

import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Tenant
from app.settings import Settings

try:
    import stripe
except Exception:  # pragma: no cover
    stripe = None


class BillingService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def create_checkout_url(self, tenant: Tenant, plan_name: str) -> str:
        if stripe is None or not self.settings.stripe_secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe billing is not configured. Set RTCM_STRIPE_SECRET_KEY and RTCM_BILLING_PLAN_PRICE_IDS.",
            )

        price_id = self.settings.billing_plan_price_ids.get(plan_name)
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stripe price ID is missing for the {plan_name} plan.",
            )

        stripe.api_key = self.settings.stripe_secret_key
        subscription_data = {"metadata": {"tenant_slug": tenant.slug, "plan_name": plan_name}}
        if plan_name == "starter" and self.settings.billing_trial_days > 0:
            subscription_data["trial_period_days"] = self.settings.billing_trial_days

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=tenant.stripe_customer_id or None,
            client_reference_id=tenant.slug,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=self.settings.billing_success_url,
            cancel_url=self.settings.billing_cancel_url,
            metadata={"tenant_slug": tenant.slug, "plan_name": plan_name},
            subscription_data=subscription_data,
        )
        return str(session.url)

    def construct_webhook_event(self, payload: bytes, signature: str | None):
        if stripe is None or not self.settings.stripe_webhook_secret:
            if self.settings.environment == "production":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Stripe webhook verification is not configured.",
                )
            return json.loads(payload.decode("utf-8"))

        try:
            return stripe.Webhook.construct_event(payload, signature or "", self.settings.stripe_webhook_secret)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook.") from exc

    def apply_webhook_event(self, event) -> None:
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            self._apply_checkout_completed(data)
        elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
            self._apply_subscription_event(data)

    def _apply_checkout_completed(self, session: dict) -> None:
        tenant_slug = (session.get("metadata") or {}).get("tenant_slug") or session.get("client_reference_id")
        if not tenant_slug:
            return
        tenant = self.db.query(Tenant).filter(Tenant.slug == tenant_slug).one_or_none()
        if not tenant:
            return

        plan_name = (session.get("metadata") or {}).get("plan_name") or tenant.plan_name
        for account_tenant in self._billing_tenants(tenant):
            account_tenant.plan_name = plan_name
            account_tenant.monthly_quota = self.settings.billing_plan_quotas.get(plan_name, account_tenant.monthly_quota)
            account_tenant.stripe_customer_id = session.get("customer") or account_tenant.stripe_customer_id
            account_tenant.stripe_subscription_id = session.get("subscription") or account_tenant.stripe_subscription_id
            account_tenant.subscription_status = "active"
            self.db.add(account_tenant)
        self.db.commit()

    def _apply_subscription_event(self, subscription: dict) -> None:
        subscription_id = subscription.get("id")
        tenant_slug = (subscription.get("metadata") or {}).get("tenant_slug")
        tenant = None
        if subscription_id:
            tenant = self.db.query(Tenant).filter(Tenant.stripe_subscription_id == subscription_id).one_or_none()
        if tenant is None and tenant_slug:
            tenant = self.db.query(Tenant).filter(Tenant.slug == tenant_slug).one_or_none()
        if tenant is None:
            return

        plan_name = (subscription.get("metadata") or {}).get("plan_name") or tenant.plan_name
        for account_tenant in self._billing_tenants(tenant):
            account_tenant.plan_name = plan_name
            account_tenant.monthly_quota = self.settings.billing_plan_quotas.get(plan_name, account_tenant.monthly_quota)
            account_tenant.stripe_subscription_id = subscription_id or account_tenant.stripe_subscription_id
            account_tenant.stripe_customer_id = subscription.get("customer") or account_tenant.stripe_customer_id
            account_tenant.subscription_status = subscription.get("status") or account_tenant.subscription_status
            if account_tenant.subscription_status in {"canceled", "unpaid", "past_due", "incomplete_expired"}:
                account_tenant.monthly_quota = 0
            self.db.add(account_tenant)
        self.db.commit()

    def _billing_tenants(self, tenant: Tenant) -> list[Tenant]:
        if tenant.billing_scope == "workspace":
            return [tenant]
        if tenant.clerk_org_id:
            tenants = (
                self.db.query(Tenant)
                .filter(Tenant.clerk_org_id == tenant.clerk_org_id, Tenant.is_active.is_(True), Tenant.billing_scope == "account")
                .all()
            )
            if tenants:
                return tenants
        if tenant.clerk_user_id:
            tenants = (
                self.db.query(Tenant)
                .filter(Tenant.clerk_user_id == tenant.clerk_user_id, Tenant.is_active.is_(True), Tenant.billing_scope == "account")
                .all()
            )
            if tenants:
                return tenants
        return [tenant]
