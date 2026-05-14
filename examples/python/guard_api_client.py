from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

import requests


class GuardApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("GUARD_API_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("GUARD_API_KEY") or ""
        self.timeout = timeout
        if not self.base_url:
            raise ValueError("GUARD_API_URL is required.")
        if not self.api_key:
            raise ValueError("GUARD_API_KEY is required.")

    def moderate_text(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._post_json("/moderate/text", {"text": text, "metadata": metadata or {}})

    def moderate_image(
        self,
        file_path: str | Path,
        *,
        image_caption: str = "",
        detected_objects: list[str] | None = None,
        ocr_text: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields = {
            "image_caption": image_caption,
            "detected_objects": ",".join(detected_objects or []),
            "ocr_text": ocr_text,
            **self._metadata_fields(metadata or {}),
        }
        return self._post_file("/moderate/image", "image", file_path, fields)

    def moderate_audio(
        self,
        file_path: str | Path,
        *,
        transcript_hint: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields = {
            "transcript_hint": transcript_hint,
            **self._metadata_fields(metadata or {}),
        }
        return self._post_file("/moderate/audio", "audio", file_path, fields)

    def moderate_video(
        self,
        file_path: str | Path,
        *,
        transcript_hint: str = "",
        frames: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json

        fields = {
            "transcript_hint": transcript_hint,
            "frames": json.dumps(frames or []),
            **self._metadata_fields(metadata or {}),
        }
        return self._post_file("/moderate/video", "video", file_path, fields)

    def _post_json(self, route: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}{route}",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
            json=payload,
            timeout=self.timeout,
        )
        return self._response_json(response)

    def _post_file(
        self,
        route: str,
        field_name: str,
        file_path: str | Path,
        fields: dict[str, str],
    ) -> dict[str, Any]:
        path = Path(file_path)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            response = requests.post(
                f"{self.base_url}{route}",
                headers={"X-API-Key": self.api_key},
                files={field_name: (path.name, handle, content_type)},
                data=fields,
                timeout=self.timeout,
            )
        return self._response_json(response)

    @staticmethod
    def _metadata_fields(metadata: dict[str, Any]) -> dict[str, str]:
        allowed = {"content_id", "user_id", "language", "channel", "region"}
        return {key: str(value) for key, value in metadata.items() if key in allowed and value is not None}

    @staticmethod
    def _response_json(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not response.ok:
            raise RuntimeError(payload.get("detail") or f"Guard API returned {response.status_code}")
        return payload


def decision_action(moderation: dict[str, Any]) -> str:
    return moderation.get("decision", {}).get("action", "review")


def should_publish(moderation: dict[str, Any]) -> bool:
    return decision_action(moderation) == "allow"


def should_hold_for_review(moderation: dict[str, Any]) -> bool:
    return decision_action(moderation) == "review"


def should_block(moderation: dict[str, Any]) -> bool:
    return decision_action(moderation) == "block"

