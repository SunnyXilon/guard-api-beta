from __future__ import annotations

from app.policy import DEFAULT_TENANT_POLICIES
from app.repositories.tenants import TenantRepository
from app.schemas import MIN_POLICY_THRESHOLD, PolicyOverride, TenantPolicyConfig, TenantPolicyUpdate
from app.taxonomy import DEFAULT_CATEGORY_THRESHOLDS, DecisionAction, ModerationCategory


class PolicyService:
    def __init__(self, tenant_repository: TenantRepository) -> None:
        self.tenant_repository = tenant_repository

    def get_policy_for_tenant(self, tenant_slug: str) -> TenantPolicyConfig:
        policy_row = self.tenant_repository.get_policy_by_slug(tenant_slug)
        if not policy_row:
            return self._with_effective_thresholds(
                DEFAULT_TENANT_POLICIES.get(tenant_slug, DEFAULT_TENANT_POLICIES["default"])
            )

        thresholds = {
            ModerationCategory(category): PolicyOverride(**self._sanitize_override(override))
            for category, override in (policy_row.thresholds or {}).items()
        }
        return self._with_effective_thresholds(TenantPolicyConfig(
            tenant_id=tenant_slug,
            labels=policy_row.labels,
            thresholds=thresholds,
            review_enabled=policy_row.review_enabled,
            protected_mode=policy_row.protected_mode,
        ))

    def update_policy_for_tenant(self, tenant_slug: str, update: TenantPolicyUpdate) -> TenantPolicyConfig:
        policy_row = self.tenant_repository.get_policy_by_slug(tenant_slug)
        if not policy_row:
            return DEFAULT_TENANT_POLICIES.get(tenant_slug, DEFAULT_TENANT_POLICIES["default"])

        current = dict(policy_row.thresholds or {})
        for category, override in update.thresholds.items():
            review = override.review
            block = override.block
            if review is not None and block is not None and review > block:
                review, block = block, review
            current[category.value] = PolicyOverride(review=review, block=block).model_dump(exclude_none=True)

        policy_row.thresholds = current
        if update.review_enabled is not None:
            policy_row.review_enabled = update.review_enabled
        if update.protected_mode is not None:
            policy_row.protected_mode = update.protected_mode

        self.tenant_repository.db.add(policy_row)
        self.tenant_repository.db.commit()
        self.tenant_repository.db.refresh(policy_row)
        return self.get_policy_for_tenant(tenant_slug)

    @staticmethod
    def _sanitize_override(override: dict) -> dict:
        sanitized = dict(override)
        for key in ("review", "block"):
            value = sanitized.get(key)
            if value is not None and value < MIN_POLICY_THRESHOLD:
                sanitized[key] = MIN_POLICY_THRESHOLD
        return sanitized

    @classmethod
    def _with_effective_thresholds(cls, policy: TenantPolicyConfig) -> TenantPolicyConfig:
        thresholds: dict[ModerationCategory, PolicyOverride] = {}
        for category in ModerationCategory:
            default_threshold = DEFAULT_CATEGORY_THRESHOLDS[category]
            override = policy.thresholds.get(category)
            thresholds[category] = PolicyOverride(
                review=(
                    override.review
                    if override and override.review is not None
                    else default_threshold[DecisionAction.REVIEW]
                ),
                block=(
                    override.block
                    if override and override.block is not None
                    else default_threshold[DecisionAction.BLOCK]
                ),
            )
        return policy.model_copy(update={"thresholds": thresholds})
