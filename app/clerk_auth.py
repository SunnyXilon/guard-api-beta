from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from time import time

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Header, HTTPException, Request, status

from app.settings import Settings

_JWKS_CACHE: dict[str, tuple[float, dict]] = {}


@dataclass(frozen=True)
class ClerkPrincipal:
    user_id: str
    org_id: str | None = None


def require_clerk_principal(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_clerk_user_id: str | None = Header(default=None, alias="X-Clerk-User-Id"),
    x_clerk_org_id: str | None = Header(default=None, alias="X-Clerk-Org-Id"),
) -> ClerkPrincipal:
    settings: Settings = request.app.state.settings
    if settings.environment != "production" and x_clerk_user_id:
        return ClerkPrincipal(user_id=x_clerk_user_id, org_id=x_clerk_org_id)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Clerk bearer token.")

    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_clerk_token(token, settings)
    user_id = str(payload.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clerk token is missing subject.")
    org_id = payload.get("org_id")
    return ClerkPrincipal(user_id=user_id, org_id=str(org_id) if org_id else None)


def verify_clerk_token(token: str, settings: Settings) -> dict:
    try:
        header_segment, payload_segment, signature_segment = token.split(".", 2)
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Clerk token.") from exc

    if header.get("alg") != "RS256":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported Clerk token algorithm.")

    now = int(time())
    if int(payload.get("exp", 0)) < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clerk token expired.")
    if int(payload.get("nbf", 0)) > now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clerk token is not active yet.")
    if settings.clerk_issuer and payload.get("iss") != settings.clerk_issuer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Clerk token issuer.")
    if settings.clerk_authorized_parties:
        authorized_party = payload.get("azp")
        if authorized_party not in settings.clerk_authorized_parties:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Clerk authorized party.")

    public_key = _public_key_for_header(header, settings)
    signed_data = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = _b64url_decode(signature_segment)
    try:
        public_key.verify(signature, signed_data, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Clerk token signature.") from exc
    return payload


def _public_key_for_header(header: dict, settings: Settings):
    if settings.clerk_jwt_key:
        return serialization.load_pem_public_key(settings.clerk_jwt_key.encode("utf-8"))

    if not settings.clerk_jwks_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Clerk JWT verification is not configured.")

    key_id = header.get("kid")
    jwks = _get_jwks(settings)

    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == key_id:
            return _rsa_key_from_jwk(jwk)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown Clerk signing key.")


def _get_jwks(settings: Settings) -> dict:
    cached = _JWKS_CACHE.get(settings.clerk_jwks_url)
    now = time()
    if cached and cached[0] > now:
        return cached[1]

    try:
        response = httpx.get(settings.clerk_jwks_url, timeout=5.0)
        response.raise_for_status()
        jwks = response.json()
    except Exception as exc:
        if cached:
            return cached[1]
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to load Clerk JWKS.") from exc

    _JWKS_CACHE[settings.clerk_jwks_url] = (now + settings.clerk_jwks_cache_ttl_seconds, jwks)
    return jwks


def _rsa_key_from_jwk(jwk: dict):
    modulus = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    exponent = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(exponent, modulus).public_key()


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
