from __future__ import annotations

from app.repositories.moderation import ModerationRepository


class AuditService:
    def __init__(self, moderation_repository: ModerationRepository) -> None:
        self.moderation_repository = moderation_repository

    def log_event(
        self,
        tenant_id: str,
        event_type: str,
        payload: dict,
        request_id: str | None = None,
        latency_ms: float | None = None,
        actor_type: str = "system",
    ) -> None:
        self.moderation_repository.create_audit_event(
            tenant_id=tenant_id,
            request_id=request_id,
            event_type=event_type,
            payload=payload,
            latency_ms=latency_ms,
            actor_type=actor_type,
        )
