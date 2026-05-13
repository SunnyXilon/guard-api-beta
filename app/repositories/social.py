from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models import ConnectedAccountRecord, SocialActionRecord, SocialEventRecord


class SocialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_connected_accounts(self, tenant_id: str) -> list[ConnectedAccountRecord]:
        return (
            self.db.query(ConnectedAccountRecord)
            .filter(ConnectedAccountRecord.tenant_id == tenant_id, ConnectedAccountRecord.status != "deleted")
            .order_by(ConnectedAccountRecord.created_at.desc())
            .all()
        )

    def get_connected_account(self, tenant_id: str, account_id: str) -> ConnectedAccountRecord | None:
        return (
            self.db.query(ConnectedAccountRecord)
            .filter(ConnectedAccountRecord.tenant_id == tenant_id, ConnectedAccountRecord.id == account_id)
            .one_or_none()
        )

    def upsert_connected_account(
        self,
        *,
        tenant_id: str,
        platform: str,
        provider_account_id: str,
        display_name: str,
        account_type: str,
        status: str,
        scopes: list[str],
        metadata: dict,
    ) -> ConnectedAccountRecord:
        record = (
            self.db.query(ConnectedAccountRecord)
            .filter(
                ConnectedAccountRecord.tenant_id == tenant_id,
                ConnectedAccountRecord.platform == platform,
                ConnectedAccountRecord.provider_account_id == provider_account_id,
            )
            .one_or_none()
        )
        if record is None:
            record = ConnectedAccountRecord(
                tenant_id=tenant_id,
                platform=platform,
                provider_account_id=provider_account_id,
                display_name=display_name,
                account_type=account_type,
                status=status,
                scopes=scopes,
                metadata_json=metadata,
            )
        else:
            record.display_name = display_name
            record.account_type = account_type
            record.scopes = scopes
            record.metadata_json = metadata
            record.status = status
            record.updated_at = datetime.now(timezone.utc)

        self.db.add(record)
        self.db.flush()
        return record

    def disconnect_connected_account(
        self,
        tenant_id: str,
        account_id: str,
        *,
        metadata: dict,
    ) -> ConnectedAccountRecord | None:
        record = self.get_connected_account(tenant_id, account_id)
        if record is None:
            return None

        record.status = "disconnected"
        record.metadata_json = metadata
        record.updated_at = datetime.now(timezone.utc)
        self.db.add(record)
        self.db.flush()
        return record

    def remove_connected_account(
        self,
        tenant_id: str,
        account_id: str,
        *,
        metadata: dict,
    ) -> ConnectedAccountRecord | None:
        record = self.get_connected_account(tenant_id, account_id)
        if record is None:
            return None

        record.provider_account_id = f"deleted:{record.id}"
        record.display_name = "Deleted social account"
        record.status = "deleted"
        record.scopes = []
        record.metadata_json = metadata
        record.updated_at = datetime.now(timezone.utc)
        self.db.add(record)
        self.db.flush()
        return record

    def create_social_event(
        self,
        *,
        tenant_id: str,
        connected_account_id: str | None,
        moderation_request_id: str | None,
        platform: str,
        external_event_id: str | None,
        source_type: str,
        actor_handle: str | None,
        content_text: str,
        content_url: str | None,
        media_urls: list[str],
        decision_action: str,
        triggered_categories: list[str],
        status: str,
        raw_payload: dict,
    ) -> SocialEventRecord:
        record = SocialEventRecord(
            tenant_id=tenant_id,
            connected_account_id=connected_account_id,
            moderation_request_id=moderation_request_id,
            platform=platform,
            external_event_id=external_event_id,
            source_type=source_type,
            actor_handle=actor_handle,
            content_text=content_text,
            content_url=content_url,
            media_urls=media_urls,
            decision_action=decision_action,
            triggered_categories=triggered_categories,
            status=status,
            raw_payload=raw_payload,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def list_social_events(self, tenant_id: str, status: str | None = None) -> list[SocialEventRecord]:
        status_order = case(
            (SocialEventRecord.status == "open", 0),
            (SocialEventRecord.status == "in_review", 1),
            (SocialEventRecord.status == "reviewed", 2),
            (SocialEventRecord.status == "hidden", 3),
            (SocialEventRecord.status == "deleted", 4),
            (SocialEventRecord.status == "allowed", 5),
            (SocialEventRecord.status == "blocked_user", 6),
            else_=7,
        )
        query = self.db.query(SocialEventRecord).filter(SocialEventRecord.tenant_id == tenant_id)
        if status:
            query = query.filter(SocialEventRecord.status == status)
        return query.order_by(status_order, SocialEventRecord.created_at.desc()).limit(200).all()

    def get_social_event(self, tenant_id: str, event_id: str) -> SocialEventRecord | None:
        return (
            self.db.query(SocialEventRecord)
            .filter(SocialEventRecord.tenant_id == tenant_id, SocialEventRecord.id == event_id)
            .one_or_none()
        )

    def create_social_action(
        self,
        *,
        tenant_id: str,
        social_event_id: str,
        action_type: str,
        status: str,
        actor_type: str,
        payload: dict,
        external_action_id: str | None = None,
    ) -> SocialActionRecord:
        record = SocialActionRecord(
            tenant_id=tenant_id,
            social_event_id=social_event_id,
            action_type=action_type,
            status=status,
            actor_type=actor_type,
            external_action_id=external_action_id,
            payload=payload,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def record_social_action(
        self,
        tenant_id: str,
        event_id: str,
        *,
        action_type: str,
        next_status: str | None,
        payload: dict,
        status: str = "completed",
        actor_type: str = "tenant_admin",
    ) -> tuple[SocialEventRecord, SocialActionRecord] | None:
        event = self.get_social_event(tenant_id, event_id)
        if event is None:
            return None

        if next_status is not None:
            event.status = next_status
            event.last_action_at = datetime.now(timezone.utc)
        self.db.add(event)
        action = self.create_social_action(
            tenant_id=tenant_id,
            social_event_id=event_id,
            action_type=action_type,
            status=status,
            actor_type=actor_type,
            payload=payload,
        )
        self.db.flush()
        return event, action
