from __future__ import annotations

from fastapi import FastAPI

from inference_service.model_runner import TransformerModerationRunner
from shared.inference_schemas import InferenceRequest, InferenceResponse

app = FastAPI(title="RTCM Inference Service", version="0.1.0")
runner = TransformerModerationRunner()


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model": runner.model_name,
        "model_loaded": runner.model_loaded,
        "fallback_used": not runner.model_loaded,
        "load_error": runner.load_error,
    }


@app.post("/infer/text", response_model=InferenceResponse)
async def infer_text(request: InferenceRequest) -> InferenceResponse:
    return runner.score_text(request.text)
