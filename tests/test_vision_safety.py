import numpy as np

from app.image_scanner import GoogleVisionImageScanner
from app.taxonomy import ModerationCategory
from app.vision_safety import (
    LocalVisionSafetyScanner,
    VisionLabelScore,
    _clip_confidence_to_risk_score,
    _remove_context_dominated_unsafe_labels,
)


def test_clip_confidence_maps_positive_labels_to_reviewable_risk() -> None:
    assert _clip_confidence_to_risk_score(0.22) == 0.0
    assert _clip_confidence_to_risk_score(0.23) == 0.55
    assert _clip_confidence_to_risk_score(0.4) == 0.99


def test_google_vision_scanner_skips_when_disabled() -> None:
    result = GoogleVisionImageScanner(enabled=False).scan(b"image")

    assert result.fallback_used is True
    assert "disabled" in result.error


def test_context_dominated_unsafe_label_does_not_trigger_category() -> None:
    labels = _remove_context_dominated_unsafe_labels(
        [
            VisionLabelScore(label="people walking on a street", confidence=0.2811, categories=[]),
            VisionLabelScore(label="people talking", confidence=0.2528, categories=[]),
            VisionLabelScore(label="fight on a street", confidence=0.2523, categories=[ModerationCategory.VIOLENCE]),
        ]
    )

    assert labels[-1].label == "fight on a street"
    assert labels[-1].categories == []


def test_strong_unsafe_label_survives_context_filter() -> None:
    labels = _remove_context_dominated_unsafe_labels(
        [
            VisionLabelScore(label="car parking area", confidence=0.2702, categories=[]),
            VisionLabelScore(label="fight on a street", confidence=0.2812, categories=[ModerationCategory.VIOLENCE]),
        ]
    )

    assert labels[-1].categories == [ModerationCategory.VIOLENCE]


def test_video_scan_batches_frame_inference() -> None:
    class StubScanner(LocalVisionSafetyScanner):
        def __init__(self) -> None:
            super().__init__(batch_size=4, max_frames=4)
            self.batch_sizes: list[int] = []

        def _sample_video_frames(self, video_bytes: bytes, suffix: str) -> list[np.ndarray]:
            return [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(4)]

        def _scan_image_arrays(
            self, images: list[np.ndarray]
        ) -> tuple[list[VisionLabelScore], dict[ModerationCategory, float]]:
            self.batch_sizes.append(len(images))
            return [
                VisionLabelScore(
                    label="weapons",
                    confidence=0.4,
                    categories=[ModerationCategory.VIOLENCE, ModerationCategory.ILLEGAL_ACTIVITY],
                )
            ], {
                ModerationCategory.VIOLENCE: 0.99,
                ModerationCategory.ILLEGAL_ACTIVITY: 0.99,
            }

    scanner = StubScanner()
    result = scanner.scan_video_bytes(b"fake-video")

    assert scanner.batch_sizes == [4]
    assert result.frames_scanned == 4
    assert result.category_scores[ModerationCategory.VIOLENCE] == 0.99


def test_video_scan_ignores_hidden_batch_category_scores() -> None:
    class StubScanner(LocalVisionSafetyScanner):
        def __init__(self) -> None:
            super().__init__(batch_size=4, max_frames=4)

        def _sample_video_frames(self, video_bytes: bytes, suffix: str) -> list[np.ndarray]:
            return [np.zeros((8, 8, 3), dtype=np.uint8)]

        def _scan_image_arrays(
            self, images: list[np.ndarray]
        ) -> tuple[list[VisionLabelScore], dict[ModerationCategory, float]]:
            return [
                VisionLabelScore(label="people walking on a street", confidence=0.28, categories=[]),
                VisionLabelScore(label="people talking", confidence=0.25, categories=[]),
            ], {ModerationCategory.SEXUAL_CONTENT: 0.58}

    result = StubScanner().scan_video_bytes(b"fake-video")

    assert result.unsafe_labels == []
    assert ModerationCategory.SEXUAL_CONTENT not in result.category_scores
