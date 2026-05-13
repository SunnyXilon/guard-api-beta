from __future__ import annotations

from app.repositories.moderation import ModerationRepository
from app.schemas import CategoryResult, ReviewCase


class ReviewService:
    def __init__(self, moderation_repository: ModerationRepository) -> None:
        self.moderation_repository = moderation_repository

    @staticmethod
    def priority_from_scores(category_scores: list[CategoryResult]) -> int:
        highest = max((score.score for score in category_scores), default=0.0)
        if highest >= 0.9:
            return 100
        if highest >= 0.75:
            return 80
        if highest >= 0.55:
            return 60
        return 40

    def create_case(
        self,
        request_id: str,
        tenant_id: str,
        submitted_text: str,
        action: str,
        category_scores: list[CategoryResult],
    ) -> ReviewCase:
        priority = self.priority_from_scores(category_scores)
        record = self.moderation_repository.create_review_case(
            request_id=request_id,
            tenant_id=tenant_id,
            action=action,
            priority=priority,
            submitted_text=submitted_text,
            category_scores=[score.model_dump(mode="json") for score in category_scores],
            notes=["Auto-created from synchronous moderation decision."],
        )
        return ReviewCase(
            case_id=record.id,
            request_id=record.request_id,
            tenant_id=tenant_id,
            submitted_text=submitted_text,
            action=action,
            priority=priority,
            status=record.status,
            assignee=record.assignee,
            category_scores=category_scores,
            notes=record.notes,
            created_at=record.created_at,
        )

    def list_cases(self, tenant_id: str, tenant_slug: str | None = None) -> list[ReviewCase]:
        records = self.moderation_repository.list_review_cases(tenant_id)
        return [
            ReviewCase(
                case_id=record.id,
                request_id=record.request_id,
                tenant_id=tenant_slug or tenant_id,
                submitted_text=record.submitted_text,
                action=record.action,
                priority=record.priority,
                status=record.status,
                assignee=record.assignee,
                category_scores=[CategoryResult(**entry) for entry in record.category_scores],
                notes=record.notes,
                created_at=record.created_at,
            )
            for record in records
        ]

    def update_case(
        self,
        tenant_id: str,
        case_id: str,
        *,
        status: str | None = None,
        note: str | None = None,
        assignee: str | None = None,
        tenant_slug: str | None = None,
    ) -> ReviewCase | None:
        record = self.moderation_repository.update_review_case(
            tenant_id,
            case_id,
            status=status,
            note=note,
            assignee=assignee,
        )
        if not record:
            return None
        return ReviewCase(
            case_id=record.id,
            request_id=record.request_id,
            tenant_id=tenant_slug or tenant_id,
            submitted_text=record.submitted_text,
            action=record.action,
            priority=record.priority,
            status=record.status,
            assignee=record.assignee,
            category_scores=[CategoryResult(**entry) for entry in record.category_scores],
            notes=record.notes,
            created_at=record.created_at,
        )
