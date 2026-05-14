from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status


@dataclass
class AudioTranscriptionResult:
    text: str
    provider: str
    model: str
    fallback_used: bool = False
    error: str | None = None


class OpenAIAudioTranscriber:
    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "gpt-4o-mini-transcribe",
        timeout_seconds: float = 45.0,
        required: bool = False,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.required = required

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        prompt: str = "",
        language: str = "",
    ) -> AudioTranscriptionResult:
        if not self.api_key:
            if self.required:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Audio transcription is required but RTCM_OPENAI_API_KEY is not configured.",
                )
            return AudioTranscriptionResult(
                text="",
                provider="openai",
                model=self.model,
                fallback_used=True,
                error="RTCM_OPENAI_API_KEY is not configured.",
            )

        data = {
            "model": self.model,
            "response_format": "json",
        }
        if prompt.strip():
            data["prompt"] = prompt.strip()
        if language.strip() and len(language.strip()) <= 8:
            data["language"] = language.strip()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=data,
                    files={"file": (filename, audio_bytes, content_type)},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response is not None else "OpenAI transcription failed."
            if self.required:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Audio transcription failed: {detail}",
                ) from exc
            return AudioTranscriptionResult(
                text="",
                provider="openai",
                model=self.model,
                fallback_used=True,
                error=detail,
            )
        except httpx.HTTPError as exc:
            if self.required:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Audio transcription service is unreachable.",
                ) from exc
            return AudioTranscriptionResult(
                text="",
                provider="openai",
                model=self.model,
                fallback_used=True,
                error=str(exc),
            )

        payload = response.json()
        transcript = str(payload.get("text", "")).strip()
        return AudioTranscriptionResult(
            text=transcript,
            provider="openai",
            model=self.model,
            fallback_used=False,
        )
