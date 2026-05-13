from __future__ import annotations

from enum import Enum
from typing import Dict


class ModerationCategory(str, Enum):
    TOXICITY = "toxicity"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    SEXUAL_CONTENT = "sexual_content"
    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    EXTREMISM = "extremism"
    SPAM_SCAM = "spam_scam"
    CHILD_SAFETY = "child_safety"
    PII_LEAKAGE = "pii_leakage"
    ILLEGAL_ACTIVITY = "illegal_activity"


class SeverityLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionAction(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


CATEGORY_DESCRIPTIONS: Dict[ModerationCategory, str] = {
    ModerationCategory.TOXICITY: "Insults, abusive language, or aggressive hostility.",
    ModerationCategory.HARASSMENT: "Targeted bullying, threats, or repeated intimidation.",
    ModerationCategory.HATE_SPEECH: "Protected-class slurs, dehumanization, or hateful attacks.",
    ModerationCategory.SEXUAL_CONTENT: "Explicit sexual language, solicitation, or adult content.",
    ModerationCategory.SELF_HARM: "Self-harm encouragement, ideation, or suicide-related risk.",
    ModerationCategory.VIOLENCE: "Graphic violence, threats of harm, or encouragement of violence.",
    ModerationCategory.EXTREMISM: "Terrorist praise, recruitment, or violent extremist content.",
    ModerationCategory.SPAM_SCAM: "Spam, phishing, impersonation, or scam-like behavior.",
    ModerationCategory.CHILD_SAFETY: "Child exploitation, grooming, or content unsafe for minors.",
    ModerationCategory.PII_LEAKAGE: "Exposure of emails, phone numbers, cards, or sensitive personal data.",
    ModerationCategory.ILLEGAL_ACTIVITY: "Promotion of drugs, weapons, fraud, or other illegal conduct.",
}


DEFAULT_CATEGORY_THRESHOLDS: Dict[ModerationCategory, Dict[DecisionAction, float]] = {
    ModerationCategory.TOXICITY: {
        DecisionAction.REVIEW: 0.55,
        DecisionAction.BLOCK: 0.82,
    },
    ModerationCategory.HARASSMENT: {
        DecisionAction.REVIEW: 0.52,
        DecisionAction.BLOCK: 0.8,
    },
    ModerationCategory.HATE_SPEECH: {
        DecisionAction.REVIEW: 0.45,
        DecisionAction.BLOCK: 0.72,
    },
    ModerationCategory.SEXUAL_CONTENT: {
        DecisionAction.REVIEW: 0.58,
        DecisionAction.BLOCK: 0.86,
    },
    ModerationCategory.SELF_HARM: {
        DecisionAction.REVIEW: 0.35,
        DecisionAction.BLOCK: 0.68,
    },
    ModerationCategory.VIOLENCE: {
        DecisionAction.REVIEW: 0.45,
        DecisionAction.BLOCK: 0.78,
    },
    ModerationCategory.EXTREMISM: {
        DecisionAction.REVIEW: 0.3,
        DecisionAction.BLOCK: 0.65,
    },
    ModerationCategory.SPAM_SCAM: {
        DecisionAction.REVIEW: 0.55,
        DecisionAction.BLOCK: 0.84,
    },
    ModerationCategory.CHILD_SAFETY: {
        DecisionAction.REVIEW: 0.2,
        DecisionAction.BLOCK: 0.5,
    },
    ModerationCategory.PII_LEAKAGE: {
        DecisionAction.REVIEW: 0.4,
        DecisionAction.BLOCK: 0.7,
    },
    ModerationCategory.ILLEGAL_ACTIVITY: {
        DecisionAction.REVIEW: 0.42,
        DecisionAction.BLOCK: 0.73,
    },
}


DEFAULT_SEVERITY_BANDS = (
    (0.0, SeverityLevel.NONE),
    (0.2, SeverityLevel.LOW),
    (0.45, SeverityLevel.MEDIUM),
    (0.7, SeverityLevel.HIGH),
    (0.9, SeverityLevel.CRITICAL),
)


def score_to_severity(score: float) -> SeverityLevel:
    severity = SeverityLevel.NONE
    for threshold, level in DEFAULT_SEVERITY_BANDS:
        if score >= threshold:
            severity = level
    return severity
