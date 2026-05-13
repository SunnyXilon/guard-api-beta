from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from time import time
from typing import Any


def generate_api_key() -> str:
    return f"rtcm_{secrets.token_urlsafe(24)}"


def api_key_prefix(raw_key: str) -> str:
    return raw_key[:12]


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_session_token(payload: dict[str, Any], secret: str, ttl_seconds: int) -> str:
    body = dict(payload)
    body["exp"] = int(time() + ttl_seconds)
    encoded = _b64url(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(encoded, secret)
    return f"{encoded}.{signature}"


def verify_session_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError:
        return None

    if not hmac.compare_digest(_sign(encoded, secret), signature):
        return None

    try:
        payload = json.loads(_b64url_decode(encoded))
    except (ValueError, json.JSONDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time()):
        return None
    return payload


def _sign(encoded_payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64url(digest)


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
