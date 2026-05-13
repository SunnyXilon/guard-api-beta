from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.repositories.social import SocialRepository
from app.schemas import ConnectedAccount
from app.services.social_service import SocialService
from app.settings import Settings


@dataclass
class MetaOAuthConnectResult:
    accounts: list[ConnectedAccount]


class MetaOAuthService:
    def __init__(self, settings: Settings, social_repository: SocialRepository) -> None:
        self.settings = settings
        self.social_repository = social_repository

    def authorization_url(self, state: str) -> str:
        self._require_configured()
        query = urlencode(
            {
                "client_id": self.settings.meta_app_id,
                "redirect_uri": self.settings.meta_oauth_redirect_uri,
                "state": state,
                "scope": ",".join(self.settings.meta_oauth_scopes),
                "response_type": "code",
            }
        )
        return f"{self.settings.meta_oauth_dialog_base_url}?{query}"

    async def connect_from_code(self, tenant_id: str, tenant_slug: str, code: str) -> MetaOAuthConnectResult:
        self._require_configured()
        async with httpx.AsyncClient(timeout=self.settings.meta_action_timeout_seconds) as client:
            user_token = await self._exchange_code(client, code)
            token_for_pages = await self._exchange_long_lived_token(client, user_token) or user_token
            user = await self._fetch_user(client, token_for_pages)
            pages = await self._fetch_pages(client, token_for_pages)

        if not pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Meta login succeeded, but no manageable Facebook Pages were returned.",
            )

        accounts: list[ConnectedAccount] = []
        for page in pages:
            page_id = str(page.get("id") or "").strip()
            page_name = str(page.get("name") or "Facebook Page").strip()
            page_token = str(page.get("access_token") or token_for_pages).strip()
            instagram_account = page.get("instagram_business_account") if isinstance(page, dict) else None
            if isinstance(instagram_account, dict) and instagram_account.get("id"):
                accounts.append(
                    self._save_account(
                        tenant_id=tenant_id,
                        tenant_slug=tenant_slug,
                        platform="instagram",
                        provider_account_id=str(instagram_account["id"]),
                        display_name=str(instagram_account.get("username") or page_name),
                        account_type="creator",
                        scopes=self.settings.meta_oauth_scopes,
                        metadata={
                            "auth_status": "authenticated",
                            "source": "meta_oauth",
                            "meta_user_id": user.get("id"),
                            "meta_user_name": user.get("name"),
                            "facebook_page_id": page_id,
                            "facebook_page_name": page_name,
                            "page_access_token": page_token,
                            "profile_picture_url": instagram_account.get("profile_picture_url"),
                        },
                    )
                )
            else:
                accounts.append(
                    self._save_account(
                        tenant_id=tenant_id,
                        tenant_slug=tenant_slug,
                        platform="facebook",
                        provider_account_id=page_id,
                        display_name=page_name,
                        account_type="page",
                        scopes=self.settings.meta_oauth_scopes,
                        metadata={
                            "auth_status": "authenticated",
                            "source": "meta_oauth",
                            "meta_user_id": user.get("id"),
                            "meta_user_name": user.get("name"),
                            "facebook_page_id": page_id,
                            "facebook_page_name": page_name,
                            "page_access_token": page_token,
                        },
                    )
                )

        return MetaOAuthConnectResult(accounts=accounts)

    async def _exchange_code(self, client: httpx.AsyncClient, code: str) -> str:
        response = await client.get(
            f"{self.settings.meta_graph_api_base_url}/oauth/access_token",
            params={
                "client_id": self.settings.meta_app_id,
                "client_secret": self.settings.meta_app_secret,
                "redirect_uri": self.settings.meta_oauth_redirect_uri,
                "code": code,
            },
        )
        payload = self._json_or_raise(response, "Meta OAuth code exchange failed.")
        token = payload.get("access_token")
        if not token:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Meta did not return an access token.")
        return str(token)

    async def _exchange_long_lived_token(self, client: httpx.AsyncClient, access_token: str) -> str | None:
        response = await client.get(
            f"{self.settings.meta_graph_api_base_url}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.settings.meta_app_id,
                "client_secret": self.settings.meta_app_secret,
                "fb_exchange_token": access_token,
            },
        )
        if response.status_code >= 400:
            return None
        payload = response.json()
        token = payload.get("access_token")
        return str(token) if token else None

    async def _fetch_user(self, client: httpx.AsyncClient, access_token: str) -> dict:
        response = await client.get(
            f"{self.settings.meta_graph_api_base_url}/me",
            params={"fields": "id,name", "access_token": access_token},
        )
        return self._json_or_raise(response, "Could not fetch Meta user profile.")

    async def _fetch_pages(self, client: httpx.AsyncClient, access_token: str) -> list[dict]:
        response = await client.get(
            f"{self.settings.meta_graph_api_base_url}/me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username,profile_picture_url}",
                "access_token": access_token,
            },
        )
        payload = self._json_or_raise(response, "Could not fetch connected Meta Pages.")
        data = payload.get("data") or []
        return data if isinstance(data, list) else []

    def _save_account(
        self,
        *,
        tenant_id: str,
        tenant_slug: str,
        platform: str,
        provider_account_id: str,
        display_name: str,
        account_type: str,
        scopes: list[str],
        metadata: dict,
    ) -> ConnectedAccount:
        record = self.social_repository.upsert_connected_account(
            tenant_id=tenant_id,
            platform=platform,
            provider_account_id=provider_account_id,
            display_name=display_name,
            account_type=account_type,
            status="connected",
            scopes=scopes,
            metadata=metadata,
        )
        return SocialService._connected_account_from_record(record, tenant_slug)

    def _require_configured(self) -> None:
        if not (self.settings.meta_app_id and self.settings.meta_app_secret and self.settings.meta_oauth_redirect_uri):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Meta OAuth is not configured. Set RTCM_META_APP_ID, RTCM_META_APP_SECRET, and RTCM_META_OAUTH_REDIRECT_URI.",
            )

    @staticmethod
    def _json_or_raise(response: httpx.Response, detail: str) -> dict:
        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
