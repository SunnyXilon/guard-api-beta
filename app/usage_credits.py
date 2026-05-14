from __future__ import annotations

from math import ceil


MODALITY_CREDIT_WEIGHTS: dict[str, int] = {
    "text": 1,
    "image": 10,
    "audio": 10,
    "video": 50,
}


def credits_for_modality(modality: str) -> int:
    return MODALITY_CREDIT_WEIGHTS.get(modality, 1)


def credits_for_usage(modality: str, duration_seconds: float | int | None = None) -> int:
    if modality not in {"audio", "video"}:
        return credits_for_modality(modality)

    started_minutes = 1
    if duration_seconds is not None:
        started_minutes = max(1, ceil(float(duration_seconds) / 60))
    return credits_for_modality(modality) * started_minutes


def credits_for_record(modality: str, content_metadata: dict | None = None) -> int:
    stored_cost = (content_metadata or {}).get("credit_cost")
    if isinstance(stored_cost, int) and stored_cost > 0:
        return stored_cost
    return credits_for_usage(modality, (content_metadata or {}).get("duration_seconds"))
