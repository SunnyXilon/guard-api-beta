from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.repositories.social import SocialRepository
from app.schemas import (
    AuthenticatedTenant,
    ConnectedAccount,
    ConnectedAccountCreate,
    ContentMetadata,
    SocialAction,
    SocialEvent,
    SocialEventCreate,
    TextModerationRequest,
)
from app.services.moderation_service import ModerationService
from app.services.social_actions import SocialActionExecutor


ACTION_STATUS_MAP = {
    "hide": "hidden",
    "delete": "deleted",
    "allow": "allowed",
    "block-user": "blocked_user",
    "mark-reviewed": "reviewed",
}

AUTH_TOKEN_KEYS = {"access_token", "page_access_token", "oauth_token"}
SENSITIVE_METADATA_KEYS = AUTH_TOKEN_KEYS | {"refresh_token", "client_secret", "app_secret"}


class SocialService:
    def __init__(
        self,
        social_repository: SocialRepository,
        moderation_service: ModerationService,
        action_executor: SocialActionExecutor | None = None,
    ) -> None:
        self.social_repository = social_repository
        self.moderation_service = moderation_service
        self.action_executor = action_executor

    def list_connected_accounts(self, tenant_id: str, tenant_slug: str) -> list[ConnectedAccount]:
        return [
            self._connected_account_from_record(record, tenant_slug)
            for record in self.social_repository.list_connected_accounts(tenant_id)
        ]

    def connect_account(
        self,
        tenant_id: str,
        tenant_slug: str,
        request: ConnectedAccountCreate,
    ) -> ConnectedAccount:
        status_value = "connected" if self._has_auth_credentials(request.metadata) else "pending_auth"
        metadata = dict(request.metadata)
        metadata["auth_status"] = "authenticated" if status_value == "connected" else "pending"
        record = self.social_repository.upsert_connected_account(
            tenant_id=tenant_id,
            platform=request.platform,
            provider_account_id=request.provider_account_id,
            display_name=request.display_name,
            account_type=request.account_type,
            status=status_value,
            scopes=request.scopes,
            metadata=metadata,
        )
        return self._connected_account_from_record(record, tenant_slug)

    def disconnect_account(self, tenant_id: str, tenant_slug: str, account_id: str) -> ConnectedAccount | None:
        record = self.social_repository.get_connected_account(tenant_id, account_id)
        if record is None:
            return None

        metadata = {
            key: value
            for key, value in (record.metadata_json or {}).items()
            if key not in SENSITIVE_METADATA_KEYS
        }
        metadata["auth_status"] = "disconnected"
        metadata["disconnected_at"] = datetime.now(timezone.utc).isoformat()
        disconnected = self.social_repository.disconnect_connected_account(tenant_id, account_id, metadata=metadata)
        if disconnected is None:
            return None
        return self._connected_account_from_record(disconnected, tenant_slug)

    def remove_account(self, tenant_id: str, tenant_slug: str, account_id: str) -> ConnectedAccount | None:
        record = self.social_repository.get_connected_account(tenant_id, account_id)
        if record is None:
            return None

        metadata = {
            "auth_status": "deleted",
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "previous_platform": record.platform,
            "previous_account_type": record.account_type,
        }
        removed = self.social_repository.remove_connected_account(tenant_id, account_id, metadata=metadata)
        if removed is None:
            return None
        return self._connected_account_from_record(removed, tenant_slug)

    async def ingest_event(
        self,
        tenant_id: str,
        tenant: AuthenticatedTenant,
        request: SocialEventCreate,
    ) -> SocialEvent:
        if request.connected_account_id:
            account = self.social_repository.get_connected_account(tenant_id, request.connected_account_id)
            if not account:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connected account not found.")
            if account.status in {"disconnected", "deleted"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Connected account is {account.status}.",
                )

        metadata = request.metadata.model_copy(
            update={
                "channel": request.source_type,
                "content_id": request.external_event_id,
                "user_id": request.actor_handle,
            }
        )
        response = await self.moderation_service.moderate_text(
            TextModerationRequest(text=request.content_text, metadata=metadata),
            tenant,
        )
        event_status = "open" if response.decision.action in {"review", "block"} else "allowed"
        record = self.social_repository.create_social_event(
            tenant_id=tenant_id,
            connected_account_id=request.connected_account_id,
            moderation_request_id=response.request_id,
            platform=request.platform,
            external_event_id=request.external_event_id,
            source_type=request.source_type,
            actor_handle=request.actor_handle,
            content_text=request.content_text,
            content_url=request.content_url,
            media_urls=request.media_urls,
            decision_action=response.decision.action,
            triggered_categories=[category.value for category in response.decision.triggered_categories],
            status=event_status,
            raw_payload=request.raw_payload,
        )
        return self._social_event_from_record(record, tenant.tenant_id)

    def list_events(self, tenant_id: str, tenant_slug: str, event_status: str | None = None) -> list[SocialEvent]:
        return [
            self._social_event_from_record(record, tenant_slug)
            for record in self.social_repository.list_social_events(tenant_id, status=event_status)
        ]

    async def apply_action(
        self,
        tenant_id: str,
        tenant_slug: str,
        event_id: str,
        action_type: str,
        note: str | None = None,
    ) -> tuple[SocialEvent, SocialAction] | None:
        event_record = self.social_repository.get_social_event(tenant_id, event_id)
        if event_record is None:
            return None

        account = (
            self.social_repository.get_connected_account(tenant_id, event_record.connected_account_id)
            if event_record.connected_account_id
            else None
        )
        platform_result = (
            await self.action_executor.execute(event=event_record, account=account, action_type=action_type)
            if self.action_executor
            else None
        )
        next_status = ACTION_STATUS_MAP[action_type]
        should_update_event = platform_result is None or platform_result.status in {"completed", "recorded"}
        payload = {
            "note": (note or "").strip(),
            "platform": platform_result.payload if platform_result else {"platform_call": "not_configured"},
        }
        applied = self.social_repository.record_social_action(
            tenant_id,
            event_id,
            action_type=action_type,
            next_status=next_status if should_update_event else None,
            status=platform_result.status if platform_result else "recorded",
            payload=payload,
        )
        if applied is None:
            return None
        event, action = applied
        return self._social_event_from_record(event, tenant_slug), SocialAction(
            id=action.id,
            tenant_id=tenant_slug,
            social_event_id=action.social_event_id,
            action_type=action.action_type,
            status=action.status,
            actor_type=action.actor_type,
            external_action_id=action.external_action_id,
            payload=action.payload,
            created_at=action.created_at,
        )

    @staticmethod
    def _connected_account_from_record(record, tenant_slug: str) -> ConnectedAccount:
        metadata = SocialService._public_metadata(record.metadata_json or {})
        status_value = record.status
        if status_value == "connected" and not SocialService._has_auth_credentials(record.metadata_json or {}):
            status_value = "pending_auth"
        return ConnectedAccount(
            id=record.id,
            tenant_id=tenant_slug,
            platform=record.platform,
            provider_account_id=record.provider_account_id,
            display_name=record.display_name,
            account_type=record.account_type,
            status=status_value,
            scopes=record.scopes,
            metadata=metadata,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _has_auth_credentials(metadata: dict) -> bool:
        return any(bool(metadata.get(key)) for key in AUTH_TOKEN_KEYS)

    @staticmethod
    def _public_metadata(metadata: dict) -> dict:
        public_metadata = {
            key: value
            for key, value in metadata.items()
            if key not in SENSITIVE_METADATA_KEYS
        }
        public_metadata["has_auth_credentials"] = SocialService._has_auth_credentials(metadata)
        return public_metadata

    @staticmethod
    def _social_event_from_record(record, tenant_slug: str) -> SocialEvent:
        return SocialEvent(
            id=record.id,
            tenant_id=tenant_slug,
            connected_account_id=record.connected_account_id,
            moderation_request_id=record.moderation_request_id,
            platform=record.platform,
            external_event_id=record.external_event_id,
            source_type=record.source_type,
            actor_handle=record.actor_handle,
            content_text=record.content_text,
            content_url=record.content_url,
            media_urls=record.media_urls,
            decision_action=record.decision_action,
            triggered_categories=record.triggered_categories,
            status=record.status,
            raw_payload=record.raw_payload,
            created_at=record.created_at,
            last_action_at=record.last_action_at,
        )


def social_event_from_meta_payload(payload: dict, *, default_platform: str = "instagram") -> SocialEventCreate:
    entry = (payload.get("entry") or [{}])[0]
    change = (entry.get("changes") or [{}])[0]
    value = change.get("value") or {}
    comment_id = value.get("comment_id") or value.get("id")
    actor = value.get("from") or {}
    media = value.get("media") or {}
    return SocialEventCreate(
        platform=str(value.get("platform") or default_platform),
        external_event_id=str(comment_id) if comment_id else None,
        source_type="comment",
        actor_handle=actor.get("username") or actor.get("name"),
        content_text=value.get("text") or value.get("message") or "",
        content_url=media.get("permalink") if isinstance(media, dict) else None,
        raw_payload=payload,
        metadata=ContentMetadata(channel="comment", region="global"),
    )
