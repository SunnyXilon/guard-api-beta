from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.inference_client import InferenceClient
from app.main import create_app
from app.settings import Settings

os.environ.setdefault("RTCM_ENABLE_HF_MODEL", "false")

from inference_service.main import app as inference_app


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    settings = Settings(
        database_url=f"sqlite:///{db_path}",
        bootstrap_default_keys=(
            "default:rtcm_default_live_key,"
            "kids-safe:rtcm_kids_live_key,"
            "marketplace:rtcm_market_live_key"
        ),
        stripe_secret_key="",
        stripe_webhook_secret="",
        billing_plan_price_ids={},
        local_vision_warmup_enabled=False,
    )
    app = create_app(settings)

    with TestClient(app) as test_client:
        transport = httpx.ASGITransport(app=inference_app)
        test_client.app.state.inference_client = InferenceClient(
            base_url="http://inference.test",
            timeout_seconds=2.0,
            transport=transport,
        )
        yield test_client
