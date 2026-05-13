from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import hashlib
import hmac
import json
import logging
import os
import re
from time import time
from urllib.parse import urlencode, urlparse
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_dashboard_tenant, get_moderation_tenant, get_policy_admin_tenant
from app.bootstrap import bootstrap_defaults, init_db
from app.clerk_auth import ClerkPrincipal, require_clerk_principal
from app.db import create_db_engine, create_session_factory
from app.detectors import HybridModerationEngine
from app.image_scanner import GoogleVisionImageScanner
from app.inference_client import InferenceClient
from app.repositories.moderation import ModerationRepository
from app.repositories.tenants import TenantRepository
from app.schemas import (
    AudioModerationRequest,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyInfo,
    ApiKeyUsage,
    AuthenticatedTenant,
    BillingCheckoutRequest,
    BillingCheckoutResponse,
    BillingScopeUpdate,
    BillingStatus,
    ContentMetadata,
    ConnectedAccount,
    ConnectedAccountCreate,
    DashboardSummary,
    DashboardSession,
    ImageModerationRequest,
    MetaOAuthStartResponse,
    ModerationDecisionItem,
    ReviewCase,
    ReviewCaseUpdate,
    SocialAction,
    SocialActionRequest,
    SocialEvent,
    SocialEventCreate,
    TenantPolicyConfig,
    TenantPolicyUpdate,
    TenantOnboardingRequest,
    TenantOnboardingResponse,
    TextModerationRequest,
    UsageSummary,
    VideoFrame,
    VideoModerationRequest,
    WorkspaceInfo,
    WorkspaceRenameRequest,
)
from app.services.dashboard_service import DashboardService
from app.services.audit_service import AuditService
from app.services.billing_service import BillingService
from app.services.meta_oauth import MetaOAuthService
from app.services.moderation_service import ModerationService
from app.services.policy_service import PolicyService
from app.services.review_service import ReviewService
from app.repositories.social import SocialRepository
from app.settings import Settings, get_settings
from app.services.social_actions import SocialActionExecutor
from app.services.social_service import ACTION_STATUS_MAP, SocialService, social_event_from_meta_payload
from app.security import create_session_token, verify_session_token
from app.vision_safety import LocalVisionSafetyScanner

try:
    import redis
except Exception:  # pragma: no cover
    redis = None

logger = logging.getLogger("guard_api")


