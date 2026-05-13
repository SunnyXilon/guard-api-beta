from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_prefix="RTCM_", extra="ignore")

    app_name: str = "Guard API"
    environment: str = "development"
    session_secret: str = "dev-only-change-me"
    dashboard_session_ttl_seconds: int = 3600
    database_url: str = "sqlite:///./rtcm.db"
    inference_service_url: str = "http://127.0.0.1:8001"
    inference_timeout_seconds: float = 5.0
    image_upload_max_bytes: int = 6_000_000
    image_allowed_content_types: list[str] = ["image/jpeg", "image/png", "image/webp"]
    image_scanning_required: bool = False
    google_vision_max_labels: int = 10
    local_vision_safety_enabled: bool = True
    local_vision_model_name: str = "ViT-B-32"
    local_vision_pretrained: str = "openai"
    local_vision_device: str = "cpu"
    local_vision_threshold: float = 0.23
    local_vision_top_k: int = 5
    local_vision_batch_size: int = 4
    local_vision_warmup_enabled: bool = True
    video_upload_max_bytes: int = 60_000_000
    video_allowed_content_types: list[str] = ["video/mp4", "video/quicktime", "video/webm", "video/x-msvideo"]
    video_frame_sample_seconds: float = 4.0
    video_max_frames: int = 4
    rate_limit_enabled: bool = True
    request_rate_limit_per_minute: int = 120
    rate_limit_redis_url: str = ""
    cors_allowed_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    bootstrap_api_keys: bool = True
    bootstrap_default_keys: str = (
        "default:rtcm_default_live_key,"
        "kids-safe:rtcm_kids_live_key,"
        "marketplace:rtcm_market_live_key"
    )
    bootstrap_admin_keys: str = (
        "default:rtcm_default_admin_key,"
        "kids-safe:rtcm_kids_admin_key,"
        "marketplace:rtcm_market_admin_key"
    )
    self_service_onboarding_enabled: bool = True
    bootstrap_monthly_quota: int = 1000
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    clerk_jwks_url: str = ""
    clerk_jwt_key: str = ""
    clerk_issuer: str = ""
    clerk_authorized_parties: list[str] = []
    clerk_jwks_cache_ttl_seconds: int = 300
    billing_success_url: str = "http://127.0.0.1:5173?billing=success"
    billing_cancel_url: str = "http://127.0.0.1:5173?billing=cancelled"
    billing_trial_days: int = 30
    billing_required: bool = False
    billing_plan_price_ids: dict[str, str] = {}
    billing_plan_quotas: dict[str, int] = {
        "starter": 1000,
        "growth": 3000,
        "scale": 10000,
    }
    request_log_sampling: float = 1.0
    meta_graph_api_base_url: str = "https://graph.facebook.com/v19.0"
    meta_oauth_dialog_base_url: str = "https://www.facebook.com/v19.0/dialog/oauth"
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_oauth_redirect_uri: str = ""
    meta_oauth_state_ttl_seconds: int = 600
    meta_oauth_scopes: list[str] = [
        "public_profile",
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_metadata",
        "instagram_basic",
        "instagram_manage_comments",
    ]
    meta_action_timeout_seconds: float = 10.0
    connector_webhook_signing_secret: str = ""

    def validate_production_safety(self) -> None:
        if self.environment != "production":
            return

        problems: list[str] = []
        if self.database_url.startswith("sqlite"):
            problems.append("RTCM_DATABASE_URL must not use SQLite in production.")
        if self.bootstrap_api_keys:
            problems.append("RTCM_BOOTSTRAP_API_KEYS must be false in production.")
        if self.self_service_onboarding_enabled and not (self.clerk_jwks_url or self.clerk_jwt_key):
            problems.append(
                "RTCM_CLERK_JWKS_URL or RTCM_CLERK_JWT_KEY must be set when self-service onboarding is enabled."
            )
        if self.self_service_onboarding_enabled and not self.clerk_issuer:
            problems.append("RTCM_CLERK_ISSUER must be set when self-service onboarding is enabled.")
        if self.self_service_onboarding_enabled and not self.clerk_authorized_parties:
            problems.append("RTCM_CLERK_AUTHORIZED_PARTIES must be set when self-service onboarding is enabled.")
        if "rtcm_market_live_key" in self.bootstrap_default_keys:
            problems.append("RTCM_BOOTSTRAP_DEFAULT_KEYS still contains demo API keys.")
        if "rtcm_market_admin_key" in self.bootstrap_admin_keys:
            problems.append("RTCM_BOOTSTRAP_ADMIN_KEYS still contains demo API keys.")
        if any(origin.startswith(("http://127.0.0.1", "http://localhost")) for origin in self.cors_allowed_origins):
            problems.append("RTCM_CORS_ALLOWED_ORIGINS must be set to production origins.")
        if self.session_secret == "dev-only-change-me":
            problems.append("RTCM_SESSION_SECRET must be set to a strong random value.")
        if self.rate_limit_enabled and not self.rate_limit_redis_url:
            problems.append("RTCM_RATE_LIMIT_REDIS_URL must be set for shared production rate limiting.")
        if self.billing_required and not self.stripe_secret_key:
            problems.append("RTCM_STRIPE_SECRET_KEY must be set when RTCM_BILLING_REQUIRED is true.")
        if self.billing_required and not self.billing_plan_price_ids:
            problems.append("RTCM_BILLING_PLAN_PRICE_IDS must be set when RTCM_BILLING_REQUIRED is true.")
        if self.stripe_secret_key and not self.stripe_webhook_secret:
            problems.append("RTCM_STRIPE_WEBHOOK_SECRET must be set when Stripe billing is enabled.")
        if self.stripe_secret_key and any(
            placeholder in self.stripe_secret_key for placeholder in ("replace", "change-me")
        ):
            problems.append("RTCM_STRIPE_SECRET_KEY still contains a placeholder value.")
        if self.stripe_webhook_secret and any(
            placeholder in self.stripe_webhook_secret for placeholder in ("replace", "change-me")
        ):
            problems.append("RTCM_STRIPE_WEBHOOK_SECRET still contains a placeholder value.")
        if any("replace" in price_id or "change-me" in price_id for price_id in self.billing_plan_price_ids.values()):
            problems.append("RTCM_BILLING_PLAN_PRICE_IDS still contains placeholder price IDs.")
        if any([self.meta_app_id, self.meta_app_secret, self.meta_oauth_redirect_uri]) and not all(
            [self.meta_app_id, self.meta_app_secret, self.meta_oauth_redirect_uri]
        ):
            problems.append("RTCM_META_APP_ID, RTCM_META_APP_SECRET, and RTCM_META_OAUTH_REDIRECT_URI must be set together.")
        if self.environment == "production" and not self.connector_webhook_signing_secret:
            problems.append("RTCM_CONNECTOR_WEBHOOK_SIGNING_SECRET must be set for production connector webhooks.")
        if self.connector_webhook_signing_secret and any(
            placeholder in self.connector_webhook_signing_secret for placeholder in ("replace", "change-me")
        ):
            problems.append("RTCM_CONNECTOR_WEBHOOK_SIGNING_SECRET still contains a placeholder value.")
        if self.meta_app_id and "replace" in self.meta_app_id:
            problems.append("RTCM_META_APP_ID still contains a placeholder value.")
        if self.meta_app_secret and any(placeholder in self.meta_app_secret for placeholder in ("replace", "change-me")):
            problems.append("RTCM_META_APP_SECRET still contains a placeholder value.")
        if self.image_scanning_required and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            problems.append(
                "GOOGLE_APPLICATION_CREDENTIALS must be set when RTCM_IMAGE_SCANNING_REQUIRED is true."
            )

        if problems:
            raise RuntimeError("Unsafe production configuration: " + " ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
