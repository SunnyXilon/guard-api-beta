import pytest

from app.settings import Settings


def test_production_settings_reject_unsafe_defaults() -> None:
    settings = Settings(environment="production")

    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        settings.validate_production_safety()


def test_production_settings_accept_required_launch_config(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/run/secrets/google-vision.json")
    settings = Settings(
        environment="production",
        session_secret="prod-secret-that-is-long-and-random",
        database_url="postgresql+psycopg://guard:secret@db:5432/guard",
        cors_allowed_origins=["https://app.guard.example"],
        bootstrap_api_keys=False,
        bootstrap_default_keys="",
        bootstrap_admin_keys="",
        self_service_onboarding_enabled=True,
        clerk_jwks_url="https://clerk.example/.well-known/jwks.json",
        clerk_issuer="https://clerk.example",
        clerk_authorized_parties=["https://app.guard.example"],
        rate_limit_redis_url="redis://redis:6379/0",
        image_scanning_required=True,
        billing_required=True,
        stripe_secret_key="sk_live_123",
        stripe_webhook_secret="whsec_123",
        connector_webhook_signing_secret="strong-webhook-signing-secret",
        billing_plan_price_ids={
            "starter": "price_starter",
            "growth": "price_growth",
            "scale": "price_scale",
        },
    )

    settings.validate_production_safety()


def test_production_settings_reject_missing_shared_rate_limit() -> None:
    settings = Settings(
        environment="production",
        session_secret="prod-secret-that-is-long-and-random",
        database_url="postgresql+psycopg://guard:secret@db:5432/guard",
        cors_allowed_origins=["https://app.guard.example"],
        bootstrap_api_keys=False,
        bootstrap_default_keys="",
        bootstrap_admin_keys="",
        self_service_onboarding_enabled=False,
        rate_limit_redis_url="",
    )

    with pytest.raises(RuntimeError, match="RTCM_RATE_LIMIT_REDIS_URL"):
        settings.validate_production_safety()


def test_request_id_header_is_returned(client) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req_test_123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_test_123"
