import hashlib
import hmac
import json

import httpx


ADMIN_HEADERS = {"X-API-Key": "rtcm_market_admin_key"}


def test_connected_account_and_social_inbox_flow(client) -> None:
    account_response = client.post(
        "/connected-accounts",
        headers=ADMIN_HEADERS,
        json={
            "platform": "instagram",
            "provider_account_id": "ig_123",
            "display_name": "Creator Studio",
            "account_type": "creator",
            "scopes": ["comments"],
        },
    )

    assert account_response.status_code == 200
    account = account_response.json()
    assert account["platform"] == "instagram"
    assert account["display_name"] == "Creator Studio"
    assert account["status"] == "pending_auth"

    event_response = client.post(
        "/connectors/webhook/events",
        headers=ADMIN_HEADERS,
        json={
            "platform": "instagram",
            "connected_account_id": account["id"],
            "external_event_id": "comment_1",
            "source_type": "comment",
            "actor_handle": "bad_user",
            "content_text": "send your otp asap",
            "raw_payload": {"source": "test"},
        },
    )

    assert event_response.status_code == 200
    event = event_response.json()
    assert event["decision_action"] == "block"
    assert event["status"] == "open"
    assert "spam_scam" in event["triggered_categories"]

    inbox_response = client.get("/social-inbox", headers=ADMIN_HEADERS)
    assert inbox_response.status_code == 200
    inbox = inbox_response.json()
    assert inbox[0]["id"] == event["id"]

    action_response = client.post(
        f"/social-actions/{event['id']}/hide",
        headers=ADMIN_HEADERS,
        json={"note": "Auto-hide spam comment."},
    )

    assert action_response.status_code == 200
    action = action_response.json()
    assert action["action_type"] == "hide"
    assert action["status"] == "recorded"

    updated_inbox = client.get("/social-inbox", headers=ADMIN_HEADERS).json()
    assert updated_inbox[0]["status"] == "hidden"

    reviewed_response = client.post(
        f"/social-actions/{event['id']}/mark-reviewed",
        headers=ADMIN_HEADERS,
        json={},
    )

    assert reviewed_response.status_code == 200
    reviewed_inbox = client.get("/social-inbox", headers=ADMIN_HEADERS).json()
    assert reviewed_inbox[0]["status"] == "reviewed"


