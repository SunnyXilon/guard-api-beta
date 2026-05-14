from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.taxonomy import DecisionAction, ModerationCategory, SeverityLevel

MIN_POLICY_THRESHOLD = 0.05


class ContentMetadata(BaseModel):
    content_id: Optional[str] = None
    user_id: Optional[str] = None
    language: str = "en"
    channel: str = "comment"
    region: str = "global"


class TextModerationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    tenant_id: Optional[str] = None
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)


class ImageModerationRequest(BaseModel):
    image_url: Optional[str] = None
    image_caption: str = ""
    detected_objects: List[str] = Field(default_factory=list)
    ocr_text: str = ""
    tenant_id: Optional[str] = None
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)


class AudioModerationRequest(BaseModel):
    audio_url: Optional[str] = None
    transcript_hint: str = ""
    tenant_id: Optional[str] = None
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)


class VideoFrame(BaseModel):
    timestamp_ms: int
    description: str = ""
    ocr_text: str = ""
    detected_objects: List[str] = Field(default_factory=list)


class VideoModerationRequest(BaseModel):
    video_url: Optional[str] = None
    transcript_hint: str = ""
    frames: List[VideoFrame] = Field(default_factory=list)
    tenant_id: Optional[str] = None
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)


class CategoryResult(BaseModel):
    category: ModerationCategory
    score: float
    severity: SeverityLevel
    reasons: List[str] = Field(default_factory=list)


class ModerationDecision(BaseModel):
    action: DecisionAction
    triggered_categories: List[ModerationCategory] = Field(default_factory=list)
    matched_policy_labels: List[str] = Field(default_factory=list)
    explanation: str


class ScoreMetadata(BaseModel):
    fast_model: str
    fallback_model: str
    policy_version: str
    latency_ms: float
    modality: str
    extracted_text: Optional[str] = None


class TextModerationResponse(BaseModel):
    request_id: str
    tenant_id: str
    category_scores: List[CategoryResult]
    decision: ModerationDecision
    metadata: ScoreMetadata
    review_case_id: Optional[str] = None


class MultimodalModerationResponse(BaseModel):
    request_id: str
    tenant_id: str
    category_scores: List[CategoryResult]
    decision: ModerationDecision
    metadata: ScoreMetadata
    modality_details: Dict[str, object] = Field(default_factory=dict)
    review_case_id: Optional[str] = None


class PolicyOverride(BaseModel):
    review: Optional[float] = Field(default=None, ge=MIN_POLICY_THRESHOLD, le=1.0)
    block: Optional[float] = Field(default=None, ge=MIN_POLICY_THRESHOLD, le=1.0)

    @model_validator(mode="after")
    def validate_order(self):
        if self.review is not None and self.block is not None and self.review > self.block:
            raise ValueError("review threshold must be less than or equal to block threshold")
        return self


class TenantPolicyConfig(BaseModel):
    tenant_id: str
    labels: List[str]
    thresholds: Dict[ModerationCategory, PolicyOverride] = Field(default_factory=dict)
    review_enabled: bool = True
    protected_mode: bool = False


class TenantPolicyUpdate(BaseModel):
    thresholds: Dict[ModerationCategory, PolicyOverride] = Field(default_factory=dict)
    review_enabled: Optional[bool] = None
    protected_mode: Optional[bool] = None


class ModerationDecisionItem(BaseModel):
    request_id: str
    modality: str
    action: DecisionAction
    triggered_categories: List[ModerationCategory] = Field(default_factory=list)
    explanation: str
    content_preview: str
    fallback_model: str = "not_used"
    created_at: datetime


class UsageSummary(BaseModel):
    month: str
    total_requests: int
    monthly_quota: int
    remaining_requests: int
    plan_name: str
    billing_scope: str = "account"
    allow: int = 0
    review: int = 0
    block: int = 0


