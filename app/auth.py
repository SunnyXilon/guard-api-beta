from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Header, HTTPException, Request, status
from app.repositories.tenants import TenantRepository
from app.schemas import AuthenticatedTenant
from app.security import verify_session_token


def require_authenticated_tenant(*required_scopes: str):
    def dependency(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> AuthenticatedTenant:
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
            payload = verify_session_token(token, request.app.state.settings.session_secret)
            if not payload:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.")

            scopes = payload.get("scopes") or []
            if required_scopes and not set(required_scopes).issubset(set(scopes)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session token does not have the required scope.",
                )

            db = request.app.state.session_factory()
            try:
                tenant_repo = TenantRepository(db)
                tenant = tenant_repo.get_tenant_by_slug(str(payload.get("tenant_id", "")))
                if not tenant or not tenant.is_active:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session tenant.")
                return AuthenticatedTenant(
                    tenant_id=tenant.slug,
                    tenant_name=tenant.name,
                    api_key_id=str(payload.get("api_key_id", "")),
                    scopes=scopes,
                )
            finally:
                db.close()

        if not x_api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key.")

        db = request.app.state.session_factory()
        try:
            tenant_repo = TenantRepository(db)
            api_key = tenant_repo.get_api_key(x_api_key)
            if not api_key or not api_key.tenant or not api_key.tenant.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

            scopes = api_key.scopes or []
            if required_scopes and not set(required_scopes).issubset(set(scopes)):
                if "dashboard" in required_scopes and "moderation" in scopes and "dashboard" not in scopes:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "This is a moderation API key. Use it for content moderation requests, "
                            "not dashboard login. Sign in and create/open your workspace to manage dashboard access."
                        ),
                    )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key does not have the required scope.",
                )

            api_key.last_used_at = datetime.now(timezone.utc)
            db.add(api_key)
            db.commit()

            return AuthenticatedTenant(
                tenant_id=api_key.tenant.slug,
                tenant_name=api_key.tenant.name,
                api_key_id=api_key.id,
                scopes=scopes,
            )
        finally:
            db.close()

    return dependency


get_authenticated_tenant = require_authenticated_tenant()
get_moderation_tenant = require_authenticated_tenant("moderation")
get_dashboard_tenant = require_authenticated_tenant("dashboard")
get_policy_admin_tenant = require_authenticated_tenant("dashboard", "policy:write")
