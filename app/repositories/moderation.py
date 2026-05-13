from __future__ import annotations

from datetime import datetime

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models import AuditEventRecord, ModerationRequestRecord, ModerationResultRecord, ReviewCaseRecord


class ModerationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_request(
        self,
        tenant_id: str,
        modality: str,
        content_text: str,
        content_metadata: dict,
    ) -> ModerationRequestRecord:
        record = ModerationRequestRecord(
            tenant_id=tenant_id,
            modality=modality,
            content_text=content_text,
            content_metadata=content_metadata,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def create_result(
        self,
        request_id: str,
        tenant_id: str,
        action: str,
        category_scores: list,
        matched_policy_labels: list[str],
        explanation: str,
        metadata_json: dict,
    ) -> ModerationResultRecord:
        record = ModerationResultRecord(
            request_id=request_id,
            tenant_id=tenant_id,
            action=action,
            category_scores=category_scores,
            matched_policy_labels=matched_policy_labels,
            explanation=explanation,
            metadata_json=metadata_json,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def create_review_case(
        self,
        request_id: str,
        tenant_id: str,
        action: str,
        priority: int,
        submitted_text: str,
        category_scores: list,
        notes: list[str],
    ) -> ReviewCaseRecord:
        record = ReviewCaseRecord(
            request_id=request_id,
            tenant_id=tenant_id,
            action=action,
            priority=priority,
            submitted_text=submitted_text,
            category_scores=category_scores,
            notes=notes,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def create_audit_event(
        self,
        tenant_id: str,
        event_type: str,
        payload: dict,
        request_id: str | None = None,
        latency_ms: float | None = None,
        actor_type: str = "system",
    ) -> AuditEventRecord:
        record = AuditEventRecord(
            tenant_id=tenant_id,
            request_id=request_id,
            event_type=event_type,
            payload=payload,
            latency_ms=latency_ms,
            actor_type=actor_type,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def list_review_cases(self, tenant_id: str) -> list[ReviewCaseRecord]:
        active_status_order = case(
            (ReviewCaseRecord.status == "open", 0),
            (ReviewCaseRecord.status == "in_review", 1),
            (ReviewCaseRecord.status == "resolved", 2),
            (ReviewCaseRecord.status == "dismissed", 3),
            else_=4,
        )
        return (
            self.db.query(ReviewCaseRecord)
            .filter(ReviewCaseRecord.tenant_id == tenant_id)
            .order_by(active_status_order, ReviewCaseRecord.priority.desc(), ReviewCaseRecord.created_at.desc())
            .all()
        )

    def get_review_case(self, tenant_id: str, case_id: str) -> ReviewCaseRecord | None:
        return (
            self.db.query(ReviewCaseRecord)
            .filter(ReviewCaseRecord.tenant_id == tenant_id, ReviewCaseRecord.id == case_id)
            .one_or_none()
        )

    def update_review_case(
        self,
        tenant_id: str,
        case_id: str,
        *,
        status: str | None = None,
        note: str | None = None,
        assignee: str | None = None,
    ) -> ReviewCaseRecord | None:
        record = self.get_review_case(tenant_id, case_id)
        if not record:
            return None

        if status is not None:
            record.status = status
        if assignee is not None:
            record.assignee = assignee.strip() or None
        if note and note.strip():
            record.notes = [*list(record.notes or []), note.strip()]

        self.db.add(record)
        self.db.flush()
        return record

    def list_recent_decisions(
        self, tenant_id: str, limit: int = 20
    ) -> list[tuple[ModerationRequestRecord, ModerationResultRecord]]:
        return (
            self.db.query(ModerationRequestRecord, ModerationResultRecord)
            .join(ModerationResultRecord, ModerationResultRecord.request_id == ModerationRequestRecord.id)
            .filter(ModerationRequestRecord.tenant_id == tenant_id)
            .order_by(ModerationRequestRecord.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_audit_events(self, tenant_id: str, event_type: str | None = None) -> list[AuditEventRecord]:
        query = self.db.query(AuditEventRecord).filter(AuditEventRecord.tenant_id == tenant_id)
        if event_type:
            query = query.filter(AuditEventRecord.event_type == event_type)
        return query.order_by(AuditEventRecord.created_at.desc()).all()

    def list_decisions_between(
        self,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> list[ModerationResultRecord]:
        return (
            self.db.query(ModerationResultRecord)
            .join(ModerationRequestRecord, ModerationResultRecord.request_id == ModerationRequestRecord.id)
            .filter(
                ModerationRequestRecord.tenant_id == tenant_id,
                ModerationRequestRecord.created_at >= start,
                ModerationRequestRecord.created_at < end,
            )
            .all()
        )

    def list_decisions_between_tenants(
        self,
        tenant_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> list[ModerationResultRecord]:
        if not tenant_ids:
            return []
        return (
            self.db.query(ModerationResultRecord)
            .join(ModerationRequestRecord, ModerationResultRecord.request_id == ModerationRequestRecord.id)
            .filter(
                ModerationRequestRecord.tenant_id.in_(tenant_ids),
                ModerationRequestRecord.created_at >= start,
                ModerationRequestRecord.created_at < end,
            )
            .all()
        )
