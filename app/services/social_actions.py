from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.models import ConnectedAccountRecord, SocialEventRecord
from app.settings import Settings


@dataclass(frozen=True)
class PlatformActionResult:
    status: str
    payload: dict[str, Any]


class SocialActionExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def execute(
        self,
        *,
        event: SocialEventRecord,
        account: ConnectedAccountRecord | None,
        action_type: str,
    ) -> PlatformActionResult:
        if action_type in {"mark-reviewed", "block-user"}:
            return PlatformActionResult(status="recorded", payload={"platform_call": "not_required"})

        if event.platform not in {"instagram", "facebook"}:
            return PlatformActionResult(status="recorded", payload={"platform_call": "unsupported_platform"})

        token = self._access_token(account)
        if not token:
            return PlatformActionResult(status="recorded", payload={"platform_call": "missing_access_token"})

        if not event.external_event_id:
            return PlatformActionResult(status="failed", payload={"platform_call": "missing_external_event_id"})

        try:
            async with httpx.AsyncClient(timeout=self.settings.meta_action_timeout_seconds) as client:
                response = await self._send_meta_action(
                    client,
                    platform=event.platform,
                    external_event_id=event.external_event_id,
                    action_type=action_type,
                    access_token=token,
                )
            payload: dict[str, Any] = {
                "platform_call": "meta_graph_api",
                "http_status": response.status_code,
                "response": self._response_payload(response),
            }
            if response.is_success:
                return PlatformActionResult(status="completed", payload=payload)
            return PlatformActionResult(status="failed", payload=payload)
        except Exception as exc:
            return PlatformActionResult(status="failed", payload={"platform_call": "meta_graph_api", "error": str(exc)})

    async def _send_meta_action(
        self,
        client: httpx.AsyncClient,
        *,
        platform: str,
        external_event_id: str,
        action_type: str,
        access_token: str,
    ) -> httpx.Response:
        url = f"{self.settings.meta_graph_api_base_url.rstrip('/')}/{external_event_id}"
        if action_type == "delete":
            return await client.delete(url, params={"access_token": access_token})

        if action_type in {"hide", "allow"}:
            hidden_value = action_type == "hide"
            field_name = "hide" if platform == "instagram" else "is_hidden"
            return await client.post(url, data={field_name: str(hidden_value).lower(), "access_token": access_token})

        raise ValueError(f"Unsupported platform action: {action_type}")

    @staticmethod
    def _access_token(account: ConnectedAccountRecord | None) -> str | None:
        if not account:
            return None
        metadata = account.metadata_json or {}
        token = metadata.get("access_token") or metadata.get("page_access_token")
        return str(token) if token else None

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any] | str:
        try:
            parsed = response.json()
        except Exception:
            return response.text[:500]
        return parsed if isinstance(parsed, dict) else {"data": parsed}