async def _warm_local_vision_scanner(scanner: LocalVisionSafetyScanner) -> None:
    await asyncio.to_thread(scanner.warmup)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    cfg.validate_production_safety()
    engine = create_db_engine(cfg)
    session_factory = create_session_factory(cfg)
    rate_limit_buckets = defaultdict(deque)
    redis_rate_limiter = redis.from_url(cfg.rate_limit_redis_url) if redis is not None and cfg.rate_limit_redis_url else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        db = session_factory()
        try:
            bootstrap_defaults(db, cfg)
        finally:
            db.close()
        app.state.session_factory = session_factory
        app.state.engine = HybridModerationEngine()
        app.state.settings = cfg
        app.state.image_scanner = GoogleVisionImageScanner(
            max_labels=cfg.google_vision_max_labels,
            enabled=bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")) or cfg.image_scanning_required,
        )
        app.state.vision_safety_scanner = LocalVisionSafetyScanner(
            enabled=cfg.local_vision_safety_enabled,
            model_name=cfg.local_vision_model_name,
            pretrained=cfg.local_vision_pretrained,
            device=cfg.local_vision_device,
            threshold=cfg.local_vision_threshold,
            top_k=cfg.local_vision_top_k,
            batch_size=cfg.local_vision_batch_size,
            frame_sample_seconds=cfg.video_frame_sample_seconds,
            max_frames=cfg.video_max_frames,
        )
        if cfg.local_vision_safety_enabled and cfg.local_vision_warmup_enabled:
            asyncio.create_task(_warm_local_vision_scanner(app.state.vision_safety_scanner))
        app.state.inference_client = InferenceClient(
            base_url=cfg.inference_service_url,
            timeout_seconds=cfg.inference_timeout_seconds,
        )
        yield

    app = FastAPI(
        title=cfg.app_name,
        version="0.2.0",
        description="Cloud-ready real-time trust and safety moderation platform.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_and_safe_logging(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        start_time = time()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time() - start_time) * 1000, 2)
            logger.exception(
                "request_failed method=%s path=%s request_id=%s elapsed_ms=%s",
                request.method,
                request.url.path,
                request_id,
                elapsed_ms,
            )
            raise

        elapsed_ms = round((time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request method=%s path=%s status=%s request_id=%s elapsed_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            elapsed_ms,
        )
        return response

    @app.middleware("http")
    async def rate_limit_requests(request: Request, call_next):
        if not cfg.rate_limit_enabled or request.method == "OPTIONS" or request.url.path in {
            "/health",
            "/ready",
            "/docs",
            "/openapi.json",
            "/redoc",
        }:
            return await call_next(request)

        key = request.headers.get("X-API-Key") or (request.client.host if request.client else "unknown")
        now = time()
        if redis_rate_limiter is not None:
            redis_key = f"rtcm:rate:{key}:{int(now // 60)}"
            try:
                count = redis_rate_limiter.incr(redis_key)
                if count == 1:
                    redis_rate_limiter.expire(redis_key, 120)
                if count > cfg.request_rate_limit_per_minute:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Rate limit exceeded. Please retry later."},
                    )
                return await call_next(request)
            except Exception:
                pass

        bucket = rate_limit_buckets[key]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()

        if len(bucket) >= cfg.request_rate_limit_per_minute:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please retry later."},
            )

        bucket.append(now)
        return await call_next(request)

    def get_db(request: Request):
        db = request.app.state.session_factory()
        try:
            yield db
        finally:
            db.close()

    def get_moderation_service(request: Request, db: Session = Depends(get_db)) -> ModerationService:
        return ModerationService(
            db=db,
            engine=request.app.state.engine,
            inference_client=request.app.state.inference_client,
            image_scanner=request.app.state.image_scanner,
            vision_safety_scanner=request.app.state.vision_safety_scanner,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": cfg.environment}

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        checks: dict[str, object] = {
            "environment": cfg.environment,
            "database": "unknown",
            "inference": "unknown",
            "rate_limit": "configured" if cfg.rate_limit_redis_url else "in_memory",
            "clerk": "configured" if cfg.clerk_jwks_url or cfg.clerk_jwt_key else "not_configured",
            "billing": "configured" if cfg.stripe_secret_key and cfg.stripe_webhook_secret else "not_configured",
            "image_scanning": "configured"
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            else ("missing_credentials" if cfg.image_scanning_required else "optional"),
        }
        ready_status = True

        db = request.app.state.session_factory()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "failed"
            ready_status = False
        finally:
            db.close()

        try:
            async with httpx.AsyncClient(timeout=min(cfg.inference_timeout_seconds, 5.0)) as client:
                response = await client.get(f"{cfg.inference_service_url.rstrip('/')}/health")
                response.raise_for_status()
            checks["inference"] = "ok"
        except Exception:
            checks["inference"] = "failed"
            ready_status = False

        if redis_rate_limiter is not None:
            try:
                redis_rate_limiter.ping()
                checks["rate_limit"] = "ok"
            except Exception:
                checks["rate_limit"] = "failed"
                ready_status = False
        elif cfg.environment == "production" and cfg.rate_limit_enabled:
            checks["rate_limit"] = "missing_redis"
            ready_status = False

        if cfg.self_service_onboarding_enabled and checks["clerk"] == "not_configured":
            ready_status = False
        if cfg.billing_required and checks["billing"] == "not_configured":
            ready_status = False
        if cfg.image_scanning_required and checks["image_scanning"] != "configured":
            ready_status = False

        content = {"status": "ok" if ready_status else "not_ready", "checks": checks}
        return JSONResponse(
            status_code=status.HTTP_200_OK if ready_status else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=content,
        )

    @app.post("/moderate/text")
    async def moderate_text(
        request_body: TextModerationRequest,
        tenant: AuthenticatedTenant = Depends(get_moderation_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        return await service.moderate_text(request_body, tenant)

    @app.post("/moderate/image")
    async def moderate_image(
        request: Request,
        tenant: AuthenticatedTenant = Depends(get_moderation_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        request_body, image_bytes, filename = await _parse_image_request(
            request,
            cfg.image_upload_max_bytes,
            cfg.image_allowed_content_types,
        )
        return await service.moderate_image(request_body, tenant, image_bytes=image_bytes, filename=filename)

    @app.post("/moderate/audio")
    async def moderate_audio(
        request_body: AudioModerationRequest,
        tenant: AuthenticatedTenant = Depends(get_moderation_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        return await service.moderate_audio(request_body, tenant)

    @app.post("/moderate/video")
    async def moderate_video(
        request: Request,
        tenant: AuthenticatedTenant = Depends(get_moderation_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        request_body, video_bytes, filename = await _parse_video_request(
            request,
            cfg.video_upload_max_bytes,
            cfg.video_allowed_content_types,
        )
        return await service.moderate_video(request_body, tenant, video_bytes=video_bytes, filename=filename)

    @app.post("/playground/moderate/text")
    async def playground_moderate_text(
        request_body: TextModerationRequest,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        return await service.moderate_text(request_body, tenant)

    @app.post("/playground/moderate/image")
    async def playground_moderate_image(
        request: Request,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        request_body, image_bytes, filename = await _parse_image_request(
            request,
            cfg.image_upload_max_bytes,
            cfg.image_allowed_content_types,
        )
        return await service.moderate_image(request_body, tenant, image_bytes=image_bytes, filename=filename)

    @app.post("/playground/moderate/audio")
    async def playground_moderate_audio(
        request_body: AudioModerationRequest,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        return await service.moderate_audio(request_body, tenant)

    @app.post("/playground/moderate/video")
    async def playground_moderate_video(
        request: Request,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        service: ModerationService = Depends(get_moderation_service),
    ):
        request_body, video_bytes, filename = await _parse_video_request(
            request,
            cfg.video_upload_max_bytes,
            cfg.video_allowed_content_types,
        )
        return await service.moderate_video(request_body, tenant, video_bytes=video_bytes, filename=filename)

    @app.get("/policies/me", response_model=TenantPolicyConfig)
    async def get_current_policy(
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> TenantPolicyConfig:
        return PolicyService(TenantRepository(db)).get_policy_for_tenant(tenant.tenant_id)

    @app.put("/policies/me", response_model=TenantPolicyConfig)
    async def update_current_policy(
        request_body: TenantPolicyUpdate,
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> TenantPolicyConfig:
        tenant_repo = TenantRepository(db)
        policy = PolicyService(tenant_repo).update_policy_for_tenant(tenant.tenant_id, request_body)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if tenant_row:
            AuditService(ModerationRepository(db)).log_event(
                tenant_id=tenant_row.id,
                event_type="policy.updated",
                actor_type="tenant_admin",
                payload={
                    "tenant_slug": tenant.tenant_id,
                    "api_key_id": tenant.api_key_id,
                    "thresholds": {
                        category.value: override.model_dump(exclude_none=True)
                        for category, override in request_body.thresholds.items()
                    },
                    "review_enabled": request_body.review_enabled,
                    "protected_mode": request_body.protected_mode,
                },
            )
            db.commit()
        return policy

    @app.get("/dashboard", response_model=DashboardSummary)
    async def dashboard(
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> DashboardSummary:
        tenant_repo = TenantRepository(db)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row or not tenant_row.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        policy = PolicyService(tenant_repo).get_policy_for_tenant(tenant.tenant_id)
        usage_tenant_ids, account_quota, account_plan = tenant_repo.quota_scope_for_tenant(tenant_row)
        return DashboardService(ModerationRepository(db)).summary(
            tenant,
            tenant_row.id,
            account_quota,
            account_plan,
            policy,
            billing_scope=tenant_row.billing_scope,
            usage_tenant_ids=usage_tenant_ids,
        )

    @app.post("/dashboard/session", response_model=DashboardSession)
    async def create_dashboard_session(
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
    ) -> DashboardSession:
        access_token = create_session_token(
            {
                "tenant_id": tenant.tenant_id,
                "tenant_name": tenant.tenant_name,
                "api_key_id": tenant.api_key_id,
                "scopes": tenant.scopes,
            },
            cfg.session_secret,
            cfg.dashboard_session_ttl_seconds,
        )
        return DashboardSession(
            access_token=access_token,
            expires_in=cfg.dashboard_session_ttl_seconds,
            tenant=tenant,
        )

    @app.post("/dashboard/session/clerk", response_model=DashboardSession)
    async def create_clerk_dashboard_session(
        tenant_id: str | None = None,
        principal: ClerkPrincipal = Depends(require_clerk_principal),
        db: Session = Depends(get_db),
    ) -> DashboardSession:
        tenant_repo = TenantRepository(db)
        tenant_row = (
            tenant_repo.get_tenant_by_clerk_owner_and_slug(principal.user_id, tenant_id, principal.org_id)
            if tenant_id
            else tenant_repo.get_tenant_by_clerk_owner(principal.user_id, principal.org_id)
        )
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No workspace found for this Clerk user.")

        tenant = AuthenticatedTenant(
            tenant_id=tenant_row.slug,
            tenant_name=tenant_row.name,
            api_key_id=f"clerk:{principal.org_id or principal.user_id}",
            scopes=["dashboard", "policy:write"],
        )
        access_token = create_session_token(
            {
                "tenant_id": tenant.tenant_id,
                "tenant_name": tenant.tenant_name,
                "api_key_id": tenant.api_key_id,
                "scopes": tenant.scopes,
            },
            cfg.session_secret,
            cfg.dashboard_session_ttl_seconds,
        )
        return DashboardSession(
            access_token=access_token,
            expires_in=cfg.dashboard_session_ttl_seconds,
            tenant=tenant,
        )

    @app.get("/workspaces/clerk", response_model=list[WorkspaceInfo])
    async def list_clerk_workspaces(
        principal: ClerkPrincipal = Depends(require_clerk_principal),
        db: Session = Depends(get_db),
    ) -> list[WorkspaceInfo]:
        tenant_rows = TenantRepository(db).list_tenants_by_clerk_owner(principal.user_id, principal.org_id)
        return [
            WorkspaceInfo(
                tenant_id=tenant.slug,
                tenant_name=tenant.name,
                billing_scope=tenant.billing_scope,
                plan_name=tenant.plan_name,
                monthly_quota=tenant.monthly_quota,
                subscription_status=tenant.subscription_status,
                created_at=tenant.created_at,
            )
            for tenant in tenant_rows
        ]

    @app.patch("/workspaces/clerk/{tenant_id}", response_model=WorkspaceInfo)
    async def rename_clerk_workspace(
        tenant_id: str,
        request_body: WorkspaceRenameRequest,
        principal: ClerkPrincipal = Depends(require_clerk_principal),
        db: Session = Depends(get_db),
    ) -> WorkspaceInfo:
        tenant_repo = TenantRepository(db)
        tenant = tenant_repo.get_tenant_by_clerk_owner_and_slug(principal.user_id, tenant_id, principal.org_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for this Clerk user.")

        tenant.name = request_body.workspace_name.strip()
        db.add(tenant)
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant.id,
            event_type="tenant.renamed",
            actor_type="tenant_admin",
            payload={"tenant_slug": tenant.slug, "workspace_name": tenant.name},
        )
        db.commit()
        db.refresh(tenant)
        return WorkspaceInfo(
            tenant_id=tenant.slug,
            tenant_name=tenant.name,
            billing_scope=tenant.billing_scope,
            plan_name=tenant.plan_name,
            monthly_quota=tenant.monthly_quota,
            subscription_status=tenant.subscription_status,
            created_at=tenant.created_at,
        )

    @app.delete("/workspaces/clerk/{tenant_id}", response_model=WorkspaceInfo)
    async def delete_clerk_workspace(
        tenant_id: str,
        principal: ClerkPrincipal = Depends(require_clerk_principal),
        db: Session = Depends(get_db),
    ) -> WorkspaceInfo:
        tenant_repo = TenantRepository(db)
        tenant = tenant_repo.get_tenant_by_clerk_owner_and_slug(principal.user_id, tenant_id, principal.org_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for this Clerk user.")

        account_tenants = tenant_repo.list_tenants_by_clerk_owner(principal.user_id, principal.org_id)
        if len(account_tenants) <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Create another workspace before deleting this one.")

        if tenant.billing_scope == "account":
            remaining_tenants = [
                row for row in account_tenants if row.id != tenant.id and row.billing_scope == "account"
            ]
            quota_owner = max(
                [row for row in account_tenants if row.billing_scope == "account"],
                key=lambda row: row.monthly_quota,
            )
            for remaining in remaining_tenants:
                remaining.plan_name = quota_owner.plan_name
                remaining.monthly_quota = quota_owner.monthly_quota
                remaining.stripe_customer_id = quota_owner.stripe_customer_id or remaining.stripe_customer_id
                remaining.stripe_subscription_id = quota_owner.stripe_subscription_id or remaining.stripe_subscription_id
                remaining.subscription_status = quota_owner.subscription_status
                db.add(remaining)

        deleted_workspace = WorkspaceInfo(
            tenant_id=tenant.slug,
            tenant_name=tenant.name,
            billing_scope=tenant.billing_scope,
            plan_name=tenant.plan_name,
            monthly_quota=tenant.monthly_quota,
            subscription_status=tenant.subscription_status,
            created_at=tenant.created_at,
        )
        tenant_repo.deactivate_workspace(tenant)
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant.id,
            event_type="tenant.deleted",
            actor_type="tenant_admin",
            payload={"tenant_slug": tenant.slug, "workspace_name": tenant.name},
        )
        db.commit()
        return deleted_workspace

    @app.post("/onboarding/tenant", response_model=TenantOnboardingResponse)
    async def onboard_tenant(
        request_body: TenantOnboardingRequest,
        principal: ClerkPrincipal = Depends(require_clerk_principal),
        db: Session = Depends(get_db),
    ) -> TenantOnboardingResponse:
        if not cfg.self_service_onboarding_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self-service onboarding is disabled.")

        tenant_repo = TenantRepository(db)
        existing_account_tenants = tenant_repo.list_tenants_by_clerk_owner(principal.user_id, principal.org_id)
        account_scope_tenants = [tenant for tenant in existing_account_tenants if tenant.billing_scope == "account"]
        quota_pool = account_scope_tenants or existing_account_tenants
        quota_owner = max(quota_pool, key=lambda row: row.monthly_quota) if quota_pool else None
        slug_base = _slugify(request_body.workspace_name)
        slug = slug_base
        suffix = 2
        while tenant_repo.get_tenant_by_slug(slug):
            slug = f"{slug_base}-{suffix}"
            suffix += 1

        policy = TenantPolicyConfig(
            tenant_id=slug,
            labels=["ugc-customer", "self-service"],
        )
        tenant_row = tenant_repo.create_tenant_with_policy(
            slug=slug,
            policy=policy,
            raw_key=None,
            name=request_body.workspace_name.strip(),
            admin_key=None,
            monthly_quota=quota_owner.monthly_quota if quota_owner else cfg.bootstrap_monthly_quota,
            plan_name=quota_owner.plan_name if quota_owner else "starter",
            clerk_user_id=principal.user_id,
            clerk_org_id=principal.org_id,
        )
        if quota_owner:
            tenant_row.stripe_customer_id = quota_owner.stripe_customer_id
            tenant_row.stripe_subscription_id = quota_owner.stripe_subscription_id
            tenant_row.subscription_status = quota_owner.subscription_status
            db.add(tenant_row)
        admin_key, _raw_admin_key = tenant_repo.create_generated_api_key(
            tenant_row,
            "workspace-admin",
            ["dashboard", "policy:write"],
        )
        moderation_key, raw_moderation_key = tenant_repo.create_generated_api_key(
            tenant_row,
            "production-webhook",
            ["moderation"],
        )
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="tenant.onboarded",
            actor_type="tenant_admin",
            payload={"tenant_slug": slug, "workspace_name": request_body.workspace_name.strip()},
        )
        db.commit()
        db.refresh(admin_key)
        db.refresh(moderation_key)

        authenticated_tenant = AuthenticatedTenant(
            tenant_id=tenant_row.slug,
            tenant_name=tenant_row.name,
            api_key_id=admin_key.id,
            scopes=admin_key.scopes,
        )
        access_token = create_session_token(
            {
                "tenant_id": authenticated_tenant.tenant_id,
                "tenant_name": authenticated_tenant.tenant_name,
                "api_key_id": authenticated_tenant.api_key_id,
                "scopes": authenticated_tenant.scopes,
            },
            cfg.session_secret,
            cfg.dashboard_session_ttl_seconds,
        )

        return TenantOnboardingResponse(
            dashboard_session=DashboardSession(
                access_token=access_token,
                expires_in=cfg.dashboard_session_ttl_seconds,
                tenant=authenticated_tenant,
            ),
            moderation_key=ApiKeyCreated(
                id=moderation_key.id,
                name=moderation_key.name,
                key_prefix=moderation_key.key_prefix,
                scopes=moderation_key.scopes,
                is_active=moderation_key.is_active,
                created_at=moderation_key.created_at,
                last_used_at=moderation_key.last_used_at,
                api_key=raw_moderation_key,
            ),
        )

    @app.get("/decisions", response_model=list[ModerationDecisionItem])
    async def recent_decisions(
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
        limit: int = 20,
    ) -> list[ModerationDecisionItem]:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        return DashboardService(ModerationRepository(db)).recent_decisions(tenant_row.id, limit=min(max(limit, 1), 100))

    @app.get("/usage", response_model=UsageSummary)
    async def usage(
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> UsageSummary:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        tenant_repo = TenantRepository(db)
        usage_tenant_ids, account_quota, account_plan = tenant_repo.quota_scope_for_tenant(tenant_row)
        return DashboardService(ModerationRepository(db)).usage_this_month_for_tenants(
            usage_tenant_ids,
            account_quota,
            account_plan,
            tenant_row.billing_scope,
        )

    @app.get("/api-keys", response_model=list[ApiKeyInfo])
    async def list_api_keys(
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> list[ApiKeyInfo]:
        tenant_repo = TenantRepository(db)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        return [ApiKeyInfo.model_validate(key, from_attributes=True) for key in tenant_repo.list_api_keys(tenant_row.id)]

    @app.get("/api-keys/usage", response_model=list[ApiKeyUsage])
    async def api_key_usage(
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> list[ApiKeyUsage]:
        tenant_repo = TenantRepository(db)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

        keys = tenant_repo.list_api_keys(tenant_row.id)
        counts = {key.id: 0 for key in keys}
        for event in ModerationRepository(db).list_audit_events(tenant_row.id, event_type="moderation.completed"):
            api_key_id = (event.payload or {}).get("api_key_id")
            if api_key_id in counts:
                counts[api_key_id] += 1

        return [
            ApiKeyUsage(
                **ApiKeyInfo.model_validate(key, from_attributes=True).model_dump(),
                total_requests=counts.get(key.id, 0),
            )
            for key in keys
        ]

    @app.post("/api-keys", response_model=ApiKeyCreated)
    async def create_api_key(
        request_body: ApiKeyCreate,
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> ApiKeyCreated:
        tenant_repo = TenantRepository(db)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        api_key, raw_key = tenant_repo.create_generated_api_key(tenant_row, request_body.name, request_body.scopes)
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="api_key.created",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "api_key_id": tenant.api_key_id,
                "created_key_id": api_key.id,
                "created_key_prefix": api_key.key_prefix,
                "scopes": request_body.scopes,
            },
        )
        db.commit()
        db.refresh(api_key)
        return ApiKeyCreated(
            id=api_key.id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            scopes=api_key.scopes,
            is_active=api_key.is_active,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            api_key=raw_key,
        )

    @app.delete("/api-keys/{api_key_id}", response_model=ApiKeyInfo)
    async def deactivate_api_key(
        api_key_id: str,
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> ApiKeyInfo:
        if api_key_id == tenant.api_key_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the API key used for this request.",
            )

        tenant_repo = TenantRepository(db)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

        api_key = tenant_repo.deactivate_api_key(tenant_row.id, api_key_id)
        if not api_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")

        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="api_key.deactivated",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "api_key_id": tenant.api_key_id,
                "deactivated_key_id": api_key.id,
                "deactivated_key_prefix": api_key.key_prefix,
            },
        )
        db.commit()
        db.refresh(api_key)
        return ApiKeyInfo.model_validate(api_key, from_attributes=True)

    @app.post("/api-keys/{api_key_id}/rotate", response_model=ApiKeyCreated)
    async def rotate_api_key(
        api_key_id: str,
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> ApiKeyCreated:
        if api_key_id == tenant.api_key_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot rotate the API key used for this request.",
            )

        tenant_repo = TenantRepository(db)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

        rotated = tenant_repo.rotate_api_key(tenant_row.id, api_key_id)
        if not rotated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
        api_key, raw_key = rotated

        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="api_key.rotated",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "api_key_id": tenant.api_key_id,
                "rotated_key_id": api_key_id,
                "replacement_key_id": api_key.id,
                "replacement_key_prefix": api_key.key_prefix,
            },
        )
        db.commit()
        db.refresh(api_key)
        return ApiKeyCreated(
            id=api_key.id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            scopes=api_key.scopes,
            is_active=api_key.is_active,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            api_key=raw_key,
        )

    @app.get("/billing/status", response_model=BillingStatus)
    async def billing_status(
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> BillingStatus:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        return BillingStatus.model_validate(tenant_row, from_attributes=True)

    @app.patch("/billing/scope", response_model=BillingStatus)
    async def update_billing_scope(
        request_body: BillingScopeUpdate,
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> BillingStatus:
        tenant_repo = TenantRepository(db)
        tenant_row = tenant_repo.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row or not tenant_row.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

        tenant_repo.set_billing_scope(tenant_row, request_body.billing_scope)
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="billing.scope_updated",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "api_key_id": tenant.api_key_id,
                "billing_scope": request_body.billing_scope,
            },
        )
        db.commit()
        db.refresh(tenant_row)
        return BillingStatus.model_validate(tenant_row, from_attributes=True)

    @app.post("/billing/checkout", response_model=BillingCheckoutResponse)
    async def billing_checkout(
        request_body: BillingCheckoutRequest,
        tenant: AuthenticatedTenant = Depends(get_policy_admin_tenant),
        db: Session = Depends(get_db),
    ) -> BillingCheckoutResponse:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        checkout_url = BillingService(db, cfg).create_checkout_url(tenant_row, request_body.plan_name)
        return BillingCheckoutResponse(checkout_url=checkout_url)

    @app.post("/billing/webhook")
    async def billing_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")
        service = BillingService(db, cfg)
        event = service.construct_webhook_event(payload, signature)
        service.apply_webhook_event(event)
        return {"status": "ok"}

    @app.get("/cases")
    async def list_cases(
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> dict[str, list]:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        review_service = ReviewService(ModerationRepository(db))
        cases = review_service.list_cases(tenant_row.id, tenant_slug=tenant.tenant_id) if tenant_row else []
        return {"cases": [case.model_dump(mode="json") for case in cases]}

    @app.patch("/cases/{case_id}", response_model=ReviewCase)
    async def update_case(
        case_id: str,
        request_body: ReviewCaseUpdate,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> ReviewCase:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

        moderation_repo = ModerationRepository(db)
        case = ReviewService(moderation_repo).update_case(
            tenant_row.id,
            case_id,
            status=request_body.status,
            note=request_body.note,
            assignee=request_body.assignee,
            tenant_slug=tenant.tenant_id,
        )
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review case not found.")

        AuditService(moderation_repo).log_event(
            tenant_id=tenant_row.id,
            event_type="review_case.updated",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "api_key_id": tenant.api_key_id,
                "case_id": case_id,
                "status": request_body.status,
                "assignee": request_body.assignee,
                "note_added": bool((request_body.note or "").strip()),
            },
        )
        db.commit()
        return case

    def get_social_service(db: Session) -> SocialService:
        return SocialService(
            SocialRepository(db),
            ModerationService(
                db=db,
                engine=app.state.engine,
                inference_client=app.state.inference_client,
                image_scanner=app.state.image_scanner,
                vision_safety_scanner=app.state.vision_safety_scanner,
            ),
            action_executor=SocialActionExecutor(cfg),
        )

    @app.get("/connectors/meta/oauth/start", response_model=MetaOAuthStartResponse)
    async def start_meta_oauth(
        return_url: str | None = None,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> MetaOAuthStartResponse:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        state_payload = {
            "tenant_id": tenant.tenant_id,
            "return_url": _safe_meta_oauth_return_url(return_url, cfg),
        }
        state_token = create_session_token(state_payload, cfg.session_secret, cfg.meta_oauth_state_ttl_seconds)
        authorization_url = MetaOAuthService(cfg, SocialRepository(db)).authorization_url(state_token)
        return MetaOAuthStartResponse(authorization_url=authorization_url, state=state_token)

    @app.get("/connectors/meta/oauth/callback")
    async def meta_oauth_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
        db: Session = Depends(get_db),
    ):
        state_payload = verify_session_token(state or "", cfg.session_secret)
        if not state_payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired Meta OAuth state.")

        return_url = _safe_meta_oauth_return_url(str(state_payload.get("return_url") or ""), cfg)
        if error:
            return _meta_oauth_redirect(
                return_url,
                meta_connect="error",
                reason=error_description or error,
            )
        if not code:
            return _meta_oauth_redirect(return_url, meta_connect="error", reason="Missing Meta OAuth code.")

        tenant_slug = str(state_payload.get("tenant_id") or "")
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant_slug)
        if not tenant_row:
            return _meta_oauth_redirect(return_url, meta_connect="error", reason="Tenant not found.")

        try:
            result = await MetaOAuthService(cfg, SocialRepository(db)).connect_from_code(tenant_row.id, tenant_slug, code)
        except HTTPException as exc:
            db.rollback()
            return _meta_oauth_redirect(return_url, meta_connect="error", reason=str(exc.detail))

        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="connected_account.meta_oauth_connected",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant_slug,
                "connected_account_ids": [account.id for account in result.accounts],
                "account_count": len(result.accounts),
            },
        )
        db.commit()
        return _meta_oauth_redirect(
            return_url,
            meta_connect="success",
            account_count=str(len(result.accounts)),
        )

    @app.get("/connected-accounts", response_model=list[ConnectedAccount])
    async def list_connected_accounts(
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> list[ConnectedAccount]:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        return get_social_service(db).list_connected_accounts(tenant_row.id, tenant.tenant_id)

    @app.post("/connected-accounts", response_model=ConnectedAccount)
    async def connect_account(
        request_body: ConnectedAccountCreate,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> ConnectedAccount:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        account = get_social_service(db).connect_account(tenant_row.id, tenant.tenant_id, request_body)
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="connected_account.upserted",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "platform": account.platform,
                "connected_account_id": account.id,
            },
        )
        db.commit()
        return account

    @app.delete("/connected-accounts/{account_id}", response_model=ConnectedAccount)
    async def disconnect_account(
        account_id: str,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> ConnectedAccount:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        account = get_social_service(db).disconnect_account(tenant_row.id, tenant.tenant_id, account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connected account not found.")
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="connected_account.disconnected",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "platform": account.platform,
                "connected_account_id": account.id,
            },
        )
        db.commit()
        return account

    @app.delete("/connected-accounts/{account_id}/remove", response_model=ConnectedAccount)
    async def remove_account(
        account_id: str,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> ConnectedAccount:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        account = get_social_service(db).remove_account(tenant_row.id, tenant.tenant_id, account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connected account not found.")
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            event_type="connected_account.deleted",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "platform": account.platform,
                "connected_account_id": account.id,
            },
        )
        db.commit()
        return account

    @app.post("/connectors/webhook/events", response_model=SocialEvent)
    async def ingest_webhook_event(
        request: Request,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> SocialEvent:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        payload = await request.body()
        _verify_connector_signature(cfg, payload, request.headers.get("X-RTCM-Signature"))
        try:
            request_body = SocialEventCreate.model_validate_json(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc
        event = await get_social_service(db).ingest_event(tenant_row.id, tenant, request_body)
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            request_id=event.moderation_request_id,
            event_type="social_event.ingested",
            actor_type="connector",
            payload={
                "tenant_slug": tenant.tenant_id,
                "platform": event.platform,
                "source_type": event.source_type,
                "decision_action": event.decision_action,
                "social_event_id": event.id,
            },
        )
        db.commit()
        return event

    @app.post("/connectors/meta/webhook", response_model=SocialEvent)
    async def ingest_meta_webhook(
        request: Request,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> SocialEvent:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        raw_payload = await request.body()
        _verify_connector_signature(cfg, raw_payload, request.headers.get("X-RTCM-Signature"))
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid JSON payload.") from exc
        social_event = social_event_from_meta_payload(payload)
        event = await get_social_service(db).ingest_event(tenant_row.id, tenant, social_event)
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            request_id=event.moderation_request_id,
            event_type="social_event.meta_ingested",
            actor_type="connector",
            payload={"tenant_slug": tenant.tenant_id, "social_event_id": event.id},
        )
        db.commit()
        return event

    @app.get("/social-inbox", response_model=list[SocialEvent])
    async def social_inbox(
        event_status: str | None = None,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> list[SocialEvent]:
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        return get_social_service(db).list_events(tenant_row.id, tenant.tenant_id, event_status=event_status)

    @app.post("/social-actions/{event_id}/{action_type}", response_model=SocialAction)
    async def apply_social_action(
        event_id: str,
        action_type: str,
        request_body: SocialActionRequest | None = None,
        tenant: AuthenticatedTenant = Depends(get_dashboard_tenant),
        db: Session = Depends(get_db),
    ) -> SocialAction:
        if action_type not in ACTION_STATUS_MAP:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"action_type must be one of: {', '.join(sorted(ACTION_STATUS_MAP))}",
            )
        tenant_row = TenantRepository(db).get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        applied = await get_social_service(db).apply_action(
            tenant_row.id,
            tenant.tenant_id,
            event_id,
            action_type,
            note=request_body.note if request_body else None,
        )
        if applied is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social event not found.")
        event, action = applied
        AuditService(ModerationRepository(db)).log_event(
            tenant_id=tenant_row.id,
            request_id=event.moderation_request_id,
            event_type="social_action.applied",
            actor_type="tenant_admin",
            payload={
                "tenant_slug": tenant.tenant_id,
                "social_event_id": event.id,
                "action_type": action.action_type,
                "status": event.status,
            },
        )
        db.commit()
        return action

    return app


def _safe_meta_oauth_return_url(return_url: str | None, settings: Settings) -> str:
    fallback = "http://127.0.0.1:5173/dashboard"
    candidate = (return_url or fallback).strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return fallback

    allowed_origins = set(settings.cors_allowed_origins)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin in allowed_origins or origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:"):
        return candidate
    return fallback


def _meta_oauth_redirect(return_url: str, **query: str) -> RedirectResponse:
    separator = "&" if "?" in return_url else "?"
    return RedirectResponse(f"{return_url}{separator}{urlencode(query)}", status_code=status.HTTP_303_SEE_OTHER)


def _verify_connector_signature(settings: Settings, payload: bytes, signature: str | None) -> None:
    if not settings.connector_webhook_signing_secret:
        return

    expected = hmac.new(
        settings.connector_webhook_signing_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    provided = (signature or "").removeprefix("sha256=").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid connector webhook signature.")


async def _parse_image_request(
    request: Request,
    max_bytes: int,
    allowed_content_types: list[str],
) -> tuple[ImageModerationRequest, bytes | None, str | None]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return ImageModerationRequest(**await request.json()), None, None

    form = await request.form()
    upload = form.get("image")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Multipart image moderation requires an 'image' file field.",
        )
    if getattr(upload, "content_type", None) not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type. Allowed: {', '.join(allowed_content_types)}.",
        )

    image_bytes = await upload.read()
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image upload exceeds {max_bytes} bytes.",
        )

    detected_objects = _parse_form_list(form.get("detected_objects"))
    metadata = ContentMetadata(
        content_id=_form_str(form.get("content_id")) or None,
        user_id=_form_str(form.get("user_id")) or None,
        language=_form_str(form.get("language")) or "en",
        channel=_form_str(form.get("channel")) or "image_upload",
        region=_form_str(form.get("region")) or "global",
    )
    metadata_json = _form_str(form.get("metadata"))
    if metadata_json:
        try:
            metadata = ContentMetadata(**json.loads(metadata_json))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid metadata JSON.") from exc

    request_body = ImageModerationRequest(
        image_url=_form_str(form.get("image_url")) or None,
        image_caption=_form_str(form.get("image_caption")),
        detected_objects=detected_objects,
        ocr_text=_form_str(form.get("ocr_text")),
        metadata=metadata,
    )
    return request_body, image_bytes, getattr(upload, "filename", None)


async def _parse_video_request(
    request: Request,
    max_bytes: int,
    allowed_content_types: list[str],
) -> tuple[VideoModerationRequest, bytes | None, str | None]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return VideoModerationRequest(**await request.json()), None, None

    form = await request.form()
    upload = form.get("video")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Multipart video moderation requires a 'video' file field.",
        )
    if getattr(upload, "content_type", None) not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported video type. Allowed: {', '.join(allowed_content_types)}.",
        )

    video_bytes = await upload.read()
    if len(video_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Video upload exceeds {max_bytes} bytes.",
        )

    frames: list[VideoFrame] = []
    frames_json = _form_str(form.get("frames"))
    if frames_json:
        try:
            frames = [VideoFrame(**item) for item in json.loads(frames_json)]
        except (TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid frames JSON.") from exc
    else:
        description = _form_str(form.get("frame_description"))
        ocr_text = _form_str(form.get("ocr_text"))
        objects = _parse_form_list(form.get("detected_objects"))
        if description or ocr_text or objects:
            frames.append(
                VideoFrame(
                    timestamp_ms=0,
                    description=description,
                    ocr_text=ocr_text,
                    detected_objects=objects,
                )
            )

    metadata = ContentMetadata(
        content_id=_form_str(form.get("content_id")) or None,
        user_id=_form_str(form.get("user_id")) or None,
        language=_form_str(form.get("language")) or "en",
        channel=_form_str(form.get("channel")) or "video_upload",
        region=_form_str(form.get("region")) or "global",
    )
    metadata_json = _form_str(form.get("metadata"))
    if metadata_json:
        try:
            metadata = ContentMetadata(**json.loads(metadata_json))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid metadata JSON.") from exc

    request_body = VideoModerationRequest(
        video_url=_form_str(form.get("video_url")) or None,
        transcript_hint=_form_str(form.get("transcript_hint")),
        frames=frames,
        metadata=metadata,
    )
    return request_body, video_bytes, getattr(upload, "filename", None)


def _form_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _parse_form_list(value: object) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "workspace"


app = create_app()
