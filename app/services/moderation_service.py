from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.audio_transcriber import AudioTranscriptionResult, OpenAIAudioTranscriber
from app.detectors import HybridModerationEngine
from app.image_scanner import GoogleVisionImageScanner, ImageScanResult
from app.inference_client import InferenceClient
from app.policy import evaluate_policy
from app.repositories.moderation import ModerationRepository
from app.repositories.tenants import TenantRepository
from app.schemas import (
    AudioModerationRequest,
    AuthenticatedTenant,
    ImageModerationRequest,
    MultimodalModerationResponse,
    ScoreMetadata,
    TextModerationRequest,
    TextModerationResponse,
    VideoModerationRequest,
)
from app.services.audit_service import AuditService
from app.services.policy_service import PolicyService
from app.services.review_service import ReviewService
from app.taxonomy import DecisionAction
from app.usage_credits import credits_for_record, credits_for_usage
from app.vision_safety import LocalVisionSafetyScanner, VisionSafetyResult


class ModerationService:
    def __init__(
        self,
        db: Session,
        engine: HybridModerationEngine,
        inference_client: InferenceClient,
        image_scanner: GoogleVisionImageScanner | None = None,
        vision_safety_scanner: LocalVisionSafetyScanner | None = None,
        audio_transcriber: OpenAIAudioTranscriber | None = None,
    ) -> None:
        self.db = db
        self.engine = engine
        self.inference_client = inference_client
        self.image_scanner = image_scanner or GoogleVisionImageScanner()
        self.vision_safety_scanner = vision_safety_scanner or LocalVisionSafetyScanner(enabled=False)
        self.audio_transcriber = audio_transcriber or OpenAIAudioTranscriber()
        self.moderation_repository = ModerationRepository(db)
        self.tenant_repository = TenantRepository(db)
        self.policy_service = PolicyService(self.tenant_repository)
        self.review_service = ReviewService(self.moderation_repository)
        self.audit_service = AuditService(self.moderation_repository)

    async def moderate_text(
        self, request: TextModerationRequest, tenant: AuthenticatedTenant
    ) -> TextModerationResponse:
        credit_cost = credits_for_usage("text")
        self._enforce_monthly_quota(tenant, "text", credit_cost)
        started = perf_counter()
        inference = await self.inference_client.score_text(
            request.text,
            language=request.metadata.language,
        )
        detection = self.engine.moderate_with_inference(request.text, inference=inference)
        policy = self.policy_service.get_policy_for_tenant(tenant.tenant_id)
        decision = evaluate_policy(detection.results, policy)
        latency_ms = round((perf_counter() - started) * 1000, 2)

        return self._persist_response(
            tenant=tenant,
            content_text=request.text,
            content_metadata=self._billing_metadata(request.metadata.model_dump(mode="json"), credit_cost),
            modality="text",
            detection_results=detection.results,
            decision=decision,
            score_metadata=ScoreMetadata(
                fast_model="rules-fast-v1",
                fallback_model=detection.fallback_model_name,
                policy_version="2026-04-mvp",
                latency_ms=latency_ms,
                modality="text",
            ),
            response_cls=TextModerationResponse,
        )

    async def moderate_image(
        self,
        request: ImageModerationRequest,
        tenant: AuthenticatedTenant,
        image_bytes: bytes | None = None,
        filename: str | None = None,
    ) -> MultimodalModerationResponse:
        credit_cost = credits_for_usage("image")
        self._enforce_monthly_quota(tenant, "image", credit_cost)
        started = perf_counter()
        vision_scan = self._scan_image_bytes(image_bytes, include_ocr=None if not request.ocr_text.strip() else False)
        safety_scan = self._scan_image_safety(image_bytes)
        detected_objects = self._merge_unique(request.detected_objects, vision_scan.labels if vision_scan else [])
        ocr_text = "\n".join(
            part for part in [request.ocr_text.strip(), vision_scan.ocr_text.strip() if vision_scan else ""] if part
        )
        image_caption = request.image_caption or (vision_scan.caption if vision_scan else "")
        detection = self.engine.moderate_image(
            image_caption,
            detected_objects,
            ocr_text,
            safe_search=vision_scan.safe_search if vision_scan else None,
            vision_safety_scores=safety_scan.category_scores if safety_scan else None,
            vision_safety_labels=safety_scan.unsafe_labels if safety_scan else None,
        )
        policy = self.policy_service.get_policy_for_tenant(tenant.tenant_id)
        decision = evaluate_policy(detection.results, policy)
        latency_ms = round((perf_counter() - started) * 1000, 2)
        modality_details = dict(detection.details)
        if vision_scan:
            modality_details.update(
                {
                    "uploaded_filename": filename,
                    "scanner_provider": vision_scan.provider,
                    "scanner_fallback_used": vision_scan.fallback_used,
                    "scanner_error": vision_scan.error,
                    "vision_labels": vision_scan.labels,
                    "vision_ocr_scanned": vision_scan.ocr_scanned,
                }
            )
        if safety_scan:
            modality_details.update(self._vision_safety_details(safety_scan))

        return self._persist_response(
            tenant=tenant,
            content_text=detection.extracted_text or request.image_url or filename or "[image payload]",
            content_metadata=self._billing_metadata(request.metadata.model_dump(mode="json"), credit_cost),
            modality="image",
            detection_results=detection.results,
            decision=decision,
            score_metadata=ScoreMetadata(
                fast_model="vision-heuristic-v1",
                fallback_model="ocr-surface-v1" if request.ocr_text else "not_used",
                policy_version="2026-04-mvp",
                latency_ms=latency_ms,
                modality="image",
                extracted_text=detection.extracted_text,
            ),
            response_cls=MultimodalModerationResponse,
            modality_details=modality_details,
        )

    def _scan_image_bytes(self, image_bytes: bytes | None, include_ocr: bool | None = None) -> ImageScanResult | None:
        if not image_bytes:
            return None
        return self.image_scanner.scan(image_bytes, include_ocr=include_ocr)

    def _scan_image_safety(self, image_bytes: bytes | None) -> VisionSafetyResult | None:
        if not image_bytes:
            return None
        return self.vision_safety_scanner.scan_image_bytes(image_bytes)

    @staticmethod
    def _merge_unique(first: list[str], second: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*first, *second]:
            normalized = item.strip()
            key = normalized.lower()
            if normalized and key not in seen:
                merged.append(normalized)
                seen.add(key)
        return merged

    async def moderate_audio(
        self,
        request: AudioModerationRequest,
        tenant: AuthenticatedTenant,
        audio_bytes: bytes | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> MultimodalModerationResponse:
        if audio_bytes is not None and request.duration_seconds is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded audio moderation requires duration_seconds for per-minute billing.",
            )
        credit_cost = credits_for_usage("audio", request.duration_seconds)
        self._enforce_monthly_quota(tenant, "audio", credit_cost)
        started = perf_counter()
        transcription = await self._transcribe_audio_bytes(
            audio_bytes,
            filename=filename,
            content_type=content_type,
            prompt=request.transcript_hint,
            language=request.metadata.language,
        )
        transcript = self._audio_transcript(request.transcript_hint, transcription)
        detection = self.engine.moderate_audio(transcript)
        policy = self.policy_service.get_policy_for_tenant(tenant.tenant_id)
        decision = evaluate_policy(detection.results, policy)
        latency_ms = round((perf_counter() - started) * 1000, 2)

        return self._persist_response(
            tenant=tenant,
            content_text=detection.extracted_text or filename or request.audio_url or "[audio payload]",
            content_metadata=self._billing_metadata(
                request.metadata.model_dump(mode="json"),
                credit_cost,
                duration_seconds=request.duration_seconds,
            ),
            modality="audio",
            detection_results=detection.results,
            decision=decision,
            score_metadata=ScoreMetadata(
                fast_model="transcribe-heuristic-v1",
                fallback_model="not_used",
                policy_version="2026-04-mvp",
                latency_ms=latency_ms,
                modality="audio",
                extracted_text=detection.extracted_text,
            ),
            response_cls=MultimodalModerationResponse,
            modality_details={
                **detection.details,
                "uploaded_filename": filename,
                "audio_content_type": content_type,
                "credit_cost": credit_cost,
                "duration_seconds": request.duration_seconds,
                "transcription_provider": transcription.provider if transcription else "manual_hint",
                "transcription_model": transcription.model if transcription else "manual_hint",
                "transcription_fallback_used": transcription.fallback_used if transcription else False,
                "transcription_error": transcription.error if transcription else None,
            },
        )

    async def _transcribe_audio_bytes(
        self,
        audio_bytes: bytes | None,
        *,
        filename: str | None,
        content_type: str | None,
        prompt: str,
        language: str,
    ) -> AudioTranscriptionResult | None:
        if not audio_bytes:
            return None
        return await self.audio_transcriber.transcribe(
            audio_bytes,
            filename=filename or "audio.webm",
            content_type=content_type or "audio/webm",
            prompt=prompt,
            language=language,
        )

    @staticmethod
    def _audio_transcript(manual_hint: str, transcription: AudioTranscriptionResult | None) -> str:
        transcribed_text = (transcription.text if transcription else "").strip()
        manual_text = manual_hint.strip()
        if transcribed_text and manual_text:
            return f"{transcribed_text}\n\nContext hint: {manual_text}"
        return transcribed_text or manual_text

    async def moderate_video(
        self,
        request: VideoModerationRequest,
        tenant: AuthenticatedTenant,
        video_bytes: bytes | None = None,
        filename: str | None = None,
    ) -> MultimodalModerationResponse:
        if video_bytes is not None and request.duration_seconds is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded video moderation requires duration_seconds for beta per-minute billing.",
            )
        credit_cost = credits_for_usage("video", request.duration_seconds)
        self._enforce_monthly_quota(tenant, "video", credit_cost)
        started = perf_counter()
        safety_scan = self._scan_video_safety(video_bytes, filename)
        detection = self.engine.moderate_video(
            request.transcript_hint,
            [frame.model_dump(mode="python") for frame in request.frames],
            vision_safety_scores=safety_scan.category_scores if safety_scan else None,
            vision_safety_labels=safety_scan.unsafe_labels if safety_scan else None,
        )
        policy = self.policy_service.get_policy_for_tenant(tenant.tenant_id)
        decision = evaluate_policy(detection.results, policy)
        latency_ms = round((perf_counter() - started) * 1000, 2)

        modality_details = dict(detection.details)
        if video_bytes is not None:
            modality_details["uploaded_filename"] = filename
        modality_details["credit_cost"] = credit_cost
        modality_details["duration_seconds"] = request.duration_seconds
        if safety_scan:
            modality_details.update(self._vision_safety_details(safety_scan))

        return self._persist_response(
            tenant=tenant,
            content_text=detection.extracted_text or filename or request.video_url or "[video payload]",
            content_metadata=self._billing_metadata(
                request.metadata.model_dump(mode="json"),
                credit_cost,
                duration_seconds=request.duration_seconds,
            ),
            modality="video",
            detection_results=detection.results,
            decision=decision,
            score_metadata=ScoreMetadata(
                fast_model="frame-fusion-v1",
                fallback_model="not_used",
                policy_version="2026-04-mvp",
                latency_ms=latency_ms,
                modality="video",
                extracted_text=detection.extracted_text,
            ),
            response_cls=MultimodalModerationResponse,
            modality_details=modality_details,
        )

    def _scan_video_safety(self, video_bytes: bytes | None, filename: str | None) -> VisionSafetyResult | None:
        if not video_bytes:
            return None
        suffix = f".{filename.rsplit('.', 1)[-1]}" if filename and "." in filename else ".mp4"
        return self.vision_safety_scanner.scan_video_bytes(video_bytes, suffix=suffix)

    @staticmethod
    def _vision_safety_details(scan: VisionSafetyResult) -> dict:
        return {
            "visual_safety_provider": scan.provider,
            "visual_safety_fallback_used": scan.fallback_used,
            "visual_safety_error": scan.error,
            "visual_safety_frames_scanned": scan.frames_scanned,
            "visual_safety_labels": [
                {
                    "label": label.label,
                    "confidence": label.confidence,
                    "categories": [category.value for category in label.categories],
                }
                for label in scan.labels
            ],
        }

    @staticmethod
    def _billing_metadata(
        content_metadata: dict,
        credit_cost: int,
        duration_seconds: float | None = None,
    ) -> dict:
        content_metadata["credit_cost"] = credit_cost
        if duration_seconds is not None:
            content_metadata["duration_seconds"] = duration_seconds
        return content_metadata

    def _persist_response(
        self,
        *,
        tenant: AuthenticatedTenant,
        content_text: str,
        content_metadata: dict,
        modality: str,
        detection_results: list,
        decision,
        score_metadata: ScoreMetadata,
        response_cls,
        modality_details: dict | None = None,
    ):
        request_record = self.moderation_repository.create_request(
            tenant_id=self.tenant_repository.get_tenant_by_slug(tenant.tenant_id).id,  # type: ignore[union-attr]
            modality=modality,
            content_text=content_text,
            content_metadata=content_metadata,
        )
        self.moderation_repository.create_result(
            request_id=request_record.id,
            tenant_id=request_record.tenant_id,
            action=decision.action.value,
            category_scores=[score.model_dump(mode="json") for score in detection_results],
            matched_policy_labels=decision.matched_policy_labels,
            explanation=decision.explanation,
            metadata_json=score_metadata.model_dump(mode="json"),
        )

        review_case_id = None
        if decision.action in {DecisionAction.REVIEW, DecisionAction.BLOCK}:
            review_case = self.review_service.create_case(
                request_id=request_record.id,
                tenant_id=request_record.tenant_id,
                submitted_text=content_text,
                action=decision.action.value,
                category_scores=detection_results,
            )
            review_case_id = review_case.case_id

        self.audit_service.log_event(
            tenant_id=request_record.tenant_id,
            request_id=request_record.id,
            event_type="moderation.completed",
            payload={
                "tenant_slug": tenant.tenant_id,
                "api_key_id": tenant.api_key_id,
                "modality": modality,
                "decision": decision.action.value,
                "matched_policy_labels": decision.matched_policy_labels,
                "review_case_id": review_case_id,
                "model_metadata": score_metadata.model_dump(mode="json"),
            },
            latency_ms=score_metadata.latency_ms,
        )
        self.db.commit()

        response_payload = dict(
            request_id=request_record.id,
            tenant_id=tenant.tenant_id,
            category_scores=detection_results,
            decision=decision,
            metadata=score_metadata,
            review_case_id=review_case_id,
        )
        if response_cls is MultimodalModerationResponse:
            response_payload["modality_details"] = modality_details or {}
        return response_cls(**response_payload)

    def _enforce_monthly_quota(self, tenant: AuthenticatedTenant, modality: str, credit_cost: int) -> None:
        tenant_row = self.tenant_repository.get_tenant_by_slug(tenant.tenant_id)
        if not tenant_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        tenant_ids, monthly_quota, plan_name = self.tenant_repository.quota_scope_for_tenant(tenant_row)
        decisions = self.moderation_repository.list_request_results_between_tenants(tenant_ids, start, end)
        used = sum(credits_for_record(request.modality, request.content_metadata) for request, _result in decisions)
        next_cost = credit_cost
        if used + next_cost > monthly_quota:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Monthly Guard credit quota exceeded for the {plan_name} plan "
                    f"({used}/{monthly_quota} Guard credits used; this {modality} check needs {next_cost} Guard credits). "
                    "Upgrade the plan from Billing or wait for next month's reset."
                ),
            )