def test_connector_webhook_signature_is_enforced_when_configured(client) -> None:
    client.app.state.settings.connector_webhook_signing_secret = "test-webhook-secret"
    payload = {
        "platform": "instagram",
        "external_event_id": "signed_comment_1",
        "source_type": "comment",
        "actor_handle": "bad_user",
        "content_text": "send your otp asap",
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    missing_response = client.post(
        "/connectors/webhook/events",
        headers={**ADMIN_HEADERS, "Content-Type": "application/json"},
        content=body,
    )
    assert missing_response.status_code == 401

    signature = hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    signed_response = client.post(
        "/connectors/webhook/events",
        headers={**ADMIN_HEADERS, "Content-Type": "application/json", "X-RTCM-Signature": f"sha256={signature}"},
        content=body,
    )
    assert signed_response.status_code == 200
    assert signed_response.json()["external_event_id"] == "signed_comment_1"
    client.app.state.settings.connector_webhook_signing_secret = ""


def test_authenticated_account_metadata_is_sanitized_and_can_disconnect(client) -> None:
    account_response = client.post(
        "/connected-accounts",
        headers=ADMIN_HEADERS,
        json={
            "platform": "facebook",
            "provider_account_id": "page_123",
            "display_name": "Real Page",
            "account_type": "page",
            "scopes": ["comments"],
            "metadata": {"page_access_token": "secret_token", "business_id": "biz_1"},
        },
    )

    assert account_response.status_code == 200
    account = account_response.json()
    assert account["status"] == "connected"
    assert account["metadata"]["business_id"] == "biz_1"
    assert account["metadata"]["has_auth_credentials"] is True
    assert "page_access_token" not in account["metadata"]

    disconnect_response = client.delete(f"/connected-accounts/{account['id']}", headers=ADMIN_HEADERS)

    assert disconnect_response.status_code == 200
    disconnected = disconnect_response.json()
    assert disconnected["status"] == "disconnected"
    assert disconnected["metadata"]["auth_status"] == "disconnected"
    assert disconnected["metadata"]["has_auth_credentials"] is False
    assert "page_access_token" not in disconnected["metadata"]

    event_response = client.post(
        "/connectors/webhook/events",
        headers=ADMIN_HEADERS,
        json={
            "platform": "facebook",
            "connected_account_id": account["id"],
            "external_event_id": "comment_after_disconnect",
            "source_type": "comment",
            "actor_handle": "bad_user",
            "content_text": "send your otp asap",
        },
    )

    assert event_response.status_code == 400


def test_connected_account_can_be_deleted_from_account_list(client) -> None:
    account_response = client.post(
        "/connected-accounts",
        headers=ADMIN_HEADERS,
        json={
            "platform": "instagram",
            "provider_account_id": "ig_delete_me",
            "display_name": "Delete Me",
            "account_type": "creator",
            "scopes": ["comments"],
            "metadata": {"access_token": "secret_token"},
        },
    )
    assert account_response.status_code == 200
    account = account_response.json()
    assert account["status"] == "connected"

    delete_response = client.delete(f"/connected-accounts/{account['id']}/remove", headers=ADMIN_HEADERS)

    assert delete_response.status_code == 200
    deleted = delete_response.json()
    assert deleted["status"] == "deleted"
    assert deleted["provider_account_id"].startswith("deleted:")
    assert deleted["metadata"]["auth_status"] == "deleted"
    assert deleted["metadata"]["has_auth_credentials"] is False
    assert "access_token" not in deleted["metadata"]

    accounts = client.get("/connected-accounts", headers=ADMIN_HEADERS).json()
    assert account["id"] not in {listed_account["id"] for listed_account in accounts}

    event_response = client.post(
        "/connectors/webhook/events",
        headers=ADMIN_HEADERS,
        json={
            "platform": "instagram",
            "connected_account_id": account["id"],
            "external_event_id": "comment_after_delete",
            "source_type": "comment",
            "actor_handle": "bad_user",
            "content_text": "send your otp asap",
        },
    )

    assert event_response.status_code == 400


def test_meta_oauth_start_requires_configuration(client) -> None:
    response = client.get("/connectors/meta/oauth/start", headers=ADMIN_HEADERS)

    assert response.status_code == 400


def test_meta_oauth_callback_connects_verified_instagram_account(client, monkeypatch) -> None:
    cfg = client.app.state.settings
    cfg.meta_app_id = "meta_app_123"
    cfg.meta_app_secret = "meta_secret_123"
    cfg.meta_oauth_redirect_uri = "http://127.0.0.1:8100/connectors/meta/oauth/callback"

    class StubMetaClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params):
            if url.endswith("/oauth/access_token") and "code" in params:
                return httpx.Response(200, json={"access_token": "short_user_token"})
            if url.endswith("/oauth/access_token") and params.get("grant_type") == "fb_exchange_token":
                return httpx.Response(200, json={"access_token": "long_user_token"})
            if url.endswith("/me"):
                return httpx.Response(200, json={"id": "user_1", "name": "Meta Admin"})
            if url.endswith("/me/accounts"):
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "page_1",
                                "name": "Creator Page",
                                "access_token": "page_token",
                                "instagram_business_account": {
                                    "id": "ig_1",
                                    "username": "creator_handle",
                                    "profile_picture_url": "https://example.test/avatar.jpg",
                                },
                            }
                        ]
                    },
                )
            return httpx.Response(404, json={})

    monkeypatch.setattr("app.services.meta_oauth.httpx.AsyncClient", StubMetaClient)

    start_response = client.get(
        "/connectors/meta/oauth/start",
        headers=ADMIN_HEADERS,
        params={"return_url": "http://127.0.0.1:5174/dashboard"},
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert "facebook.com" in start_payload["authorization_url"]

    callback_response = client.get(
        "/connectors/meta/oauth/callback",
        params={"code": "oauth_code", "state": start_payload["state"]},
        follow_redirects=False,
    )

    assert callback_response.status_code == 303
    assert "meta_connect=success" in callback_response.headers["location"]

    accounts = client.get("/connected-accounts", headers=ADMIN_HEADERS).json()
    connected = [account for account in accounts if account["provider_account_id"] == "ig_1"][0]
    assert connected["platform"] == "instagram"
    assert connected["display_name"] == "creator_handle"
    assert connected["status"] == "connected"
    assert connected["metadata"]["has_auth_credentials"] is True
    assert connected["metadata"]["facebook_page_id"] == "page_1"
    assert "page_access_token" not in connected["metadata"]


def test_meta_webhook_payload_is_normalized_and_moderated(client) -> None:
    response = client.post(
        "/connectors/meta/webhook",
        headers=ADMIN_HEADERS,
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "field": "comments",
                            "value": {
                                "comment_id": "ig_comment_9",
                                "text": "go kill yourself",
                                "from": {"username": "unsafe_user"},
                                "media": {"permalink": "https://instagram.com/p/example"},
                            },
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["platform"] == "instagram"
    assert payload["external_event_id"] == "ig_comment_9"
    assert payload["actor_handle"] == "unsafe_user"
    assert payload["decision_action"] == "block"
    assert "self_harm" in payload["triggered_categories"]


def test_moderation_key_cannot_access_social_inbox(client) -> None:
    response = client.get("/social-inbox", headers={"X-API-Key": "rtcm_market_live_key"})

    assert response.status_code == 403
