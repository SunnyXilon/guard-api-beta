from __future__ import annotations


MODALITY_CREDIT_WEIGHTS: dict[str, int] = {
    "text": 1,
    "image": 10,
    "audio": 10,
    "video": 25,
}


def credits_for_modality(modality: str) -> int:
    return MODALITY_CREDIT_WEIGHTS.get(modality, 1)
