import pytest

from app.inference_client import InferenceClient
from inference_service.main import app as inference_app


@pytest.mark.anyio
async def test_inference_client_calls_service() -> None:
    import httpx

    client = InferenceClient(
        base_url="http://inference.test",
        timeout_seconds=2.0,
        transport=httpx.ASGITransport(app=inference_app),
    )
    response = await client.score_text("You are an idiot")
    assert response.model_name
    assert response.latency_ms >= 0
