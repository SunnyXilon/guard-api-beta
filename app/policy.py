from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from app.schemas import MIN_POLICY_THRESHOLD, CategoryResult, ModerationDecision, PolicyOverride, TenantPolicyConfig
from app.taxonomy import (
    DEFAULT_CATEGORY_THRESHOLDS,
    DecisionAction,
    ModerationCategory,
)


@dataclass(frozen=True)
class DecisionContext:
    label: str
    category: ModerationCategory
    score: float


PROTECTED_MODE_THRESHOLD_FACTORS = {
    DecisionAction.REVIEW: 0.8,
    DecisionAction.BLOCK: 0.9,
}


DEFAULT_TENANT_POLICIES: Dict[str, TenantPolicyConfig] = {
    "default": TenantPolicyConfig(
        tenant_id="default",
        labels=["ugc-default", "text-realtime"],
    ),
    "kids-safe": TenantPolicyConfig(
        tenant_id="kids-safe",
        labels=["ugc-kids", "strict-safety"],
        protected_mode=True,
        thresholds={
            ModerationCategory.SEXUAL_CONTENT: PolicyOverride(review=0.3, block=0.55),
            ModerationCategory.VIOLENCE: PolicyOverride(review=0.3, block=0.6),
            ModerationCategory.CHILD_SAFETY: PolicyOverride(review=0.15, block=0.35),
        },
    ),
    "marketplace": TenantPolicyConfig(
        tenant_id="marketplace",
        labels=["ugc-marketplace", "anti-fraud"],
        thresholds={
            ModerationCategory.SPAM_SCAM: PolicyOverride(review=0.45, block=0.72),
            ModerationCategory.ILLEGAL_ACTIVITY: PolicyOverride(review=0.35, block=0.62),
            ModerationCategory.PII_LEAKAGE: PolicyOverride(review=0.3, block=0.64),
        },
    ),
}


def get_policy(tenant_id: str) -> TenantPolicyConfig:
    return DEFAULT_TENANT_POLICIES.get(tenant_id, DEFAULT_TENANT_POLICIES["default"])


def default_policy_configs() -> list[TenantPolicyConfig]:
    return list(DEFAULT_TENANT_POLICIES.values())


def _threshold_for(
    policy: TenantPolicyConfig, category: ModerationCategory, action: DecisionAction
) -> float:
    override = policy.thresholds.get(category)
    if override:
        value = getattr(override, action.value, None)
        if value is not None:
            return _apply_protected_mode(policy, action, value)
    return _apply_protected_mode(policy, action, DEFAULT_CATEGORY_THRESHOLDS[category][action])


def _apply_protected_mode(policy: TenantPolicyConfig, action: DecisionAction, threshold: float) -> float:
    if not policy.protected_mode:
        return threshold
    return max(MIN_POLICY_THRESHOLD, threshold * PROTECTED_MODE_THRESHOLD_FACTORS[action])


def _decision_contexts(
    results: Iterable[CategoryResult], policy: TenantPolicyConfig
) -> List[DecisionContext]:
    contexts: List[DecisionContext] = []
    for result in results:
        review_threshold = _threshold_for(policy, result.category, DecisionAction.REVIEW)
        block_threshold = _threshold_for(policy, result.category, DecisionAction.BLOCK)

        if result.score >= block_threshold:
            contexts.append(
                DecisionContext(
                    label=f"{result.category.value}:block",
                    category=result.category,
                    score=result.score,
                )
            )
        elif result.score >= review_threshold and policy.review_enabled:
            contexts.append(
                DecisionContext(
                    label=f"{result.category.value}:review",
                    category=result.category,
                    score=result.score,
                )
            )
    return contexts


def evaluate_policy(
    results: List[CategoryResult], policy: TenantPolicyConfig
) -> ModerationDecision:
    contexts = _decision_contexts(results, policy)
    if not contexts:
        return ModerationDecision(
            action=DecisionAction.ALLOW,
            triggered_categories=[],
            matched_policy_labels=policy.labels,
            explanation="No category crossed the review threshold.",
        )

    highest = max(contexts, key=lambda item: item.score)
    has_block = any(ctx.label.endswith(":block") for ctx in contexts)
    action = DecisionAction.BLOCK if has_block else DecisionAction.REVIEW

    triggered = []
    for ctx in contexts:
        if ctx.category not in triggered:
            triggered.append(ctx.category)

    explanation = (
        f"Policy {policy.tenant_id} marked the content as {action.value} because "
        f"{highest.category.value} scored {highest.score:.2f}."
    )
    labels = policy.labels + [ctx.label for ctx in contexts]
    if policy.protected_mode:
        labels.append("protected_mode")
        explanation = f"{explanation} Protected mode applied stricter thresholds."

    return ModerationDecision(
        action=action,
        triggered_categories=triggered,
        matched_policy_labels=labels,
        explanation=explanation,
    )
