import httpx
import pytest

from app.models import ConnectedAccountRecord, SocialEventRecord
from app.services.social_actions import SocialActionExecutor
from app.settings import Settings


@pytest.mark.anyio
async def test_meta_instagram_hide_action_calls_graph_api(monkeypatch) -> None:
    calls = []

    class StubClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            calls.append((url, data))
            return httpx.Response(200, json={"success": True})

    monkeypatch.setattr(httpx, "AsyncClient", StubClient)

    executor = SocialActionExecutor(Settings(meta_graph_api_base_url="https://graph.example/v19.0"))
    result = await executor.execute(
        event=SocialEventRecord(platform="instagram", external_event_id="ig_comment_1"),
        account=ConnectedAccountRecord(metadata_json={"access_token": "token_123"}),
        action_type="hide",
    )

    assert result.status == "completed"
    assert calls == [
        (
            "https://graph.example/v19.0/ig_comment_1",
            {"hide": "true", "access_token": "token_123"},
        )
    ]


@pytest.mark.anyio
async def test_meta_facebook_allow_action_uses_is_hidden_false(monkeypatch) -> None:
    calls = []

    class StubClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            calls.append((url, data))
            return httpx.Response(200, json={"success": True})

    monkeypatch.setattr(httpx, "AsyncClient", StubClient)

    executor = SocialActionExecutor(Settings(meta_graph_api_base_url="https://graph.example/v19.0"))
    result = await executor.execute(
        event=SocialEventRecord(platform="facebook", external_event_id="fb_comment_1"),
        account=ConnectedAccountRecord(metadata_json={"page_access_token": "page_token"}),
        action_type="allow",
    )

    assert result.status == "completed"
    assert calls == [
        (
            "https://graph.example/v19.0/fb_comment_1",
            {"is_hidden": "false", "access_token": "page_token"},
        )
    ]


@pytest.mark.anyio
async def test_missing_meta_token_records_action_without_platform_call() -> None:
    result = await SocialActionExecutor(Settings()).execute(
        event=SocialEventRecord(platform="instagram", external_event_id="ig_comment_1"),
        account=ConnectedAccountRecord(metadata_json={}),
        action_type="hide",
    )

    assert result.status == "recorded"
    assert result.payload["platform_call"] == "missing_access_token"
