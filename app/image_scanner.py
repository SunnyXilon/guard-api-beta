from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageScanResult:
    provider: str
    labels: list[str] = field(default_factory=list)
    ocr_text: str = ""
    safe_search: dict[str, str] = field(default_factory=dict)
    fallback_used: bool = False
    error: str | None = None

    @property
    def caption(self) -> str:
        if not self.labels:
            return ""
        return "Detected image labels: " + ", ".join(self.labels)


class GoogleVisionImageScanner:
    provider = "google-cloud-vision"

    def __init__(self, max_labels: int = 10, enabled: bool = True) -> None:
        self.max_labels = max_labels
        self.enabled = enabled

    def scan(self, image_bytes: bytes) -> ImageScanResult:
        if not self.enabled:
            return ImageScanResult(
                provider=self.provider,
                fallback_used=True,
                error="Google Cloud Vision scanning is disabled because credentials are not configured.",
            )

        try:
            from google.cloud import vision
        except Exception as exc:
            return ImageScanResult(
                provider=self.provider,
                fallback_used=True,
                error=f"Google Cloud Vision client is not installed: {exc}",
            )

        try:
            client = vision.ImageAnnotatorClient()
            image = vision.Image(content=image_bytes)

            label_response = client.label_detection(image=image, max_results=self.max_labels)
            text_response = client.text_detection(image=image)
            safe_response = client.safe_search_detection(image=image)

            self._raise_if_vision_error(label_response, "label_detection")
            self._raise_if_vision_error(text_response, "text_detection")
            self._raise_if_vision_error(safe_response, "safe_search_detection")

            labels = [annotation.description for annotation in label_response.label_annotations]
            text_annotations = list(text_response.text_annotations)
            ocr_text = text_annotations[0].description if text_annotations else ""
            safe = safe_response.safe_search_annotation
            safe_search = {
                "adult": self._likelihood_name(vision, safe.adult),
                "medical": self._likelihood_name(vision, safe.medical),
                "spoof": self._likelihood_name(vision, safe.spoof),
                "violence": self._likelihood_name(vision, safe.violence),
                "racy": self._likelihood_name(vision, safe.racy),
            }

            return ImageScanResult(
                provider=self.provider,
                labels=labels,
                ocr_text=ocr_text,
                safe_search=safe_search,
            )
        except Exception as exc:
            return ImageScanResult(provider=self.provider, fallback_used=True, error=str(exc))

    @staticmethod
    def _raise_if_vision_error(response: Any, operation: str) -> None:
        if getattr(response, "error", None) and response.error.message:
            raise RuntimeError(f"{operation}: {response.error.message}")

    @staticmethod
    def _likelihood_name(vision: Any, value: int) -> str:
        return vision.Likelihood(value).name
