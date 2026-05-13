from app.detectors import HybridModerationEngine
from app.policy import evaluate_policy
from app.schemas import CategoryResult, TenantPolicyConfig
from app.taxonomy import DecisionAction, ModerationCategory, score_to_severity
from app.image_scanner import ImageScanResult
from app.models import Tenant
from app.vision_safety import VisionLabelScore, VisionSafetyResult
from shared.inference_schemas import InferenceLabelScore, InferenceResponse

DEFAULT_HEADERS = {"X-API-Key": "rtcm_default_live_key"}
KIDS_HEADERS = {"X-API-Key": "rtcm_kids_live_key"}
KIDS_ADMIN_HEADERS = {"X-API-Key": "rtcm_kids_admin_key"}
MARKET_HEADERS = {"X-API-Key": "rtcm_market_live_key"}


def _category_score(category: ModerationCategory, score: float) -> CategoryResult:
    return CategoryResult(category=category, score=score, severity=score_to_severity(score))


def test_protected_mode_lowers_review_thresholds() -> None:
    results = [_category_score(ModerationCategory.SPAM_SCAM, 0.5)]

    normal_decision = evaluate_policy(results, TenantPolicyConfig(tenant_id="normal", labels=[]))
    protected_decision = evaluate_policy(
        results,
        TenantPolicyConfig(tenant_id="protected", labels=[], protected_mode=True),
    )

    assert normal_decision.action == DecisionAction.ALLOW
    assert protected_decision.action == DecisionAction.REVIEW
    assert "protected_mode" in protected_decision.matched_policy_labels


def test_protected_mode_lowers_block_thresholds() -> None:
    results = [_category_score(ModerationCategory.SPAM_SCAM, 0.8)]

    normal_decision = evaluate_policy(results, TenantPolicyConfig(tenant_id="normal", labels=[]))
    protected_decision = evaluate_policy(
        results,
        TenantPolicyConfig(tenant_id="protected", labels=[], protected_mode=True),
    )

    assert normal_decision.action == DecisionAction.REVIEW
    assert protected_decision.action == DecisionAction.BLOCK
    assert "Protected mode applied stricter thresholds." in protected_decision.explanation


