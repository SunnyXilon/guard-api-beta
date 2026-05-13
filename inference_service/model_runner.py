from __future__ import annotations

import os
from time import perf_counter

from app.taxonomy import ModerationCategory
from shared.inference_schemas import InferenceLabelScore, InferenceResponse

try:
    from transformers import pipeline
except Exception:  # pragma: no cover
    pipeline = None


class TransformerModerationRunner:
    def __init__(self) -> None:
        self.model_name = "unitary/toxic-bert"
        self._pipeline = None
        self.load_error: str | None = None
        self.model_enabled = os.getenv("RTCM_ENABLE_HF_MODEL", "true").lower() == "true"
        if not self.model_enabled:
            self.load_error = "HuggingFace model loading is disabled by RTCM_ENABLE_HF_MODEL."
        elif pipeline is not None:
            try:
                self._pipeline = pipeline("text-classification", model=self.model_name, top_k=None)
            except Exception as exc:
                self.load_error = str(exc)
                self._pipeline = None
        else:
            self.load_error = "transformers is not installed"

    @property
    def model_loaded(self) -> bool:
        return self._pipeline is not None

    def score_text(self, text: str) -> InferenceResponse:
        started = perf_counter()
        if self._pipeline is None:
            lowered = text.lower()
            heuristic = {
                ModerationCategory.TOXICITY.value: 0.82 if "idiot" in lowered else 0.03,
                ModerationCategory.HARASSMENT.value: 0.88 if "deserve pain" in lowered else 0.02,
                ModerationCategory.SPAM_SCAM.value: 0.85 if "guaranteed profit" in lowered else 0.02,
            }
            latency_ms = round((perf_counter() - started) * 1000, 2)
            return InferenceResponse(
                model_name="heuristic-transformer-fallback",
                scores=[InferenceLabelScore(label=label, score=score) for label, score in heuristic.items()],
                latency_ms=latency_ms,
                fallback_used=True,
            )

        raw_scores = self._pipeline(text)[0]
        normalized = {category.value: 0.01 for category in ModerationCategory}
        for item in raw_scores:
            label = str(item["label"]).lower()
            score = float(item["score"])
            if "toxic" in label:
                normalized[ModerationCategory.TOXICITY.value] = max(normalized[ModerationCategory.TOXICITY.value], score)
            if "insult" in label or "threat" in label:
                normalized[ModerationCategory.HARASSMENT.value] = max(
                    normalized[ModerationCategory.HARASSMENT.value], score
                )
            if "obscene" in label:
                normalized[ModerationCategory.SEXUAL_CONTENT.value] = max(
                    normalized[ModerationCategory.SEXUAL_CONTENT.value], score
                )

        latency_ms = round((perf_counter() - started) * 1000, 2)
        return InferenceResponse(
            model_name=self.model_name,
            scores=[InferenceLabelScore(label=label, score=score) for label, score in normalized.items()],
            latency_ms=latency_ms,
        )