class AuthenticatedTenant(BaseModel):
    tenant_id: str
    tenant_name: str
    api_key_id: str
    scopes: List[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    tenant: AuthenticatedTenant
    usage: UsageSummary
    recent_decisions: List[ModerationDecisionItem]
    policy: TenantPolicyConfig


class ApiKeyInfo(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: List[str] = Field(default_factory=lambda: ["moderation"])

    @model_validator(mode="after")
    def validate_scopes(self):
        allowed = {"moderation", "dashboard", "policy:write"}
        requested = set(self.scopes)
        if not requested:
            raise ValueError("at least one scope is required")
        if not requested.issubset(allowed):
            raise ValueError(f"allowed scopes are: {', '.join(sorted(allowed))}")
        if "policy:write" in requested and "dashboard" not in requested:
            raise ValueError("policy:write requires dashboard scope")
        return self


class ApiKeyCreated(ApiKeyInfo):
    api_key: str


class ApiKeyUsage(ApiKeyInfo):
    total_requests: int = 0


class DashboardSession(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant: AuthenticatedTenant


class WorkspaceInfo(BaseModel):
    tenant_id: str
    tenant_name: str
    billing_scope: str = "account"
    plan_name: str
    monthly_quota: int
    subscription_status: str
    created_at: datetime


class TenantOnboardingRequest(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=120)


class WorkspaceRenameRequest(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=120)


class TenantOnboardingResponse(BaseModel):
    dashboard_session: DashboardSession
    moderation_key: ApiKeyCreated


class BillingCheckoutRequest(BaseModel):
    plan_name: str = Field(min_length=2, max_length=80)


class BillingScopeUpdate(BaseModel):
    billing_scope: str = Field(pattern="^(account|workspace)$")


class BillingCheckoutResponse(BaseModel):
    checkout_url: str


class BillingPortalResponse(BaseModel):
    portal_url: str


class BillingStatus(BaseModel):
    billing_scope: str = "account"
    plan_name: str
    monthly_quota: int
    subscription_status: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class ReviewCase(BaseModel):
    case_id: str
    request_id: str
    tenant_id: str
    submitted_text: str
    action: DecisionAction
    priority: int
    status: str = "open"
    assignee: Optional[str] = None
    category_scores: List[CategoryResult]
    notes: List[str] = Field(default_factory=list)
    created_at: datetime


class ReviewCaseUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=1000)
    assignee: Optional[str] = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_update(self):
        allowed_statuses = {"open", "in_review", "resolved", "dismissed"}
        if self.status is not None and self.status not in allowed_statuses:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed_statuses))}")
        if self.status is None and not (self.note or "").strip() and self.assignee is None:
            raise ValueError("status, note, or assignee is required")
        return self


class ConnectedAccount(BaseModel):
    id: str
    tenant_id: str
    platform: str
    provider_account_id: str
    display_name: str
    account_type: str = "business"
    status: str = "connected"
    scopes: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ConnectedAccountCreate(BaseModel):
    platform: str = Field(min_length=2, max_length=40)
    provider_account_id: str = Field(min_length=2, max_length=160)
    display_name: str = Field(min_length=2, max_length=200)
    account_type: str = Field(default="business", min_length=2, max_length=60)
    scopes: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_platform(self):
        self.platform = self.platform.strip().lower()
        self.provider_account_id = self.provider_account_id.strip()
        self.display_name = self.display_name.strip()
        self.account_type = self.account_type.strip().lower()
        return self


class MetaOAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class SocialEvent(BaseModel):
    id: str
    tenant_id: str
    connected_account_id: Optional[str] = None
    moderation_request_id: Optional[str] = None
    platform: str
    external_event_id: Optional[str] = None
    source_type: str
    actor_handle: Optional[str] = None
    content_text: str
    content_url: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    decision_action: DecisionAction
    triggered_categories: List[ModerationCategory] = Field(default_factory=list)
    status: str = "open"
    raw_payload: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    last_action_at: Optional[datetime] = None


class SocialEventCreate(BaseModel):
    platform: str = Field(default="webhook", min_length=2, max_length=40)
    connected_account_id: Optional[str] = None
    external_event_id: Optional[str] = Field(default=None, max_length=200)
    source_type: str = Field(default="comment", min_length=2, max_length=40)
    actor_handle: Optional[str] = Field(default=None, max_length=160)
    content_text: str = Field(min_length=1, max_length=5000)
    content_url: Optional[str] = Field(default=None, max_length=500)
    media_urls: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, object] = Field(default_factory=dict)
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)

    @model_validator(mode="after")
    def normalize_event(self):
        self.platform = self.platform.strip().lower()
        self.source_type = self.source_type.strip().lower()
        if self.external_event_id is not None:
            self.external_event_id = self.external_event_id.strip() or None
        if self.actor_handle is not None:
            self.actor_handle = self.actor_handle.strip() or None
        return self


class SocialActionRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class SocialAction(BaseModel):
    id: str
    tenant_id: str
    social_event_id: str
    action_type: str
    status: str
    actor_type: str
    external_action_id: Optional[str] = None
    payload: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime

