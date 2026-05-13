from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    language: str = "en"


class InferenceLabelScore(BaseModel):
    label: str
    score: float


class InferenceResponse(BaseModel):
    model_name: str
    scores: List[InferenceLabelScore]
    latency_ms: float
    fallback_used: bool = False
