from __future__ import annotations

from time import perf_counter

import httpx

from shared.inference_schemas import InferenceRequest, InferenceResponse


class InferenceClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0, transport: httpx.BaseTransport | None = None) -> None:
        if "://" not in base_url:
            base_url = f"http://{base_url}"
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def score_text(self, text: str, language: str = "en") -> InferenceResponse:
        request = InferenceRequest(text=text, language=language)
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post("/infer/text", json=request.model_dump())
                response.raise_for_status()
                return InferenceResponse(**response.json())
        except Exception:
            latency_ms = round((perf_counter() - started) * 1000, 2)
            return InferenceResponse(
                model_name="inference-service-unavailable",
                scores=[],
                latency_ms=latency_ms,
                fallback_used=True,
            )