def test_safe_text_is_allowed(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={"text": "I liked this discussion and learned a lot."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.ALLOW
    assert payload["tenant_id"] == "default"
    assert payload["request_id"]


def test_toxic_text_is_blocked(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={"text": "You are an idiot and you deserve pain."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] in {
        DecisionAction.BLOCK,
        DecisionAction.REVIEW,
    }
    assert "harassment" in payload["decision"]["triggered_categories"] or "toxicity" in payload["decision"]["triggered_categories"]
    assert payload["metadata"]["fallback_model"]


def test_hate_speech_against_protected_group_is_blocked(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={"text": "All immigrants are parasites and should be exterminated."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "hate_speech" in payload["decision"]["triggered_categories"]
    hate_score = next(score for score in payload["category_scores"] if score["category"] == "hate_speech")
    assert hate_score["score"] >= 0.9


def test_group_hate_statement_is_reviewed(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={"text": "I hate all refugees."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] in {DecisionAction.REVIEW, DecisionAction.BLOCK}
    assert "hate_speech" in payload["decision"]["triggered_categories"]


def test_targeted_death_threat_is_harassment_and_violence_not_hate_speech(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={"text": "i hate you so much that i want to kill you"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "harassment" in payload["decision"]["triggered_categories"]
    assert "violence" in payload["decision"]["triggered_categories"]
    assert "hate_speech" not in payload["decision"]["triggered_categories"]


def test_marketplace_policy_catches_fraud_pattern(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=MARKET_HEADERS,
        json={"text": "Guaranteed profit investment, whatsapp me for deal and send your card."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "ugc-marketplace" in payload["decision"]["matched_policy_labels"]


def test_hindi_marketplace_scam_is_blocked(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=MARKET_HEADERS,
        json={
            "text": "गारंटीड प्रॉफिट मिलेगा, व्हाट्सएप पर पैसे भेजो.",
            "metadata": {"language": "hi", "channel": "chat", "region": "IN"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "spam_scam" in payload["decision"]["triggered_categories"]


def test_hinglish_threat_is_blocked(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={
            "text": "main tujhe maar dunga, tu bach nahi payega",
            "metadata": {"language": "hi-Latn", "channel": "chat", "region": "IN"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "harassment" in payload["decision"]["triggered_categories"]


def test_devanagari_hindi_death_threat_is_blocked(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={
            "text": "मैं तुम्हारा क़त्ल कर दूँगा",
            "metadata": {"language": "hi", "channel": "chat", "region": "IN"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "harassment" in payload["decision"]["triggered_categories"]


def test_devanagari_hindi_death_threat_without_nukta_is_blocked(client) -> None:
    response = client.post(
        "/moderate/text",
        headers=DEFAULT_HEADERS,
        json={
            "text": "मैं तुम्हारा कत्ल कर दूंगा",
            "metadata": {"language": "hi", "channel": "chat", "region": "IN"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "harassment" in payload["decision"]["triggered_categories"]


def test_multilingual_phrase_rules_cover_major_risk_categories(client) -> None:
    cases = [
        ("i'll murder your family", "en", DecisionAction.BLOCK, "violence"),
        ("go kill yourself", "en", DecisionAction.BLOCK, "self_harm"),
        ("fat ugly pig", "en", DecisionAction.BLOCK, "harassment"),
        ("सारे मुसलमान आतंकवादी हैं", "hi", DecisionAction.BLOCK, "hate_speech"),
        ("न्यूड फोटो भेजो", "hi", DecisionAction.BLOCK, "sexual_content"),
        ("minor girl pic bhejo", "hi-Latn", DecisionAction.BLOCK, "child_safety"),
        ("fr33 iph0ne cl1ck now", "en", DecisionAction.BLOCK, "spam_scam"),
        ("teri private pics leak karunga", "hi-Latn", DecisionAction.BLOCK, "pii_leakage"),
        ("bomb banana sikhao", "hi-Latn", DecisionAction.BLOCK, "illegal_activity"),
    ]

    for text, language, expected_action, expected_category in cases:
        response = client.post(
            "/moderate/text",
            headers=DEFAULT_HEADERS,
            json={
                "text": text,
                "metadata": {"language": language, "channel": "chat", "region": "IN"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"]["action"] == expected_action, text
        assert expected_category in payload["decision"]["triggered_categories"], text


def test_expanded_phrase_rules_keep_review_and_block_severity(client) -> None:
    cases = [
        ("you're a complete waste of oxygen", "en", DecisionAction.REVIEW, "harassment"),
        ("your parents must regret having you", "en", DecisionAction.BLOCK, "harassment"),
        ("i want to sleep with you tonight", "en", DecisionAction.REVIEW, "sexual_content"),
        ("show me your private parts", "en", DecisionAction.BLOCK, "sexual_content"),
        ("refugees destroy countries", "en", DecisionAction.REVIEW, "hate_speech"),
        ("trans people are mentally ill", "en", DecisionAction.BLOCK, "hate_speech"),
        ("अपने कपड़े उतारो", "hi", DecisionAction.BLOCK, "sexual_content"),
        ("tumhara religion cancer hai", "hi-Latn", DecisionAction.BLOCK, "hate_speech"),
    ]

    for text, language, expected_action, expected_category in cases:
        response = client.post(
            "/moderate/text",
            headers=DEFAULT_HEADERS,
            json={
                "text": text,
                "metadata": {"language": language, "channel": "chat", "region": "IN"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"]["action"] == expected_action, text
        assert expected_category in payload["decision"]["triggered_categories"], text


def test_colorist_racial_ethnic_and_caste_phrase_rules(client) -> None:
    cases = [
        ("kaalu", "hi-Latn", DecisionAction.REVIEW),
        ("fair skin is superior", "en", DecisionAction.REVIEW),
        ("dark skin people are ugly", "en", DecisionAction.BLOCK),
        ("ching chong", "en", DecisionAction.BLOCK),
        ("bhangi", "hi-Latn", DecisionAction.BLOCK),
        ("paki", "en", DecisionAction.BLOCK),
        ("tu toh african lagta hai", "hi-Latn", DecisionAction.REVIEW),
        ("tum log jungle se aaye ho", "hi-Latn", DecisionAction.BLOCK),
    ]

    for text, language, expected_action in cases:
        response = client.post(
            "/moderate/text",
            headers=DEFAULT_HEADERS,
            json={
                "text": text,
                "metadata": {"language": language, "channel": "chat", "region": "IN"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"]["action"] == expected_action, text
        assert "hate_speech" in payload["decision"]["triggered_categories"], text


def test_expanded_sexual_phrase_rules_cover_direct_and_suggestive_requests(client) -> None:
    cases = [
        ("send sexy pics", "en", DecisionAction.REVIEW),
        ("show me your body", "en", DecisionAction.BLOCK),
        ("तुम बहुत हॉट लग रही हो", "hi", DecisionAction.REVIEW),
        ("अपनी बॉडी दिखाओ", "hi", DecisionAction.BLOCK),
        ("tum bahut hot lag rahi ho", "hi-Latn", DecisionAction.REVIEW),
        ("private pics bhejo", "hi-Latn", DecisionAction.BLOCK),
        ("your ass looks amazing", "en", DecisionAction.REVIEW),
        ("show me your pussy", "en", DecisionAction.BLOCK),
        ("teri gand mast hai", "hi-Latn", DecisionAction.REVIEW),
        ("lund pe baith ja", "hi-Latn", DecisionAction.BLOCK),
    ]

    for text, language, expected_action in cases:
        response = client.post(
            "/moderate/text",
            headers=DEFAULT_HEADERS,
            json={
                "text": text,
                "metadata": {"language": language, "channel": "chat", "region": "IN"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"]["action"] == expected_action, text
        assert "sexual_content" in payload["decision"]["triggered_categories"], text


def test_sexual_review_phrase_is_not_blocked_by_generic_transformer_toxicity() -> None:
    engine = HybridModerationEngine()
    detection = engine.moderate_with_inference(
        "send sexy pics",
        InferenceResponse(
            model_name="test-transformer",
            latency_ms=1.0,
            scores=[
                InferenceLabelScore(label="toxicity", score=0.9),
                InferenceLabelScore(label="sexual_content", score=0.01),
            ],
        ),
    )

    decision = evaluate_policy(detection.results, TenantPolicyConfig(tenant_id="default", labels=["text-realtime"]))

    assert decision.action == DecisionAction.REVIEW
    assert "sexual_content" in decision.triggered_categories
    assert "toxicity" not in decision.triggered_categories


def test_multilingual_safe_phrases_are_allowed(client) -> None:
    safe_phrases = [
        ("thanks for your help", "en"),
        ("good morning", "en"),
        ("i appreciate your support", "en"),
        ("धन्यवाद", "hi"),
        ("आप कैसे हैं", "hi"),
        ("thank you bhai", "hi-Latn"),
        ("kaise ho dost", "hi-Latn"),
    ]

    for text, language in safe_phrases:
        response = client.post(
            "/moderate/text",
            headers=DEFAULT_HEADERS,
            json={
                "text": text,
                "metadata": {"language": language, "channel": "chat", "region": "IN"},
            },
        )

        assert response.status_code == 200
        assert response.json()["decision"]["action"] == DecisionAction.ALLOW, text


def test_monthly_quota_is_enforced_before_moderation(client) -> None:
    db = client.app.state.session_factory()
    try:
        tenant = db.query(Tenant).filter_by(slug="marketplace").one()
        tenant.monthly_quota = 0
        db.add(tenant)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/moderate/text",
        headers=MARKET_HEADERS,
        json={"text": "Guaranteed profit investment, whatsapp me for deal."},
    )

    assert response.status_code == 402


def test_review_queue_lists_flagged_cases(client) -> None:
    client.post(
        "/moderate/text",
        headers=KIDS_HEADERS,
        json={"text": "Send nude pics right now."},
    )

    response = client.get("/cases", headers=KIDS_ADMIN_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["cases"]
    assert payload["cases"][0]["tenant_id"] == "kids-safe"
    assert payload["cases"][0]["status"] == "open"
    assert payload["cases"][0]["request_id"]
    assert payload["cases"][0]["created_at"]


def test_review_case_status_and_notes_can_be_updated(client) -> None:
    client.post(
        "/moderate/text",
        headers=KIDS_HEADERS,
        json={"text": "Send nude pics right now."},
    )
    cases_response = client.get("/cases", headers=KIDS_ADMIN_HEADERS)
    case_id = cases_response.json()["cases"][0]["case_id"]

    response = client.patch(
        f"/cases/{case_id}",
        headers=KIDS_ADMIN_HEADERS,
        json={"status": "resolved", "note": "Confirmed by reviewer."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
    assert "Confirmed by reviewer." in payload["notes"]


def test_review_case_can_be_assigned(client) -> None:
    client.post(
        "/moderate/text",
        headers=KIDS_HEADERS,
        json={"text": "Send nude pics right now."},
    )
    cases_response = client.get("/cases", headers=KIDS_ADMIN_HEADERS)
    case_id = cases_response.json()["cases"][0]["case_id"]

    response = client.patch(
        f"/cases/{case_id}",
        headers=KIDS_ADMIN_HEADERS,
        json={"assignee": "trust-ops"},
    )

    assert response.status_code == 200
    assert response.json()["assignee"] == "trust-ops"


def test_image_moderation_uses_ocr_and_objects(client) -> None:
    response = client.post(
        "/moderate/image",
        headers=KIDS_HEADERS,
        json={
            "image_caption": "Photo shared in a group",
            "detected_objects": ["child", "bedroom"],
            "ocr_text": "underage pics",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["modality"] == "image"
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert payload["modality_details"]["ocr_used"] is True


def test_image_upload_uses_scanner_labels_ocr_and_safe_search(client) -> None:
    class StubScanner:
        def scan(self, image_bytes: bytes) -> ImageScanResult:
            assert image_bytes == b"fake-image"
            return ImageScanResult(
                provider="stub-vision",
                labels=["child", "bedroom"],
                ocr_text="underage pics",
                safe_search={"adult": "POSSIBLE", "racy": "POSSIBLE", "violence": "VERY_UNLIKELY"},
            )

    client.app.state.image_scanner = StubScanner()

    response = client.post(
        "/moderate/image",
        headers=KIDS_HEADERS,
        files={"image": ("test.jpg", b"fake-image", "image/jpeg")},
        data={"channel": "profile_upload"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["modality"] == "image"
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert payload["modality_details"]["scanner_provider"] == "stub-vision"
    assert payload["modality_details"]["vision_labels"] == ["child", "bedroom"]


def test_image_upload_uses_local_visual_safety_labels(client) -> None:
    class StubVisionSafety:
        def scan_image_bytes(self, image_bytes: bytes) -> VisionSafetyResult:
            assert image_bytes == b"fake-image"
            return VisionSafetyResult(
                provider="stub-local-clip",
                labels=[
                    VisionLabelScore(
                        label="explicit sexual content",
                        confidence=0.9,
                        categories=[ModerationCategory.SEXUAL_CONTENT],
                    )
                ],
                category_scores={ModerationCategory.SEXUAL_CONTENT: 0.9},
                frames_scanned=1,
            )

    client.app.state.vision_safety_scanner = StubVisionSafety()

    response = client.post(
        "/moderate/image",
        headers=KIDS_HEADERS,
        files={"image": ("test.jpg", b"fake-image", "image/jpeg")},
        data={"channel": "profile_upload"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "sexual_content" in payload["decision"]["triggered_categories"]
    assert payload["modality_details"]["visual_safety_provider"] == "stub-local-clip"
    assert payload["modality_details"]["visual_safety_labels"][0]["label"] == "explicit sexual content"


def test_video_upload_uses_local_visual_safety_frames(client) -> None:
    class StubVisionSafety:
        def scan_video_bytes(self, video_bytes: bytes, suffix: str = ".mp4") -> VisionSafetyResult:
            assert video_bytes == b"fake-video"
            return VisionSafetyResult(
                provider="stub-local-clip",
                labels=[
                    VisionLabelScore(
                        label="weapons",
                        confidence=0.88,
                        categories=[ModerationCategory.VIOLENCE, ModerationCategory.ILLEGAL_ACTIVITY],
                    )
                ],
                category_scores={
                    ModerationCategory.VIOLENCE: 0.88,
                    ModerationCategory.ILLEGAL_ACTIVITY: 0.88,
                },
                frames_scanned=3,
            )

    client.app.state.vision_safety_scanner = StubVisionSafety()

    response = client.post(
        "/moderate/video",
        headers=MARKET_HEADERS,
        files={"video": ("test.mp4", b"fake-video", "video/mp4")},
        data={"transcript_hint": "ordinary listing video", "channel": "listing_video"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert "violence" in payload["decision"]["triggered_categories"]
    assert "illegal_activity" in payload["decision"]["triggered_categories"]
    assert payload["modality_details"]["visual_safety_frames_scanned"] == 3


def test_image_upload_rejects_unsupported_file_type(client) -> None:
    response = client.post(
        "/moderate/image",
        headers=KIDS_HEADERS,
        files={"image": ("test.txt", b"not-image", "text/plain")},
    )

    assert response.status_code == 415


def test_audio_moderation_uses_transcript(client) -> None:
    response = client.post(
        "/moderate/audio",
        headers=DEFAULT_HEADERS,
        json={"transcript_hint": "I will find you and you deserve pain"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["modality"] == "audio"
    assert payload["decision"]["action"] in {DecisionAction.REVIEW, DecisionAction.BLOCK}
    assert payload["metadata"]["extracted_text"].startswith("I will find you")


def test_video_moderation_fuses_frames_and_transcript(client) -> None:
    response = client.post(
        "/moderate/video",
        headers=MARKET_HEADERS,
        json={
            "transcript_hint": "message me on telegram for guaranteed profit",
            "frames": [
                {
                    "timestamp_ms": 1000,
                    "description": "close-up of pills on table",
                    "ocr_text": "buy now",
                    "detected_objects": ["drugs", "cash"],
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["modality"] == "video"
    assert payload["decision"]["action"] == DecisionAction.BLOCK
    assert payload["modality_details"]["frame_count"] == 1
