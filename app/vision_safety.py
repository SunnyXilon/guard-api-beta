from __future__ import annotations

import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.taxonomy import ModerationCategory


SAFETY_LABELS = [
    # Original violence-detection labels.
    "people walking on a street",
    "buildings",
    "fight on a street",
    "fire on a street",
    "street violence",
    "road",
    "car crash",
    "cars on a road",
    "car parking area",
    "cars",
    "office environment",
    "office corridor",
    "violence in office",
    "fire in office",
    "people talking",
    "people walking in office",
    "person walking in office",
    "group of people",
    # Added trust-and-safety labels.
    "explicit sexual content",
    "nudity",
    "adult content",
    "sexual activity",
    "suggestive image",
    "weapons",
    "blood",
    "gore",
    "drug use",
    "illegal drugs",
    "child unsafe content",
    "self harm",
]


LABEL_CATEGORY_MAP: dict[str, list[ModerationCategory]] = {
    "fight on a street": [ModerationCategory.VIOLENCE],
    "fire on a street": [ModerationCategory.VIOLENCE],
    "street violence": [ModerationCategory.VIOLENCE],
    "car crash": [ModerationCategory.VIOLENCE],
    "violence in office": [ModerationCategory.VIOLENCE],
    "fire in office": [ModerationCategory.VIOLENCE],
    "explicit sexual content": [ModerationCategory.SEXUAL_CONTENT],
    "nudity": [ModerationCategory.SEXUAL_CONTENT],
    "adult content": [ModerationCategory.SEXUAL_CONTENT],
    "sexual activity": [ModerationCategory.SEXUAL_CONTENT],
    "suggestive image": [ModerationCategory.SEXUAL_CONTENT],
    "weapons": [ModerationCategory.VIOLENCE, ModerationCategory.ILLEGAL_ACTIVITY],
    "blood": [ModerationCategory.VIOLENCE],
    "gore": [ModerationCategory.VIOLENCE],
    "drug use": [ModerationCategory.ILLEGAL_ACTIVITY],
    "illegal drugs": [ModerationCategory.ILLEGAL_ACTIVITY],
    "child unsafe content": [ModerationCategory.CHILD_SAFETY],
    "self harm": [ModerationCategory.SELF_HARM],
}

UNSAFE_DOMINANCE_MARGIN = 0.01


@dataclass(frozen=True)
class VisionLabelScore:
    label: str
    confidence: float
    categories: list[ModerationCategory] = field(default_factory=list)


@dataclass(frozen=True)
class VisionSafetyResult:
    provider: str
    labels: list[VisionLabelScore] = field(default_factory=list)
    category_scores: dict[ModerationCategory, float] = field(default_factory=dict)
    fallback_used: bool = False
    error: str | None = None
    frames_scanned: int = 0

    @property
    def unsafe_labels(self) -> list[str]:
        return [score.label for score in self.labels if score.categories]


