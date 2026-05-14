from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.repositories.moderation import ModerationRepository
from app.schemas import (
    AuthenticatedTenant,
    DashboardSummary,
    ModerationDecisionItem,
    TenantPolicyConfig,
    UsageSummary,
)
from app.taxonomy import DecisionAction, ModerationCategory
from app.usage_credits import credits_for_record


class DashboardService:
    def __init__(self, moderation_repository: ModerationRepository) -> None:
        self.moderation_repository = moderation_repository

    def recent_decisions(self, tenant_id: str, limit: int = 20) -> list[ModerationDecisionItem]:
        rows = self.moderation_repository.list_recent_decisions(tenant_id=tenant_id, limit=limit)
        decisions: list[ModerationDecisionItem] = []
        for request, result in rows:
            categories = [
                ModerationCategory(score["category"])
                for score in result.category_scores
                if score.get("score", 0) >= 0.2
            ]
            decisions.append(
                ModerationDecisionItem(
                    request_id=request.id,
                    modality=request.modality,
                    action=DecisionAction(result.action),
                    triggered_categories=categories,
                    explanation=result.explanation,
                    content_preview=self._preview(request.content_text),
                    fallback_model=(result.metadata_json or {}).get("fallback_model", "not_used"),
                    created_at=request.created_at,
                )
            )
        return decisions

    def usage_this_month(self, tenant_id: str, monthly_quota: int, plan_name: str) -> UsageSummary:
        return self.usage_this_month_for_tenants([tenant_id], monthly_quota, plan_name)

    def usage_this_month_for_tenants(
        self,
        tenant_ids: list[str],
        monthly_quota: int,
        plan_name: str,
        billing_scope: str = "account",
    ) -> UsageSummary:
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        decisions = self.moderation_repository.list_request_results_between_tenants(tenant_ids, start=start, end=end)
        used_credits = sum(credits_for_record(request.modality, request.content_metadata) for request, _result in decisions)
        counts = Counter(result.action for _request, result in decisions)
        request_count = len(decisions)
        remaining_credits = max(monthly_quota - used_credits, 0)
        return UsageSummary(
            month=start.strftime("%Y-%m"),
            # Backward compatibility: dashboard clients historically read this as weighted credit usage.
            total_requests=used_credits,
            monthly_quota=monthly_quota,
            remaining_requests=remaining_credits,
            request_count=request_count,
            used_credits=used_credits,
            remaining_credits=remaining_credits,
            credit_unit="Guard credits",
            plan_name=plan_name,
            billing_scope=billing_scope,
            allow=counts.get(DecisionAction.ALLOW.value, 0),
            review=counts.get(DecisionAction.REVIEW.value, 0),
            block=counts.get(DecisionAction.BLOCK.value, 0),
        )

    def summary(
        self,
        tenant: AuthenticatedTenant,
        tenant_row_id: str,
        monthly_quota: int,
        plan_name: str,
        policy: TenantPolicyConfig,
        billing_scope: str = "account",
        usage_tenant_ids: list[str] | None = None,
    ) -> DashboardSummary:
        return DashboardSummary(
            tenant=tenant,
            usage=self.usage_this_month_for_tenants(
                usage_tenant_ids or [tenant_row_id],
                monthly_quota,
                plan_name,
                billing_scope,
            ),
            recent_decisions=self.recent_decisions(tenant_row_id),
            policy=policy,
        )

    @staticmethod
    def _preview(text: str, max_length: int = 140) -> str:
        clean = " ".join((text or "").split())
        if len(clean) <= max_length:
            return clean
        return clean[: max_length - 3] + "..."