class LocalVisionSafetyScanner:
    provider = "local-clip-vision-safety"

    def __init__(
        self,
        *,
        enabled: bool = True,
        model_name: str = "ViT-B-32",
        pretrained: str = "openai",
        device: str = "cpu",
        threshold: float = 0.23,
        top_k: int = 5,
        batch_size: int = 4,
        frame_sample_seconds: float = 2.0,
        max_frames: int = 12,
    ) -> None:
        self.enabled = enabled
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device
        self.threshold = threshold
        self.top_k = top_k
        self.batch_size = max(batch_size, 1)
        self.frame_sample_seconds = frame_sample_seconds
        self.max_frames = max(max_frames, 1)
        self._backend: str | None = None
        self._model: Any | None = None
        self._preprocess: Any | None = None
        self._tokenizer: Any | None = None
        self._text_features: Any | None = None
        self._model_lock = threading.Lock()

    def warmup(self) -> VisionSafetyResult:
        if not self.enabled:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error="Local vision safety is disabled.")
        try:
            self._ensure_model()
            return VisionSafetyResult(provider=self.provider)
        except Exception as exc:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error=str(exc))

    def scan_image_bytes(self, image_bytes: bytes) -> VisionSafetyResult:
        if not self.enabled:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error="Local vision safety is disabled.")
        try:
            image = self._decode_image_bytes(image_bytes)
            return self.scan_image_array(image)
        except Exception as exc:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error=str(exc))

    def scan_image_array(self, image: np.ndarray) -> VisionSafetyResult:
        if not self.enabled:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error="Local vision safety is disabled.")
        try:
            labels, category_scores = self._scan_image_arrays([image])
            return VisionSafetyResult(
                provider=self.provider,
                labels=labels,
                category_scores=category_scores,
                frames_scanned=1,
            )
        except Exception as exc:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error=str(exc))

    def scan_video_bytes(self, video_bytes: bytes, suffix: str = ".mp4") -> VisionSafetyResult:
        if not self.enabled:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error="Local vision safety is disabled.")
        try:
            frames = self._sample_video_frames(video_bytes, suffix)
            if not frames:
                return VisionSafetyResult(
                    provider=self.provider,
                    fallback_used=True,
                    error="No video frames could be sampled.",
                )

            merged_labels: dict[str, VisionLabelScore] = {}
            frames_scanned = 0
            for start in range(0, len(frames), self.batch_size):
                batch = frames[start : start + self.batch_size]
                labels, _batch_scores = self._scan_image_arrays(batch)
                frames_scanned += len(batch)
                for label_score in labels:
                    current = merged_labels.get(label_score.label)
                    if current is None or label_score.confidence > current.confidence:
                        merged_labels[label_score.label] = label_score
            final_labels = sorted(merged_labels.values(), key=lambda item: item.confidence, reverse=True)[: self.top_k]

            return VisionSafetyResult(
                provider=self.provider,
                labels=final_labels,
                category_scores=self._category_scores(final_labels),
                frames_scanned=frames_scanned,
            )
        except Exception as exc:
            return VisionSafetyResult(provider=self.provider, fallback_used=True, error=str(exc))

    def _ensure_model(self) -> None:
        if self._model is not None:
            return

        with self._model_lock:
            if self._model is not None:
                return

            try:
                import torch
            except Exception as exc:
                raise RuntimeError("PyTorch is required for local vision safety scanning.") from exc

            try:
                import open_clip

                model, _, preprocess = open_clip.create_model_and_transforms(
                    self.model_name,
                    pretrained=self.pretrained,
                    device=self.device,
                )
                tokenizer = open_clip.get_tokenizer(self.model_name)
                prompts = [f"a photo of {label}" for label in SAFETY_LABELS]
                tokens = tokenizer(prompts).to(self.device)
                with torch.no_grad():
                    text_features = model.encode_text(tokens)
                    text_features /= text_features.norm(dim=-1, keepdim=True)
                self._backend = "open_clip"
            except Exception:
                try:
                    import clip

                    model, preprocess = clip.load("ViT-B/32", device=self.device)
                    prompts = [f"a photo of {label}" for label in SAFETY_LABELS]
                    tokens = clip.tokenize(prompts).to(self.device)
                    with torch.no_grad():
                        text_features = model.encode_text(tokens)
                        text_features /= text_features.norm(dim=-1, keepdim=True)
                    tokenizer = clip.tokenize
                    self._backend = "clip"
                except Exception as exc:
                    raise RuntimeError(
                        "Install open_clip_torch or clip-by-openai to enable local CLIP vision safety scanning."
                    ) from exc

            self._model = model
            self._model.eval()
            self._preprocess = preprocess
            self._tokenizer = tokenizer
            self._text_features = text_features

    def _predict_labels(self, image: np.ndarray) -> list[VisionLabelScore]:
        return self._predict_labels_batch([image])[0]

    def _scan_image_arrays(self, images: list[np.ndarray]) -> tuple[list[VisionLabelScore], dict[ModerationCategory, float]]:
        if not images:
            return [], {}

        self._ensure_model()
        merged_labels: dict[str, VisionLabelScore] = {}
        category_scores: dict[ModerationCategory, float] = {}
        for labels in self._predict_labels_batch(images):
            for label_score in labels:
                current = merged_labels.get(label_score.label)
                if current is None or label_score.confidence > current.confidence:
                    merged_labels[label_score.label] = label_score
            for category, score in self._category_scores(labels).items():
                category_scores[category] = max(category_scores.get(category, 0.0), score)

        return sorted(merged_labels.values(), key=lambda item: item.confidence, reverse=True)[: self.top_k], category_scores

    def _predict_labels_batch(self, images: list[np.ndarray]) -> list[list[VisionLabelScore]]:
        import torch
        from PIL import Image

        image_tensors = [
            self._preprocess(Image.fromarray(image).convert("RGB"))
            for image in images
        ]
        image_tensor = torch.stack(image_tensors).to(self.device)
        with torch.no_grad():
            image_features = self._model.encode_image(image_tensor)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            similarities = image_features @ self._text_features.T
            values, indices = similarities.topk(min(self.top_k, len(SAFETY_LABELS)), dim=1)

        batch_labels: list[list[VisionLabelScore]] = []
        for frame_values, frame_indices in zip(values.cpu().tolist(), indices.cpu().tolist()):
            labels: list[VisionLabelScore] = []
            for value, index in zip(frame_values, frame_indices):
                confidence = abs(float(value))
                label = SAFETY_LABELS[int(index)]
                categories = LABEL_CATEGORY_MAP.get(label, []) if confidence >= self.threshold else []
                labels.append(VisionLabelScore(label=label, confidence=round(confidence, 4), categories=categories))
            batch_labels.append(_remove_context_dominated_unsafe_labels(labels))
        return batch_labels

    def _sample_video_frames(self, video_bytes: bytes, suffix: str) -> list[np.ndarray]:
        try:
            import cv2
        except Exception as exc:
            raise RuntimeError("OpenCV is required for local video frame sampling.") from exc

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as file:
            file.write(video_bytes)
            video_path = Path(file.name)

        try:
            capture = cv2.VideoCapture(str(video_path))
            if not capture.isOpened():
                raise RuntimeError("Unable to open video file for frame sampling.")

            fps = capture.get(cv2.CAP_PROP_FPS) or 1.0
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            step = max(int(fps * self.frame_sample_seconds), 1)
            frames: list[np.ndarray] = []

            if frame_count > 0:
                candidate_indices = list(range(0, frame_count, step)) or [0]
                if len(candidate_indices) > self.max_frames:
                    selected_positions = np.linspace(0, len(candidate_indices) - 1, self.max_frames, dtype=int)
                    candidate_indices = [candidate_indices[int(position)] for position in selected_positions]
                for frame_index in candidate_indices[: self.max_frames]:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    success, frame = capture.read()
                    if success:
                        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                capture.release()
                return frames

            frame_index = 0
            while len(frames) < self.max_frames:
                success, frame = capture.read()
                if not success:
                    break
                if frame_index % step == 0:
                    frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                frame_index += 1
            capture.release()
            return frames
        finally:
            video_path.unlink(missing_ok=True)

    @staticmethod
    def _decode_image_bytes(image_bytes: bytes) -> np.ndarray:
        try:
            from PIL import Image
        except Exception as exc:
            raise RuntimeError("Pillow is required for local image safety scanning.") from exc

        from io import BytesIO

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        return np.array(image)

    @staticmethod
    def _category_scores(labels: list[VisionLabelScore]) -> dict[ModerationCategory, float]:
        scores: dict[ModerationCategory, float] = {}
        for label_score in labels:
            for category in label_score.categories:
                scores[category] = max(scores.get(category, 0.0), _clip_confidence_to_risk_score(label_score.confidence))
        return scores


def _clip_confidence_to_risk_score(confidence: float) -> float:
    # CLIP cosine values are commonly low even for correct matches. The source
    # violence model treats 0.23 as a positive label threshold, so map confirmed
    # matches into RTCM's moderation score range instead of using raw cosine.
    if confidence < 0.23:
        return 0.0
    normalized = (confidence - 0.23) / 0.17
    return round(max(0.55, min(0.99, 0.55 + normalized * 0.44)), 4)


def _remove_context_dominated_unsafe_labels(labels: list[VisionLabelScore]) -> list[VisionLabelScore]:
    safe_confidences = [label.confidence for label in labels if not LABEL_CATEGORY_MAP.get(label.label)]
    if not safe_confidences:
        return labels

    strongest_safe_context = max(safe_confidences)
    filtered: list[VisionLabelScore] = []
    for label in labels:
        if label.categories and label.confidence + UNSAFE_DOMINANCE_MARGIN < strongest_safe_context:
            filtered.append(VisionLabelScore(label=label.label, confidence=label.confidence, categories=[]))
        else:
            filtered.append(label)
    return filtered
