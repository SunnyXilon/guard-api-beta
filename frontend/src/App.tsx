import { AnimatePresence, motion } from "framer-motion";
import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/react";
import {
  Activity,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  BookOpen,
  ChevronDown,
  CheckCircle2,
  Code2,
  Copy,
  CreditCard,
  Database,
  ExternalLink,
  FileAudio,
  Film,
  LayoutDashboard,
  Gauge,
  Image as ImageIcon,
  LineChart,
  LockKeyhole,
  LogIn,
  Moon,
  Radar,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  UploadCloud,
  UserRound,
  Workflow,
  XCircle,
  Trash2,
  Video,
} from "lucide-react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Textarea } from "./components/ui/textarea";
import { cn } from "./lib/utils";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TEXT_API_KEY = import.meta.env.VITE_DEMO_TEXT_API_KEY ?? "";
const IMAGE_API_KEY = import.meta.env.VITE_DEMO_IMAGE_API_KEY ?? "";
const DASHBOARD_DEMO_API_KEY = import.meta.env.VITE_DEMO_ADMIN_API_KEY ?? "";
const LAST_WORKSPACE_STORAGE_KEY = "guard-api-last-workspace-id";

type AppProps = {
  clerkEnabled: boolean;
  clerkLoaded: boolean;
  clerkSignedIn: boolean;
  getClerkToken: () => Promise<string | null>;
};

type ModerationResult = {
  request_id: string;
  tenant_id: string;
  category_scores: Array<{
    category: string;
    score: number;
    severity: string;
    reasons: string[];
  }>;
  decision: {
    action: "allow" | "review" | "block";
    triggered_categories: string[];
    explanation: string;
  };
  metadata: {
    latency_ms: number;
    fallback_model: string;
    policy_version: string;
    extracted_text?: string | null;
  };
  modality_details?: {
    scanner_provider?: string;
    scanner_fallback_used?: boolean;
    scanner_error?: string | null;
    vision_labels?: string[];
    visual_safety_provider?: string;
    visual_safety_fallback_used?: boolean;
    visual_safety_error?: string | null;
    visual_safety_frames_scanned?: number;
    visual_safety_labels?: Array<{
      label: string;
      confidence: number;
      categories: string[];
    }>;
    safe_search?: Record<string, string>;
  };
  review_case_id?: string | null;
};

type PolicyThreshold = {
  review?: number;
  block?: number;
};

type DashboardSummary = {
  tenant: {
    tenant_id: string;
    tenant_name: string;
    api_key_id: string;
  };
  usage: {
    month: string;
    total_requests: number;
    monthly_quota: number;
    remaining_requests: number;
    plan_name: string;
    billing_scope: "account" | "workspace";
    allow: number;
    review: number;
    block: number;
  };
  recent_decisions: Array<{
    request_id: string;
    modality: string;
    action: "allow" | "review" | "block";
    triggered_categories: string[];
    explanation: string;
    content_preview: string;
    fallback_model: string;
    created_at: string;
  }>;
  policy: {
    tenant_id: string;
    labels: string[];
    thresholds: Record<string, PolicyThreshold>;
    review_enabled: boolean;
    protected_mode: boolean;
  };
};

type ApiKeyInfo = {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
};

type InferenceStatus = {
  status: "online" | "offline";
  runtime: "local" | "hosted";
  model: string;
  model_loaded: boolean;
  fallback_used: boolean;
  latency_ms: number;
  error?: string | null;
};

type ApiKeyUsage = ApiKeyInfo & {
  total_requests: number;
};

type ApiKeyCreated = ApiKeyInfo & {
  api_key: string;
};

type ReviewCase = {
  case_id: string;
  request_id: string;
  tenant_id: string;
  submitted_text: string;
  action: "allow" | "review" | "block";
  priority: number;
  status: "open" | "in_review" | "resolved" | "dismissed";
  assignee?: string | null;
  category_scores: ModerationResult["category_scores"];
  notes: string[];
  created_at: string;
};

type ConnectedAccount = {
  id: string;
  tenant_id: string;
  platform: string;
  provider_account_id: string;
  display_name: string;
  account_type: string;
  status: string;
  scopes: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type SocialEvent = {
  id: string;
  tenant_id: string;
  connected_account_id?: string | null;
  moderation_request_id?: string | null;
  platform: string;
  external_event_id?: string | null;
  source_type: string;
  actor_handle?: string | null;
  content_text: string;
  content_url?: string | null;
  media_urls: string[];
  decision_action: "allow" | "review" | "block";
  triggered_categories: string[];
  status: "open" | "in_review" | "hidden" | "deleted" | "allowed" | "blocked_user" | "reviewed";
  raw_payload: Record<string, unknown>;
  created_at: string;
  last_action_at?: string | null;
};

type SocialActionType = "hide" | "delete" | "allow" | "block-user" | "mark-reviewed";

type SocialEventCreateInput = {
  connected_account_id?: string;
  platform: string;
  external_event_id?: string;
  source_type: string;
  actor_handle?: string;
  content_text: string;
};

type SocialActionResponse = {
  status: string;
  payload?: {
    platform?: {
      platform_call?: string;
      error?: string;
    };
  };
};

type MetaOAuthStartResponse = {
  authorization_url: string;
  state: string;
};

type BillingStatus = {
  billing_scope: "account" | "workspace";
  plan_name: string;
  monthly_quota: number;
  subscription_status: string;
  stripe_customer_id?: string | null;
  stripe_subscription_id?: string | null;
};

type DashboardSession = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  tenant: DashboardSummary["tenant"];
};

type WorkspaceInfo = {
  tenant_id: string;
  tenant_name: string;
  billing_scope: "account" | "workspace";
  plan_name: string;
  monthly_quota: number;
  subscription_status: string;
  created_at: string;
};

type TenantOnboardingResponse = {
  dashboard_session: DashboardSession;
  moderation_key: ApiKeyCreated;
};

type DemoMode = "text" | "image" | "audio" | "video";

type TextSample = {
  label: string;
  text: string;
  language: string;
};

const sampleTexts: TextSample[] = [
  {
    label: "Marketplace scam",
    text: "Guaranteed profit investment, whatsapp me for deal.",
    language: "en",
  },
  {
    label: "Safe feedback",
    text: "Thanks for the quick delivery. The product looks great.",
    language: "en",
  },
  {
    label: "Hindi scam",
    text: "गारंटीड प्रॉफिट मिलेगा, व्हाट्सएप पर पैसे भेजो.",
    language: "hi",
  },
  {
    label: "Hinglish threat",
    text: "main tujhe maar dunga, tu bach nahi payega",
    language: "hi-Latn",
  },
];

const audioSamples: Array<{ label: string; transcript: string }> = [
  {
    label: "Harassment",
    transcript: "You are worthless and I will find you after school.",
  },
  {
    label: "Scam",
    transcript: "Send your OTP and bank details now to unlock your account.",
  },
  {
    label: "Sexual",
    transcript: "Send nude pics right now.",
  },
  {
    label: "Self-harm",
    transcript: "I want to kill myself tonight.",
  },
  {
    label: "Illegal",
    transcript: "Buy cocaine and pills for cash only.",
  },
];

const nodeExpressTemplate = `import express from "express";

const app = express();
app.use(express.json());

const GUARD_API_URL = process.env.GUARD_API_URL;
const GUARD_API_KEY = process.env.GUARD_API_KEY;

app.post("/messages", async (req, res) => {
  const response = await fetch(\`\${GUARD_API_URL}/moderate/text\`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": GUARD_API_KEY
    },
    body: JSON.stringify({
      text: req.body.text,
      metadata: {
        content_id: req.body.messageId,
        user_id: req.body.userId,
        channel: "chat"
      }
    })
  });

  const moderation = await response.json();

  if (moderation.decision.action === "block") {
    return res.status(422).json({ status: "blocked", request_id: moderation.request_id });
  }

  if (moderation.decision.action === "review") {
    return res.status(202).json({ status: "pending_review", request_id: moderation.request_id });
  }

  return res.status(201).json({ status: "published", request_id: moderation.request_id });
});

app.listen(9000);`;

const nodeAudioTemplate = `const form = new FormData();
form.set("audio", audioBlob, "voice-note.mp3");
form.set("transcript_hint", "optional fallback transcript");
form.set("channel", "voice_message");

const response = await fetch(\`\${process.env.GUARD_API_URL}/moderate/audio\`, {
  method: "POST",
  headers: {
    "X-API-Key": process.env.GUARD_API_KEY
  },
  body: form
});

const moderation = await response.json();

if (moderation.decision.action === "allow") publishAudio();
if (moderation.decision.action === "review") holdForModerator();
if (moderation.decision.action === "block") rejectAudio();`;

const nodeImageTemplate = `const form = new FormData();
form.set("image", imageBlob, "upload.jpg");
form.set("image_caption", "caption or alt text from your app");
form.set("ocr_text", "text already extracted by your app, optional");
form.set("channel", "image_upload");

const response = await fetch(\`\${process.env.GUARD_API_URL}/moderate/image\`, {
  method: "POST",
  headers: {
    "X-API-Key": process.env.GUARD_API_KEY
  },
  body: form
});

const moderation = await response.json();

if (moderation.decision.action === "allow") publishImage();
if (moderation.decision.action === "review") holdForModerator();
if (moderation.decision.action === "block") rejectImage();`;

const nodeVideoTemplate = `const form = new FormData();
form.set("video", videoBlob, "upload.mp4");
form.set("transcript_hint", "optional speech transcript or caption");
form.set("frame_description", "short description from your video pipeline");
form.set("ocr_text", "visible text detected in sampled frames");
form.set("detected_objects", "phone,cash");
form.set("channel", "video_upload");

const response = await fetch(\`\${process.env.GUARD_API_URL}/moderate/video\`, {
  method: "POST",
  headers: {
    "X-API-Key": process.env.GUARD_API_KEY
  },
  body: form
});

const moderation = await response.json();

if (moderation.decision.action === "allow") publishVideo();
if (moderation.decision.action === "review") holdForModerator();
if (moderation.decision.action === "block") rejectVideo();`;

const pythonFastApiTemplate = `import os
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

GUARD_API_URL = os.environ["GUARD_API_URL"]
GUARD_API_KEY = os.environ["GUARD_API_KEY"]

@app.post("/messages")
def create_message(payload: dict):
    response = requests.post(
        f"{GUARD_API_URL}/moderate/text",
        headers={"X-API-Key": GUARD_API_KEY},
        json={
            "text": payload["text"],
            "metadata": {
                "content_id": payload.get("message_id"),
                "user_id": payload.get("user_id"),
                "channel": "chat",
            },
        },
        timeout=10,
    )
    response.raise_for_status()
    moderation = response.json()

    if moderation["decision"]["action"] == "block":
        raise HTTPException(status_code=422, detail="Blocked by moderation.")

    if moderation["decision"]["action"] == "review":
        return {"status": "pending_review", "request_id": moderation["request_id"]}

    return {"status": "published", "request_id": moderation["request_id"]}`;

const pythonAudioTemplate = `with open("voice-note.mp3", "rb") as audio_file:
    response = requests.post(
        f"{GUARD_API_URL}/moderate/audio",
        headers={"X-API-Key": GUARD_API_KEY},
        files={"audio": ("voice-note.mp3", audio_file, "audio/mpeg")},
        data={
            "transcript_hint": "optional fallback transcript",
            "channel": "voice_message",
        },
        timeout=30,
    )

moderation = response.json()

if moderation["decision"]["action"] == "allow":
    publish_audio()
elif moderation["decision"]["action"] == "review":
    hold_for_moderator()
else:
    reject_audio()`;

const pythonImageTemplate = `with open("upload.jpg", "rb") as image_file:
    response = requests.post(
        f"{GUARD_API_URL}/moderate/image",
        headers={"X-API-Key": GUARD_API_KEY},
        files={"image": ("upload.jpg", image_file, "image/jpeg")},
        data={
            "image_caption": "caption or alt text from your app",
            "ocr_text": "text already extracted by your app, optional",
            "channel": "image_upload",
        },
        timeout=30,
    )

moderation = response.json()

if moderation["decision"]["action"] == "allow":
    publish_image()
elif moderation["decision"]["action"] == "review":
    hold_for_moderator()
else:
    reject_image()`;

const pythonVideoTemplate = `with open("upload.mp4", "rb") as video_file:
    response = requests.post(
        f"{GUARD_API_URL}/moderate/video",
        headers={"X-API-Key": GUARD_API_KEY},
        files={"video": ("upload.mp4", video_file, "video/mp4")},
        data={
            "transcript_hint": "optional speech transcript or caption",
            "frame_description": "short description from your video pipeline",
            "ocr_text": "visible text detected in sampled frames",
            "detected_objects": "phone,cash",
            "channel": "video_upload",
        },
        timeout=60,
    )

moderation = response.json()

if moderation["decision"]["action"] == "allow":
    publish_video()
elif moderation["decision"]["action"] == "review":
    hold_for_moderator()
else:
    reject_video()`;

const productStats = [
  { label: "Modalities", value: "4", detail: "Text, image, audio, video" },
  { label: "Decision path", value: "<350ms", detail: "Fast local scoring first" },
  { label: "Tenant modes", value: "3", detail: "Default, kids-safe, marketplace" },
];

const platformBlocks = [
  {
    icon: ShieldCheck,
    title: "Real-time moderation",
    body: "Score live user content for scams, toxicity, harassment, hate, violence, child safety, PII, and illegal activity.",
  },
  {
    icon: Workflow,
    title: "Policy-aware decisions",
    body: "Each tenant gets independent thresholds, labels, API keys, review behavior, and enforcement outcomes.",
  },
  {
    icon: Database,
    title: "Operational memory",
    body: "Every request writes durable moderation results, review cases, and audit events for follow-up workflows.",
  },
];

const pipeline = [
  "Authenticate tenant key",
  "Score risk signals",
  "Fuse inference output",
  "Apply policy",
  "Persist audit trail",
];

type GuideAudience = "individuals" | "organizations" | "developers" | "nontechnical";

type HowToUsePath = {
  id: GuideAudience;
  label: string;
  title: string;
  summary: string;
  icon: typeof BarChart3;
  steps: string[];
  useCases: string[];
  dashboardActions: string[];
};

const howToUsePaths: HowToUsePath[] = [
  {
    id: "individuals",
    label: "Individuals",
    title: "Use Guard API as a solo creator or small operator",
    summary:
      "Start with one workspace, scan risky messages or uploads, and use the review queue when a decision needs a human check.",
    icon: UserRound,
    steps: [
      "Create one workspace for your app, page, shop, or community.",
      "Run the live demo to understand allow, review, and block decisions.",
      "Create a moderation key and test content from the Integration center.",
      "Check Marketplace and Review cases after every test request.",
      "Tune policy thresholds only after seeing real examples.",
    ],
    useCases: ["Marketplace listings", "Creator comments", "Contact forms", "Community posts"],
    dashboardActions: ["Playground", "Marketplace", "Integration center", "Review cases", "Policy thresholds"],
  },
  {
    id: "organizations",
    label: "Organizations",
    title: "Roll it out across a team or business unit",
    summary:
      "Separate workspaces by product or client, keep API keys scoped, route uncertain content to reviewers, and track credits by billing scope.",
    icon: Workflow,
    steps: [
      "Create separate workspaces for production, testing, or each client.",
      "Generate dedicated API keys for each backend integration.",
      "Define who handles review cases and what resolved means.",
      "Set billing scope to shared account or separate workspace billing.",
      "Review recent decisions and audit trails before policy changes.",
    ],
    useCases: ["Multi-brand moderation", "Support inbox triage", "Marketplace trust teams", "Agency client work"],
    dashboardActions: ["Workspaces", "API keys", "Review cases", "Billing"],
  },
  {
    id: "developers",
    label: "Developers",
    title: "Integrate Guard API into an app or backend",
    summary:
      "Keep keys server-side, call moderation endpoints before publishing content, and map decisions to product actions.",
    icon: Code2,
    steps: [
      "Create a moderation API key and store it in your server environment.",
      "Call /moderate/text or /moderate/image before content is published.",
      "Treat allow, review, and block as product states in your backend.",
      "Store request_id with your own content record for auditability.",
      "Sign connector webhook events with HMAC when using inbound events.",
    ],
    useCases: ["Chat moderation", "Upload scanning", "Listing submission checks", "Webhook-based social inbox"],
    dashboardActions: ["Playground", "Integration center", "API docs", "API keys", "Review cases"],
  },
  {
    id: "nontechnical",
    label: "Non-technical",
    title: "Operate moderation without writing code",
    summary:
      "Use the dashboard to understand risk, review uncertain content, connect inbox sources when available, and adjust policy with clear thresholds.",
    icon: ShieldCheck,
    steps: [
      "Open Marketplace to see recent allowed, reviewed, and blocked content.",
      "Use Review cases to start, resolve, dismiss, or assign uncertain items.",
      "Use Social inbox to test comments, DMs, emails, forms, or webhook messages.",
      "Use Policy thresholds to make moderation stricter or more relaxed.",
      "Ask a developer only when an API key, webhook, or production setup is needed.",
    ],
    useCases: ["Daily safety review", "Comment moderation", "Policy tuning", "Escalating risky content"],
    dashboardActions: ["Playground", "Marketplace", "Social inbox", "Review cases", "Policy thresholds"],
  },
];

const publicFaqs = [
  {
    question: "What does Guard API moderate?",
    answer:
      "Guard API scans text, images, audio, and video for spam, scams, harassment, hate speech, violence, sexual content, self-harm, child safety, PII leakage, and illegal activity risk.",
  },
  {
    question: "Can it work with my own app or website?",
    answer:
      "Yes. Start with the direct API for apps, websites, forms, chat, uploads, and backend workflows. Your system sends content to Guard API and receives allow, review, or block decisions.",
  },
  {
    question: "Can it moderate Instagram or Facebook?",
    answer:
      "The Social Inbox supports Meta OAuth connection work. Real comment hiding or deletion requires a verified Meta app, approved permissions, and a connected Facebook Page or Instagram professional account.",
  },
  {
    question: "What happens to risky content?",
    answer:
      "Low-risk content is allowed, uncertain content can go to review, and high-risk content can be blocked. Teams can tune thresholds per policy category from the dashboard.",
  },
  {
    question: "Do users need to train a model?",
    answer:
      "No. Guard API ships with moderation rules, policy thresholds, and local safety scoring. You can improve results over time by adding domain-specific labels and review feedback.",
  },
  {
    question: "Is it ready for production deployment?",
    answer:
      "The core moderation API and dashboard are in place, but production use still needs real secrets, a production database, billing setup, platform app approval where needed, and deployment hardening.",
  },
  {
    question: "Is a mobile app available?",
    answer:
      "The web dashboard is the current product surface. A mobile app is planned as an upcoming update so creators and teams can monitor moderation alerts, review cases, and social inbox activity from their phone.",
  },
];

const previewDashboard: DashboardSummary = {
  tenant: {
    tenant_id: "demo_marketplace",
    tenant_name: "Marketplace preview",
    api_key_id: "key_demo_preview",
  },
  usage: {
    month: "2026-05",
    total_requests: 0,
    monthly_quota: 10,
    remaining_requests: 10,
    plan_name: "Preview",
    billing_scope: "account",
    allow: 0,
    review: 0,
    block: 0,
  },
  recent_decisions: [],
  policy: {
    tenant_id: "demo_marketplace",
    labels: ["marketplace", "text", "image"],
    thresholds: {
      harassment: { review: 0.45, block: 0.75 },
      hate_speech: { review: 0.4, block: 0.7 },
      scam: { review: 0.35, block: 0.65 },
      violence: { review: 0.42, block: 0.72 },
    },
    review_enabled: true,
    protected_mode: true,
  },
};

const previewApiKeys: ApiKeyInfo[] = [
  {
    id: "demo_key_active",
    name: "preview-webhook",
    key_prefix: "rtcm_demo",
    scopes: ["moderation"],
    is_active: true,
    created_at: "2026-05-11T08:00:00Z",
    last_used_at: "2026-05-11T08:40:00Z",
  },
];

const previewApiKeyUsage: ApiKeyUsage[] = previewApiKeys.map((key) => ({ ...key, total_requests: 0 }));

const previewBillingStatus: BillingStatus = {
  billing_scope: "account",
  plan_name: "Preview",
  monthly_quota: 10,
  subscription_status: "preview",
};

const billingPlans = [
  {
    name: "starter",
    price: "$15",
    cadence: "month",
    quota: 3_000,
    audience: "For early apps testing real moderation traffic",
    overage: "Includes up to 300 image scans if used only for images",
    trial: "15-day free trial",
    features: ["Unlimited workspaces", "3,000 moderation credits", "Text, image, audio, and video modes", "Basic review queue"],
  },
  {
    name: "growth",
    price: "$29",
    cadence: "month",
    quota: 10_000,
    audience: "For small production marketplaces and communities",
    overage: "Includes up to 1,000 image scans if used only for images",
    features: ["Unlimited workspaces", "10,000 moderation credits", "Policy threshold controls", "Email support"],
    badge: "Most teams",
  },
  {
    name: "scale",
    price: "$69",
    cadence: "month",
    quota: 20_000,
    audience: "For higher-volume trust operations",
    overage: "Includes up to 2,000 image scans if used only for images",
    features: ["Unlimited workspaces", "20,000 moderation credits", "Audit-ready activity logs", "Priority support"],
  },
];

const legalPages = {
  "/terms": {
    title: "Terms of Service",
    updated: "May 14, 2026",
    sections: [
      ["Product use", "Guard API is a moderation API and dashboard for business use. Customers are responsible for how they configure policies, handle user appeals, and apply decisions in their own products."],
      ["Accounts and keys", "Customers must keep API keys and dashboard sessions secure, use server-side integrations for moderation keys, and promptly rotate any key that may be exposed."],
      ["Billing", "Paid plans renew monthly unless cancelled. Usage limits, trial periods, overage handling, and available features are shown on the pricing and billing screens."],
      ["Service limits", "The service may reject requests that exceed credit quota, rate limits, file-size limits, unsupported media types, or acceptable-use restrictions."],
      ["No legal advice", "Moderation decisions are risk signals and workflow recommendations. Customers remain responsible for legal compliance and final enforcement choices."],
    ],
  },
  "/privacy": {
    title: "Privacy Policy",
    updated: "May 14, 2026",
    sections: [
      ["Data processed", "The service processes submitted text, image metadata, uploaded media where enabled, account information, API keys, policy settings, audit events, and billing identifiers."],
      ["Purpose", "Data is used to score content, explain decisions, maintain review queues, enforce credits, secure the service, provide support, and improve reliability."],
      ["Subprocessors", "Production deployments may use hosting, database, authentication, billing, monitoring, and optional image-scanning providers configured by the operator."],
      ["Customer control", "Customers can rotate keys, delete workspaces, resolve review cases, and request deletion or export through support."],
    ],
  },
  "/refund": {
    title: "Refund Policy",
    updated: "May 14, 2026",
    sections: [
      ["Trials", "Starter plans can include a trial period when configured in Stripe. Trial users can cancel before the trial ends."],
      ["Monthly subscriptions", "Cancellations stop future renewals. Partial-month refunds are reviewed case by case for duplicate charges, service outages, or accidental upgrades."],
      ["How to request", "Send the workspace name, billing email, charge date, and reason to support. Approved refunds are returned through the original payment method."],
    ],
  },
  "/acceptable-use": {
    title: "Acceptable Use Policy",
    updated: "May 14, 2026",
    sections: [
      ["Allowed use", "Use Guard API to detect, review, and reduce spam, fraud, harassment, sexual content, violence, and other policy risks in legitimate products."],
      ["Prohibited use", "Do not use the service to build surveillance systems, evade platform rules, classify protected traits for discriminatory decisions, or process illegal content except for defensive moderation workflows."],
      ["Abuse response", "Workspaces may be suspended for credential sharing, attacks, excessive automated abuse, illegal use, or attempts to extract models or bypass rate limits."],
    ],
  },
  "/data-retention": {
    title: "Moderation Data Retention",
    updated: "May 14, 2026",
    sections: [
      ["Default retention", "Moderation requests, decisions, review cases, and audit events are retained while the workspace is active so customers can investigate decisions and usage."],
      ["Minimization", "Production logging should avoid raw customer content outside the primary database. External monitoring should receive request IDs, status, latency, and error metadata only."],
      ["Deletion", "Workspace deletion deactivates the workspace and stops its API keys. Production operators should define a backend deletion/export process before public launch."],
    ],
  },
} satisfies Record<string, { title: string; updated: string; sections: Array<[string, string]> }>;

export function App({ clerkEnabled, clerkLoaded, clerkSignedIn, getClerkToken }: AppProps) {
  const [path, setPath] = useState(() => window.location.pathname);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const savedTheme = window.localStorage.getItem("guard-api-theme");
    if (savedTheme === "light" || savedTheme === "dark") {
      return savedTheme;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const [text, setText] = useState(sampleTexts[0].text);
  const [textLanguage, setTextLanguage] = useState(sampleTexts[0].language);
  const [result, setResult] = useState<ModerationResult | null>(null);
  const [error, setError] = useState("");
  const [demoMode, setDemoMode] = useState<DemoMode>("text");
  const [textLoading, setTextLoading] = useState(false);
  const [imageLoading, setImageLoading] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [videoLoading, setVideoLoading] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioTranscript, setAudioTranscript] = useState("I will find you and you deserve pain.");
  const [videoTranscript, setVideoTranscript] = useState("");
  const [videoFrameDescription, setVideoFrameDescription] = useState("");
  const [videoOcrText, setVideoOcrText] = useState("");
  const [videoObjects, setVideoObjects] = useState("");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [dashboardApiKey, setDashboardApiKey] = useState(() => {
    return DASHBOARD_DEMO_API_KEY;
  });
  const [dashboardToken, setDashboardToken] = useState(() => window.sessionStorage.getItem("guard-api-dashboard-token") ?? "");
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [policyDraft, setPolicyDraft] = useState<Record<string, PolicyThreshold>>({});
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState("");
  const [dashboardSaved, setDashboardSaved] = useState("");
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [apiKeyUsage, setApiKeyUsage] = useState<ApiKeyUsage[]>([]);
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [newKeyName, setNewKeyName] = useState("server-moderation-key");
  const [createdApiKey, setCreatedApiKey] = useState("");
  const [workspaceName, setWorkspaceName] = useState("Marketplace");
  const [workspaceRename, setWorkspaceRename] = useState("");
  const [workspaces, setWorkspaces] = useState<WorkspaceInfo[]>([]);
  const [onboardingModerationKey, setOnboardingModerationKey] = useState("");
  const [workspaceShieldTenant, setWorkspaceShieldTenant] = useState("");
  const [clerkWorkspaceChecked, setClerkWorkspaceChecked] = useState(false);
  const [reviewCases, setReviewCases] = useState<ReviewCase[]>([]);
  const [connectedAccounts, setConnectedAccounts] = useState<ConnectedAccount[]>([]);
  const [socialEvents, setSocialEvents] = useState<SocialEvent[]>([]);
  const [caseNotes, setCaseNotes] = useState<Record<string, string>>({});
  const [dashboardPreview, setDashboardPreview] = useState<DashboardSummary>(previewDashboard);
  const [previewKeyUsage, setPreviewKeyUsage] = useState<ApiKeyUsage[]>(previewApiKeyUsage);
  const [previewReviewCasesState, setPreviewReviewCasesState] = useState<ReviewCase[]>([]);

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("guard-api-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!clerkEnabled || !clerkLoaded) {
      return;
    }
    if (!clerkSignedIn) {
      setDashboard(null);
      setPolicyDraft({});
      setApiKeys([]);
      setApiKeyUsage([]);
      setBillingStatus(null);
      setReviewCases([]);
      setDashboardToken("");
      setDashboardError("");
      setDashboardSaved("");
      setCreatedApiKey("");
      setOnboardingModerationKey("");
      setWorkspaces([]);
      setWorkspaceRename("");
      setWorkspaceShieldTenant("");
      setClerkWorkspaceChecked(false);
      window.sessionStorage.removeItem("guard-api-dashboard-token");
    }
  }, [clerkEnabled, clerkLoaded, clerkSignedIn]);

  useEffect(() => {
    if (
      !clerkEnabled ||
      !clerkLoaded ||
      !clerkSignedIn ||
      path !== "/dashboard" ||
      dashboard ||
      dashboardLoading ||
      clerkWorkspaceChecked
    ) {
      return;
    }
    void loadDashboardFromClerk();
  }, [clerkEnabled, clerkLoaded, clerkSignedIn, path, dashboard, dashboardLoading, clerkWorkspaceChecked]);

  useEffect(() => {
    if (!imageFile) {
      setImagePreview("");
      return;
    }
    const previewUrl = URL.createObjectURL(imageFile);
    setImagePreview(previewUrl);
    return () => URL.revokeObjectURL(previewUrl);
  }, [imageFile]);

  const topScores = useMemo(() => {
    return [...(result?.category_scores ?? [])].sort((a, b) => b.score - a.score).slice(0, 4);
  }, [result]);

  const thresholdRows = useMemo(() => {
    return Object.entries(policyDraft).sort(([left], [right]) => left.localeCompare(right));
  }, [policyDraft]);

  async function runModeration(nextText = text, nextLanguage = textLanguage) {
    setDemoMode("text");
    setText(nextText);
    setTextLanguage(nextLanguage);
    if (!TEXT_API_KEY) {
      setError("Text demo API key is not configured.");
      return;
    }
    setTextLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/moderate/text`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": TEXT_API_KEY,
        },
        body: JSON.stringify({
          text: nextText,
          metadata: {
            channel: "landing_demo",
            region: "global",
            language: nextLanguage,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }

      const payload = (await response.json()) as ModerationResult;
      setResult(payload);
      recordPreviewModeration(payload, "text", nextText);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to reach Guard API.");
    } finally {
      setTextLoading(false);
    }
  }

  async function runImageModeration() {
    setDemoMode("image");
    if (!IMAGE_API_KEY) {
      setError("Image demo API key is not configured.");
      return;
    }
    if (!imageFile) {
      setError("Choose an image first.");
      return;
    }

    setImageLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("image", imageFile);
      formData.append("channel", "landing_image_upload");
      formData.append("region", "global");

      const response = await fetch(`${API_BASE}/moderate/image`, {
        method: "POST",
        headers: {
          "X-API-Key": IMAGE_API_KEY,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }

      const payload = (await response.json()) as ModerationResult;
      setResult(payload);
      recordPreviewModeration(payload, "image", imageFile.name);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to scan image.");
    } finally {
      setImageLoading(false);
    }
  }

  async function runAudioModeration() {
    setDemoMode("audio");
    if (!TEXT_API_KEY) {
      setError("Audio demo API key is not configured.");
      return;
    }
    if (!audioFile && !audioTranscript.trim()) {
      setError("Upload audio or add a transcript first.");
      return;
    }

    setAudioLoading(true);
    setError("");
    try {
      const body = audioFile
        ? (() => {
            const formData = new FormData();
            formData.append("audio", audioFile);
            if (audioTranscript.trim()) {
              formData.append("transcript_hint", audioTranscript);
            }
            formData.append("channel", "landing_audio_demo");
            formData.append("region", "global");
            formData.append("language", textLanguage);
            return formData;
          })()
        : JSON.stringify({
            transcript_hint: audioTranscript,
            metadata: {
              channel: "landing_audio_demo",
              region: "global",
              language: textLanguage,
            },
          });
      const response = await fetch(`${API_BASE}/moderate/audio`, {
        method: "POST",
        headers: audioFile
          ? { "X-API-Key": TEXT_API_KEY }
          : {
              "Content-Type": "application/json",
              "X-API-Key": TEXT_API_KEY,
            },
        body,
      });

      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }

      const payload = (await response.json()) as ModerationResult;
      setResult(payload);
      recordPreviewModeration(payload, "audio", audioFile?.name || audioTranscript);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to scan audio.");
    } finally {
      setAudioLoading(false);
    }
  }

  async function runVideoModeration() {
    setDemoMode("video");
    if (!TEXT_API_KEY) {
      setError("Video demo API key is not configured.");
      return;
    }

    const transcript = videoTranscript.trim();
    const frameDescription = videoFrameDescription.trim();
    const frameOcrText = videoOcrText.trim();
    const objects = videoObjects
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const hasFrameCues = [frameDescription, frameOcrText, objects.join(" ")].some(Boolean);
    if (!videoFile && ![transcript, frameDescription, frameOcrText, objects.join(" ")].some(Boolean)) {
      setError("Add a transcript, frame description, OCR text, or objects first.");
      return;
    }

    setVideoLoading(true);
    setError("");
    try {
      const frame = {
        timestamp_ms: 1000,
        description: frameDescription,
        ocr_text: frameOcrText,
        detected_objects: objects,
      };
      const response = videoFile
        ? await fetch(`${API_BASE}/moderate/video`, {
            method: "POST",
            headers: {
              "X-API-Key": TEXT_API_KEY,
            },
            body: (() => {
              const formData = new FormData();
              formData.append("video", videoFile);
              if (transcript) {
                formData.append("transcript_hint", transcript);
              }
              if (hasFrameCues) {
                formData.append("frames", JSON.stringify([frame]));
              }
              formData.append("channel", "landing_video_upload");
              formData.append("region", "global");
              formData.append("language", textLanguage);
              return formData;
            })(),
          })
        : await fetch(`${API_BASE}/moderate/video`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-API-Key": TEXT_API_KEY,
            },
            body: JSON.stringify({
              transcript_hint: transcript,
              frames: hasFrameCues ? [frame] : [],
              metadata: {
                channel: "landing_video_demo",
                region: "global",
                language: textLanguage,
              },
            }),
          });

      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }

      const payload = (await response.json()) as ModerationResult;
      setResult(payload);
      recordPreviewModeration(payload, "video", videoFile?.name || transcript || frameDescription || objects.join(", "));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to scan video cues.");
    } finally {
      setVideoLoading(false);
    }
  }

  function handleVideoFileChange(file: File | null) {
    setVideoFile(file);
    setVideoTranscript("");
    setVideoFrameDescription("");
    setVideoOcrText("");
    setVideoObjects("");
    setResult(null);
    setError("");
  }

  function recordPreviewModeration(payload: ModerationResult, modality: DemoMode, contentPreview: string) {
    if (dashboardPreview.usage.total_requests >= dashboardPreview.usage.monthly_quota) {
      return;
    }

    setDashboardPreview((current) => {
      if (current.usage.total_requests >= current.usage.monthly_quota) {
        return current;
      }

      const action = payload.decision.action;
      const nextTotal = current.usage.total_requests + 1;
      const nextDecision: DashboardSummary["recent_decisions"][number] = {
        request_id: payload.request_id,
        modality,
        action,
        triggered_categories: payload.decision.triggered_categories,
        explanation: payload.decision.explanation,
        content_preview: contentPreview,
        fallback_model: payload.metadata.fallback_model,
        created_at: new Date().toISOString(),
      };

      return {
        ...current,
        usage: {
          ...current.usage,
          total_requests: nextTotal,
          remaining_requests: Math.max(current.usage.monthly_quota - nextTotal, 0),
          allow: current.usage.allow + (action === "allow" ? 1 : 0),
          review: current.usage.review + (action === "review" ? 1 : 0),
          block: current.usage.block + (action === "block" ? 1 : 0),
        },
        recent_decisions: [nextDecision, ...current.recent_decisions].slice(0, 8),
      };
    });

    setPreviewKeyUsage((current) =>
      current.map((key) =>
        key.id === "demo_key_active" ? { ...key, total_requests: Math.min(key.total_requests + 1, 10) } : key,
      ),
    );

    if (payload.decision.action !== "allow") {
      const nextCase: ReviewCase = {
        case_id: `preview_case_${payload.request_id}`,
        request_id: payload.request_id,
        tenant_id: "demo_marketplace",
        submitted_text: contentPreview,
        action: payload.decision.action,
        priority: payload.decision.action === "block" ? 8 : 6,
        status: "open",
        assignee: null,
        category_scores: payload.category_scores,
        notes: ["Auto-created from the landing-page demo."],
        created_at: new Date().toISOString(),
      };
      setPreviewReviewCasesState((current) =>
        [nextCase, ...current].slice(0, 10),
      );
    }
  }

  function resetDashboardPreview() {
    setDashboardPreview(previewDashboard);
    setPreviewKeyUsage(previewApiKeyUsage);
    setPreviewReviewCasesState([]);
  }

  async function loadWorkspaces(clerkToken: string) {
    const response = await fetch(`${API_BASE}/workspaces/clerk`, {
      headers: {
        Authorization: `Bearer ${clerkToken}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Could not load workspaces: ${response.status}`);
    }
    const payload = (await response.json()) as WorkspaceInfo[];
    setWorkspaces(payload);
    return payload;
  }

  function rememberWorkspace(tenantId: string) {
    window.localStorage.setItem(LAST_WORKSPACE_STORAGE_KEY, tenantId);
  }

  function forgetWorkspace(tenantId?: string) {
    const savedTenantId = window.localStorage.getItem(LAST_WORKSPACE_STORAGE_KEY);
    if (!tenantId || savedTenantId === tenantId) {
      window.localStorage.removeItem(LAST_WORKSPACE_STORAGE_KEY);
    }
  }

  function preferredWorkspaceId(availableWorkspaces: WorkspaceInfo[]) {
    const savedTenantId = window.localStorage.getItem(LAST_WORKSPACE_STORAGE_KEY);
    if (savedTenantId && availableWorkspaces.some((workspace) => workspace.tenant_id === savedTenantId)) {
      return savedTenantId;
    }
    if (dashboard && availableWorkspaces.some((workspace) => workspace.tenant_id === dashboard.tenant.tenant_id)) {
      return dashboard.tenant.tenant_id;
    }
    return availableWorkspaces[0]?.tenant_id ?? "";
  }

  async function loadDashboard(apiKey = dashboardApiKey) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      let token = dashboardToken;
      if (!token || apiKey) {
        const sessionResponse = await fetch(`${API_BASE}/dashboard/session`, {
          method: "POST",
          headers: {
            "X-API-Key": apiKey,
          },
        });
        if (!sessionResponse.ok) {
          throw new Error(sessionResponse.status === 401 ? "Invalid admin API key." : `Session failed: ${sessionResponse.status}`);
        }
        const session = (await sessionResponse.json()) as DashboardSession;
        token = session.access_token;
        setDashboardToken(token);
        window.sessionStorage.setItem("guard-api-dashboard-token", token);
        setDashboardApiKey("");
      }

      const response = await fetch(`${API_BASE}/dashboard`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        throw new Error(response.status === 401 ? "Invalid API key." : `Guard API returned ${response.status}`);
      }
      const payload = (await response.json()) as DashboardSummary;
      setDashboard(payload);
      setPolicyDraft(payload.policy.thresholds);
      rememberWorkspace(payload.tenant.tenant_id);
      await loadApiKeys(token);
      await loadApiKeyUsage(token);
      await loadBillingStatus(token);
      await loadReviewCases(token);
      await loadSocialData(token);
    } catch (caught) {
      setDashboard(null);
      setApiKeys([]);
      setApiKeyUsage([]);
      setBillingStatus(null);
      setReviewCases([]);
      setConnectedAccounts([]);
      setSocialEvents([]);
      setDashboardToken("");
      window.sessionStorage.removeItem("guard-api-dashboard-token");
      setDashboardError(caught instanceof Error ? caught.message : "Unable to load dashboard.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function loadDashboardFromClerk() {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const clerkToken = await getClerkToken();
      if (!clerkToken) {
        throw new Error("Clerk session is not ready.");
      }

      const availableWorkspaces = await loadWorkspaces(clerkToken);
      if (!availableWorkspaces.length) {
        forgetWorkspace();
        setClerkWorkspaceChecked(true);
        return;
      }
      const activeWorkspaceId = preferredWorkspaceId(availableWorkspaces);

      const sessionResponse = await fetch(`${API_BASE}/dashboard/session/clerk?tenant_id=${encodeURIComponent(activeWorkspaceId)}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${clerkToken}`,
        },
      });
      if (sessionResponse.status === 404) {
        setClerkWorkspaceChecked(true);
        return;
      }
      if (!sessionResponse.ok) {
        throw new Error(`Clerk dashboard session failed: ${sessionResponse.status}`);
      }

      const session = (await sessionResponse.json()) as DashboardSession;
      const token = session.access_token;
      setDashboardToken(token);
      window.sessionStorage.setItem("guard-api-dashboard-token", token);
      setDashboardApiKey("");

      const response = await fetch(`${API_BASE}/dashboard`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      const payload = (await response.json()) as DashboardSummary;
      setDashboard(payload);
      setPolicyDraft(payload.policy.thresholds);
      rememberWorkspace(payload.tenant.tenant_id);
      setClerkWorkspaceChecked(true);
      await loadApiKeys(token);
      await loadApiKeyUsage(token);
      await loadBillingStatus(token);
      await loadReviewCases(token);
      await loadSocialData(token);
    } catch (caught) {
      setClerkWorkspaceChecked(true);
      setDashboardError(caught instanceof Error ? caught.message : "Unable to load your workspace.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function switchWorkspace(tenantId: string) {
    if (!tenantId || tenantId === dashboard?.tenant.tenant_id) {
      return;
    }
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    setOnboardingModerationKey("");
    setCreatedApiKey("");
    try {
      const clerkToken = await getClerkToken();
      if (!clerkToken) {
        throw new Error("Clerk session is not ready.");
      }

      const sessionResponse = await fetch(`${API_BASE}/dashboard/session/clerk?tenant_id=${encodeURIComponent(tenantId)}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${clerkToken}`,
        },
      });
      if (!sessionResponse.ok) {
        throw new Error(`Workspace switch failed: ${sessionResponse.status}`);
      }

      const session = (await sessionResponse.json()) as DashboardSession;
      const token = session.access_token;
      setDashboardToken(token);
      window.sessionStorage.setItem("guard-api-dashboard-token", token);

      const dashboardResponse = await fetch(`${API_BASE}/dashboard`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!dashboardResponse.ok) {
        throw new Error(`Guard API returned ${dashboardResponse.status}`);
      }
      const payload = (await dashboardResponse.json()) as DashboardSummary;
      setDashboard(payload);
      setPolicyDraft(payload.policy.thresholds);
      rememberWorkspace(payload.tenant.tenant_id);
      await loadWorkspaces(clerkToken);
      await loadApiKeys(token);
      await loadApiKeyUsage(token);
      await loadBillingStatus(token);
      await loadReviewCases(token);
      await loadSocialData(token);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to switch workspace.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function renameWorkspace() {
    if (!dashboard || workspaceRename.trim().length < 2) {
      return;
    }
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const clerkToken = await getClerkToken();
      if (!clerkToken) {
        throw new Error("Clerk session is not ready.");
      }

      const response = await fetch(`${API_BASE}/workspaces/clerk/${encodeURIComponent(dashboard.tenant.tenant_id)}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${clerkToken}`,
        },
        body: JSON.stringify({
          workspace_name: workspaceRename,
        }),
      });
      if (!response.ok) {
        throw new Error(`Workspace rename failed: ${response.status}`);
      }

      const updatedWorkspace = (await response.json()) as WorkspaceInfo;
      const nextDashboard = {
        ...dashboard,
        tenant: {
          ...dashboard.tenant,
          tenant_name: updatedWorkspace.tenant_name,
        },
      };
      setDashboard(nextDashboard);
      setWorkspaces((current) =>
        current.map((workspace) =>
          workspace.tenant_id === updatedWorkspace.tenant_id ? updatedWorkspace : workspace,
        ),
      );
      setWorkspaceRename("");
      setDashboardSaved("Workspace renamed.");
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to rename workspace.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function deleteWorkspace() {
    if (!dashboard) {
      return;
    }
    if (workspaces.length <= 1) {
      setDashboardError("Create another workspace before deleting this one.");
      return;
    }

    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    setOnboardingModerationKey("");
    setCreatedApiKey("");
    try {
      const clerkToken = await getClerkToken();
      if (!clerkToken) {
        throw new Error("Clerk session is not ready.");
      }

      const response = await fetch(`${API_BASE}/workspaces/clerk/${encodeURIComponent(dashboard.tenant.tenant_id)}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${clerkToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`Workspace deletion failed: ${response.status}`);
      }

      const remainingWorkspaces = await loadWorkspaces(clerkToken);
      const nextWorkspace = remainingWorkspaces[0];
      forgetWorkspace(dashboard.tenant.tenant_id);
      if (!nextWorkspace) {
        setDashboard(null);
        setDashboardToken("");
        window.sessionStorage.removeItem("guard-api-dashboard-token");
        setClerkWorkspaceChecked(true);
        return;
      }

      const sessionResponse = await fetch(`${API_BASE}/dashboard/session/clerk?tenant_id=${encodeURIComponent(nextWorkspace.tenant_id)}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${clerkToken}`,
        },
      });
      if (!sessionResponse.ok) {
        throw new Error(`Workspace switch failed: ${sessionResponse.status}`);
      }

      const session = (await sessionResponse.json()) as DashboardSession;
      const token = session.access_token;
      setDashboardToken(token);
      window.sessionStorage.setItem("guard-api-dashboard-token", token);

      const dashboardResponse = await fetch(`${API_BASE}/dashboard`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!dashboardResponse.ok) {
        throw new Error(`Guard API returned ${dashboardResponse.status}`);
      }
      const payload = (await dashboardResponse.json()) as DashboardSummary;
      setDashboard(payload);
      setPolicyDraft(payload.policy.thresholds);
      rememberWorkspace(payload.tenant.tenant_id);
      await loadApiKeys(token);
      await loadApiKeyUsage(token);
      await loadBillingStatus(token);
      await loadReviewCases(token);
      await loadSocialData(token);
      setDashboardSaved("Workspace deleted.");
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to delete workspace.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function createWorkspace() {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    setOnboardingModerationKey("");
    try {
      const clerkToken = await getClerkToken();
      if (!clerkToken) {
        throw new Error("Clerk session is not ready.");
      }
      const response = await fetch(`${API_BASE}/onboarding/tenant`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${clerkToken}`,
        },
        body: JSON.stringify({
          workspace_name: workspaceName,
        }),
      });
      if (!response.ok) {
        throw new Error(`Workspace creation failed: ${response.status}`);
      }

      const payload = (await response.json()) as TenantOnboardingResponse;
      const token = payload.dashboard_session.access_token;
      setDashboardToken(token);
      window.sessionStorage.setItem("guard-api-dashboard-token", token);
      setDashboardApiKey("");
      setClerkWorkspaceChecked(true);
      setOnboardingModerationKey(payload.moderation_key.api_key);
      setCreatedApiKey(payload.moderation_key.api_key);

      const dashboardResponse = await fetch(`${API_BASE}/dashboard`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!dashboardResponse.ok) {
        throw new Error(`Dashboard load failed: ${dashboardResponse.status}`);
      }
      const dashboardPayload = (await dashboardResponse.json()) as DashboardSummary;
      setDashboard(dashboardPayload);
      setPolicyDraft(dashboardPayload.policy.thresholds);
      rememberWorkspace(dashboardPayload.tenant.tenant_id);
      setWorkspaceShieldTenant(dashboardPayload.tenant.tenant_id);
      await loadWorkspaces(clerkToken);
      await loadApiKeys(token);
      await loadApiKeyUsage(token);
      await loadBillingStatus(token);
      await loadReviewCases(token);
      await loadSocialData(token);
      setDashboardSaved("Workspace created. Save the moderation API key shown below.");
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to create workspace.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function loadApiKeys(token = dashboardToken) {
    const response = await fetch(`${API_BASE}/api-keys`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Could not load API keys: ${response.status}`);
    }
    setApiKeys((await response.json()) as ApiKeyInfo[]);
  }

  async function loadApiKeyUsage(token = dashboardToken) {
    const response = await fetch(`${API_BASE}/api-keys/usage`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Could not load API key usage: ${response.status}`);
    }
    setApiKeyUsage((await response.json()) as ApiKeyUsage[]);
  }

  async function loadBillingStatus(token = dashboardToken) {
    const response = await fetch(`${API_BASE}/billing/status`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Could not load billing status: ${response.status}`);
    }
    setBillingStatus((await response.json()) as BillingStatus);
  }

  async function loadReviewCases(token = dashboardToken) {
    const response = await fetch(`${API_BASE}/cases`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Could not load review cases: ${response.status}`);
    }
    const payload = (await response.json()) as { cases: ReviewCase[] };
    setReviewCases(payload.cases);
  }

  async function loadSocialData(token = dashboardToken) {
    const [accountsResponse, inboxResponse] = await Promise.all([
      fetch(`${API_BASE}/connected-accounts`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }),
      fetch(`${API_BASE}/social-inbox`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }),
    ]);
    if (!accountsResponse.ok) {
      throw new Error(`Could not load connected accounts: ${accountsResponse.status}`);
    }
    if (!inboxResponse.ok) {
      throw new Error(`Could not load social inbox: ${inboxResponse.status}`);
    }
    setConnectedAccounts((await accountsResponse.json()) as ConnectedAccount[]);
    setSocialEvents((await inboxResponse.json()) as SocialEvent[]);
  }

  async function deactivateApiKey(apiKeyId: string) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/api-keys/${apiKeyId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${dashboardToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      setDashboardSaved("API key deactivated.");
      await loadApiKeys(dashboardToken);
      await loadApiKeyUsage(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to deactivate API key.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function rotateApiKey(apiKeyId: string) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    setCreatedApiKey("");
    try {
      const response = await fetch(`${API_BASE}/api-keys/${apiKeyId}/rotate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${dashboardToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      const payload = (await response.json()) as ApiKeyCreated;
      setCreatedApiKey(payload.api_key);
      setDashboardSaved("API key rotated. Copy the replacement key now; it will not be shown again.");
      await loadApiKeys(dashboardToken);
      await loadApiKeyUsage(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to rotate API key.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function updateReviewCase(caseId: string, status: ReviewCase["status"]) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/cases/${caseId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify({
          status,
          assignee: caseNotes[`${caseId}:assignee`] || undefined,
          note: caseNotes[caseId] || undefined,
        }),
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      setDashboardSaved("Review case updated.");
      setCaseNotes((current) => ({ ...current, [caseId]: "", [`${caseId}:assignee`]: "" }));
      await loadReviewCases(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to update review case.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function connectSocialAccount(account: {
    platform: string;
    provider_account_id: string;
    display_name: string;
    account_type: string;
    scopes: string[];
  }) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/connected-accounts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify(account),
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      setDashboardSaved("Connected account saved.");
      await loadSocialData(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to save connected account.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function startMetaOAuth() {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const returnUrl = `${window.location.origin}/dashboard`;
      const response = await fetch(
        `${API_BASE}/connectors/meta/oauth/start?return_url=${encodeURIComponent(returnUrl)}`,
        {
          headers: {
            Authorization: `Bearer ${dashboardToken}`,
          },
        },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || `Guard API returned ${response.status}`);
      }
      const payload = (await response.json()) as MetaOAuthStartResponse;
      window.location.assign(payload.authorization_url);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to start Meta OAuth.");
      setDashboardLoading(false);
    }
  }

  async function disconnectSocialAccount(accountId: string) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/connected-accounts/${accountId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${dashboardToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      setDashboardSaved("Social account disconnected.");
      await loadSocialData(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to disconnect social account.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function deleteSocialAccount(accountId: string) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/connected-accounts/${accountId}/remove`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${dashboardToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      setDashboardSaved("Social ID deleted.");
      await loadSocialData(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to delete social ID.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function createSocialEvent(event: SocialEventCreateInput) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/connectors/webhook/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify({
          ...event,
          connected_account_id: event.connected_account_id || undefined,
          external_event_id: event.external_event_id || undefined,
          actor_handle: event.actor_handle || undefined,
          raw_payload: {
            source: "dashboard-social-inbox",
          },
        }),
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      setDashboardSaved("Social event scanned.");
      await loadSocialData(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to scan social event.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function applySocialAction(eventId: string, actionType: SocialActionType) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/social-actions/${eventId}/${actionType}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      const action = (await response.json()) as SocialActionResponse;
      const platformCall = action.payload?.platform?.platform_call;
      if (action.status === "failed") {
        setDashboardError(action.payload?.platform?.error || "Platform action failed.");
      } else if (platformCall === "missing_access_token") {
        setDashboardSaved("Action recorded locally. OAuth access is needed before it can run on the platform.");
      } else if (platformCall === "unsupported_platform") {
        setDashboardSaved("Action recorded locally for this connector.");
      } else {
        setDashboardSaved("Social action applied.");
      }
      await loadSocialData(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to apply social action.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function createModerationKey() {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    setCreatedApiKey("");
    try {
      const response = await fetch(`${API_BASE}/api-keys`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify({
          name: newKeyName,
          scopes: ["moderation"],
        }),
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      const payload = (await response.json()) as ApiKeyCreated;
      setCreatedApiKey(payload.api_key);
      setDashboardSaved("Moderation key created. Copy it now; it will not be shown again.");
      await loadApiKeys(dashboardToken);
      await loadApiKeyUsage(dashboardToken);
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to create API key.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function savePolicy() {
    if (!dashboard) {
      return;
    }

    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/policies/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify({
          thresholds: policyDraft,
          review_enabled: dashboard.policy.review_enabled,
          protected_mode: dashboard.policy.protected_mode,
        }),
      });
      if (!response.ok) {
        throw new Error(`Guard API returned ${response.status}`);
      }
      const policy = (await response.json()) as DashboardSummary["policy"];
      setDashboard({ ...dashboard, policy });
      setPolicyDraft(policy.thresholds);
      setDashboardSaved("Policy saved.");
      await loadDashboard("");
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to save policy.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function startBillingCheckout(planName: string) {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/billing/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify({ plan_name: planName }),
      });
      if (!response.ok) {
        let detail = "";
        try {
          detail = String(((await response.json()) as { detail?: string }).detail ?? "");
        } catch {
          detail = "";
        }
        throw new Error(detail || `Checkout failed: ${response.status}`);
      }
      const payload = (await response.json()) as { checkout_url: string };
      window.location.href = payload.checkout_url;
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to start checkout.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function openBillingPortal() {
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/billing/portal`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${dashboardToken}`,
        },
      });
      if (!response.ok) {
        let detail = "";
        try {
          detail = String(((await response.json()) as { detail?: string }).detail ?? "");
        } catch {
          detail = "";
        }
        throw new Error(detail || `Billing portal failed: ${response.status}`);
      }
      const payload = (await response.json()) as { portal_url: string };
      window.location.href = payload.portal_url;
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to open billing portal.");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function updateBillingScope(nextScope: "account" | "workspace") {
    if (!dashboard || billingStatus?.billing_scope === nextScope) {
      return;
    }
    setDashboardLoading(true);
    setDashboardError("");
    setDashboardSaved("");
    try {
      const response = await fetch(`${API_BASE}/billing/scope`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardToken}`,
        },
        body: JSON.stringify({ billing_scope: nextScope }),
      });
      if (!response.ok) {
        throw new Error(`Billing scope update failed: ${response.status}`);
      }
      const status = (await response.json()) as BillingStatus;
      setBillingStatus(status);
      setDashboard({
        ...dashboard,
        usage: {
          ...dashboard.usage,
          billing_scope: status.billing_scope,
          monthly_quota: status.monthly_quota,
          plan_name: status.plan_name,
          remaining_requests: Math.max(status.monthly_quota - dashboard.usage.total_requests, 0),
        },
      });
      await loadDashboard("");
      setDashboardSaved(
        nextScope === "workspace"
          ? "This workspace now has separate billing."
          : "This workspace now uses shared account billing.",
      );
    } catch (caught) {
      setDashboardError(caught instanceof Error ? caught.message : "Unable to update billing scope.");
    } finally {
      setDashboardLoading(false);
    }
  }

  function updateThreshold(category: string, key: keyof PolicyThreshold, value: number) {
    setPolicyDraft((current) => {
      const existing = current[category] ?? {};
      const next = { ...existing, [key]: value };
      if (next.review != null && next.block != null && next.review > next.block) {
        if (key === "review") {
          next.block = value;
        } else {
          next.review = value;
        }
      }
      return { ...current, [category]: next };
    });
  }

  function updatePolicyFlag(key: "review_enabled" | "protected_mode", value: boolean) {
    setDashboard((current) =>
      current
        ? {
            ...current,
            policy: {
              ...current.policy,
              [key]: value,
            },
          }
        : current,
    );
  }

  function navigate(nextPath: string) {
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setPath(nextPath);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const dashboardNode = (
    <ClientDashboard
      apiKey={dashboardApiKey}
      setApiKey={setDashboardApiKey}
      dashboard={dashboard}
      thresholdRows={thresholdRows}
      loading={dashboardLoading}
      error={dashboardError}
      saved={dashboardSaved}
      apiKeys={apiKeys}
      apiKeyUsage={apiKeyUsage}
      billingStatus={billingStatus}
      workspaces={workspaces}
      reviewCases={reviewCases}
      connectedAccounts={connectedAccounts}
      socialEvents={socialEvents}
      caseNotes={caseNotes}
      clerkEnabled={clerkEnabled}
      workspaceLookupLoading={clerkEnabled && clerkSignedIn && !clerkWorkspaceChecked && dashboardLoading && !dashboard}
      newKeyName={newKeyName}
      createdApiKey={createdApiKey}
      workspaceName={workspaceName}
      workspaceRename={workspaceRename}
      onboardingModerationKey={onboardingModerationKey}
      workspaceShieldTenant={workspaceShieldTenant}
      setNewKeyName={setNewKeyName}
      setWorkspaceName={setWorkspaceName}
      setWorkspaceRename={setWorkspaceRename}
      setCaseNotes={setCaseNotes}
      onLogin={() => loadDashboard()}
      onCreateWorkspace={createWorkspace}
      onSwitchWorkspace={switchWorkspace}
      onRenameWorkspace={renameWorkspace}
      onDeleteWorkspace={deleteWorkspace}
      onRefresh={() => loadDashboard()}
      onThresholdChange={updateThreshold}
      onPolicyFlagChange={updatePolicyFlag}
      onSave={savePolicy}
      onCreateModerationKey={createModerationKey}
      onDeactivateApiKey={deactivateApiKey}
      onRotateApiKey={rotateApiKey}
      onUpdateReviewCase={updateReviewCase}
      onConnectSocialAccount={connectSocialAccount}
      onStartMetaOAuth={startMetaOAuth}
      onDisconnectSocialAccount={disconnectSocialAccount}
      onDeleteSocialAccount={deleteSocialAccount}
      onCreateSocialEvent={createSocialEvent}
      onApplySocialAction={applySocialAction}
      onStartBillingCheckout={startBillingCheckout}
      onOpenBillingPortal={openBillingPortal}
      onUpdateBillingScope={updateBillingScope}
      onWorkspaceShieldComplete={() => setWorkspaceShieldTenant("")}
      dashboardToken={dashboardToken}
      onPlaygroundComplete={() => loadDashboard("")}
    />
  );

  if (path === "/dashboard") {
    return (
      <DashboardRoute
        clerkEnabled={clerkEnabled}
        theme={theme}
        setTheme={setTheme}
        navigate={navigate}
      >
        {dashboardNode}
      </DashboardRoute>
    );
  }

  const legalPage = legalPages[path as keyof typeof legalPages];
  if (legalPage) {
    return <LegalPage page={legalPage} theme={theme} setTheme={setTheme} navigate={navigate} />;
  }

  return (
    <main className="min-h-screen overflow-hidden bg-background text-foreground">
      <section className="relative border-b border-border">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(20,184,166,0.18),transparent_28%),radial-gradient(circle_at_78%_5%,rgba(244,63,94,0.13),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.04),transparent_40%)] dark:bg-[radial-gradient(circle_at_15%_20%,rgba(45,212,191,0.18),transparent_28%),radial-gradient(circle_at_78%_5%,rgba(251,113,133,0.13),transparent_30%),linear-gradient(135deg,rgba(255,255,255,0.05),transparent_40%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(15,23,42,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.05)_1px,transparent_1px)] bg-[size:42px_42px] dark:bg-[linear-gradient(rgba(255,255,255,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.06)_1px,transparent_1px)]" />

        <div className="container relative">
          <nav className="flex h-20 items-center justify-between gap-4">
            <button className="flex shrink-0 items-center gap-3" type="button" onClick={() => navigate("/")}>
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-glow">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <span className="whitespace-nowrap text-lg font-semibold">Guard API</span>
            </button>
            <div className="hidden min-w-0 flex-1 items-center justify-center gap-4 text-sm text-muted-foreground lg:flex xl:gap-5">
              <a className="whitespace-nowrap transition hover:text-foreground" href="#platform">
                Platform
              </a>
              <a className="whitespace-nowrap transition hover:text-foreground" href="#workflow">
                Workflow
              </a>
              <a className="whitespace-nowrap transition hover:text-foreground" href="#how-to-use">
                How to use
              </a>
              <a className="hidden whitespace-nowrap transition hover:text-foreground xl:inline" href="#next-update">
                Next update
              </a>
              <a className="hidden whitespace-nowrap transition hover:text-foreground 2xl:inline" href="#dashboard-preview">
                Dashboard preview
              </a>
              <a className="whitespace-nowrap transition hover:text-foreground" href="#pricing">
                Pricing
              </a>
              <a className="whitespace-nowrap transition hover:text-foreground" href="#faq">
                FAQ
              </a>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
              >
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <AuthActions clerkEnabled={clerkEnabled} onDashboard={() => navigate("/dashboard")} />
            </div>
          </nav>

          <div className="grid min-h-[calc(100vh-5rem)] items-center gap-10 py-10 lg:grid-cols-[0.92fr_1.08fr] lg:py-14">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55 }}
              className="max-w-2xl"
            >
              <Badge variant="secondary" className="mb-5 gap-2 border border-border bg-white/70">
                <Sparkles className="h-3.5 w-3.5 text-teal-700" />
                Real-time trust and safety infrastructure
              </Badge>
              <h1 className="text-4xl font-semibold leading-tight tracking-normal text-slate-950 dark:text-white sm:text-5xl lg:text-6xl">
                Guard API
              </h1>
              <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600 dark:text-slate-300">
                A polished moderation command center for products that need to stop spam, abuse, fraud,
                and safety risk before it reaches users.
              </p>
              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <Button size="lg" onClick={() => runModeration(sampleTexts[0].text, sampleTexts[0].language)}>
                  Run live demo
                  <Radar className="h-4 w-4" />
                </Button>
                <AuthPrimaryAction clerkEnabled={clerkEnabled} onDashboard={() => navigate("/dashboard")} />
              </div>
              <div className="mt-8 grid gap-3 sm:grid-cols-3">
                {productStats.map((stat) => (
                  <div
                    key={stat.label}
                    className="rounded-lg border border-white/70 bg-white/70 p-4 shadow-sm backdrop-blur dark:border-white/10 dark:bg-white/[0.07]"
                  >
                    <div className="text-2xl font-semibold text-slate-950 dark:text-white">{stat.value}</div>
                    <div className="mt-1 text-sm font-medium text-slate-700 dark:text-slate-200">{stat.label}</div>
                    <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{stat.detail}</div>
                  </div>
                ))}
              </div>
            </motion.div>

            <motion.div
              id="demo"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.55, delay: 0.08 }}
            >
              <ModerationConsole
                text={text}
                setText={setText}
                textLanguage={textLanguage}
                setTextLanguage={setTextLanguage}
                result={result}
                topScores={topScores}
                demoMode={demoMode}
                setDemoMode={setDemoMode}
                textLoading={textLoading}
                imageLoading={imageLoading}
                audioLoading={audioLoading}
                videoLoading={videoLoading}
                error={error}
                imageFile={imageFile}
                imagePreview={imagePreview}
                setImageFile={setImageFile}
                audioFile={audioFile}
                setAudioFile={setAudioFile}
                audioTranscript={audioTranscript}
                setAudioTranscript={setAudioTranscript}
                videoTranscript={videoTranscript}
                setVideoTranscript={setVideoTranscript}
                videoFrameDescription={videoFrameDescription}
                setVideoFrameDescription={setVideoFrameDescription}
                videoOcrText={videoOcrText}
                setVideoOcrText={setVideoOcrText}
                videoObjects={videoObjects}
                setVideoObjects={setVideoObjects}
                videoFile={videoFile}
                setVideoFile={setVideoFile}
                onVideoFileChange={handleVideoFileChange}
                onRun={() => runModeration()}
                onSample={(sample) => runModeration(sample.text, sample.language)}
                onImageRun={runImageModeration}
                onAudioRun={runAudioModeration}
                onVideoRun={runVideoModeration}
              />
            </motion.div>
          </div>
        </div>
      </section>

      <section id="platform" className="relative overflow-hidden bg-white py-16 dark:bg-slate-950">
        <CyberSecurityBackdrop />
        <div className="container relative">
          <div className="max-w-2xl">
            <Badge variant="outline" className="mb-4">
              Product surface
            </Badge>
            <h2 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-white">Built for products with live UGC risk</h2>
            <p className="mt-3 text-slate-600 dark:text-slate-300">
              Guard API combines fast local rules, inference-service scoring, policy thresholds, review cases,
              and audit trails behind one simple API.
            </p>
          </div>

          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {platformBlocks.map((block, index) => (
              <motion.div
                key={block.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.35, delay: index * 0.06 }}
              >
                <Card className="h-full border-slate-200 bg-slate-50/70 dark:border-white/10 dark:bg-white/[0.06]">
                  <CardHeader>
                    <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-white text-teal-700 shadow-sm dark:bg-slate-900 dark:text-teal-300">
                      <block.icon className="h-5 w-5" />
                    </span>
                    <CardTitle>{block.title}</CardTitle>
                    <CardDescription>{block.body}</CardDescription>
                  </CardHeader>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <PublicHowToUseSection onDashboard={() => navigate("/dashboard")} />

      <PublicPricingSection onDashboard={() => navigate("/dashboard")} />

      <PublicDashboardPreview
        dashboardPreview={dashboardPreview}
        previewKeyUsage={previewKeyUsage}
        previewReviewCases={previewReviewCasesState}
        onResetPreview={resetDashboardPreview}
      />

      <PublicNextUpdateSection />

      <section id="workflow" className="relative overflow-hidden border-y border-border bg-slate-950 py-16 text-white">
        <CyberSecurityBackdrop intensity="strong" />
        <div className="container relative grid gap-10 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <Badge className="mb-4 bg-teal-400 text-slate-950">Workflow</Badge>
            <h2 className="text-3xl font-semibold tracking-normal">Every decision is explainable and stored.</h2>
            <p className="mt-4 text-slate-300">
              The API returns the action, triggered categories, policy labels, latency, model metadata,
              and a review case when the content needs human follow-up.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {pipeline.map((step, index) => (
              <div key={step} className="rounded-lg border border-white/10 bg-white/[0.06] p-4">
                <div className="mb-5 flex h-8 w-8 items-center justify-center rounded-md bg-teal-400 text-sm font-semibold text-slate-950">
                  {index + 1}
                </div>
                <p className="text-sm font-medium leading-5 text-slate-100">{step}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <PublicAboutDeveloperSection />

      <PublicFaqSection />

      <PublicFooter navigate={navigate} />
    </main>
  );
}

function PublicHowToUseSection({ onDashboard }: { onDashboard: () => void }) {
  const [selectedPathId, setSelectedPathId] = useState<GuideAudience>("developers");
  const selectedPath = howToUsePaths.find((path) => path.id === selectedPathId) ?? howToUsePaths[0];

  return (
    <section id="how-to-use" className="relative overflow-hidden border-y border-border bg-slate-50 py-16 dark:bg-slate-900">
      <CyberSecurityBackdrop />
      <div className="container relative">
        <div className="grid gap-8 lg:grid-cols-[0.78fr_1.22fr]">
          <div>
            <Badge variant="secondary" className="mb-4 gap-2">
              <BookOpen className="h-3.5 w-3.5 text-teal-700" />
              How to use
            </Badge>
            <h2 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-white">
              Choose the guide that matches how you will use Guard API.
            </h2>
            <p className="mt-3 text-slate-600 dark:text-slate-300">
              Developers get integration steps. Operators and non-technical users get dashboard workflows.
              Organizations get the rollout path for workspaces, keys, review cases, and billing scope.
            </p>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {howToUsePaths.map((path) => (
                <button
                  key={path.id}
                  type="button"
                  onClick={() => setSelectedPathId(path.id)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg border p-3 text-left transition",
                    selectedPath.id === path.id
                      ? "border-teal-500 bg-white text-slate-950 shadow-sm dark:bg-slate-950 dark:text-white"
                      : "border-border bg-background/80 text-muted-foreground hover:bg-background",
                  )}
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                    <path.icon className="h-4 w-4" />
                  </span>
                  <span className="text-sm font-medium">{path.label}</span>
                </button>
              ))}
            </div>
          </div>

          <Card className="border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-slate-950/80">
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <selectedPath.icon className="h-5 w-5 text-teal-700" />
                    {selectedPath.title}
                  </CardTitle>
                  <CardDescription className="mt-2">{selectedPath.summary}</CardDescription>
                </div>
                <Badge variant="outline">{selectedPath.label}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-3">
                  {selectedPath.steps.map((step, index) => (
                    <div key={step} className="grid grid-cols-[32px_1fr] gap-3 rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-900">
                      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-600 text-sm font-semibold text-white">
                        {index + 1}
                      </span>
                      <p className="text-sm leading-6 text-slate-700 dark:text-slate-200">{step}</p>
                    </div>
                  ))}
                </div>
                <div className="grid content-start gap-3">
                  <div className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-900">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">Common use cases</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedPath.useCases.map((useCase) => (
                        <Badge key={useCase} variant="secondary">{useCase}</Badge>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-900">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">Dashboard areas</p>
                    <div className="mt-3 grid gap-2">
                      {selectedPath.dashboardActions.map((action) => (
                        <div key={action} className="flex items-center gap-2 text-sm text-muted-foreground">
                          <CheckCircle2 className="h-4 w-4 text-teal-700" />
                          <span>{action}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <Button onClick={onDashboard} className="w-full">
                    Open dashboard
                    <LayoutDashboard className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}

function PublicNextUpdateSection() {
  const upcomingUpdates = [
    {
      title: "Mobile review app",
      description: "Monitor alerts, review cases, and social inbox activity from a phone when teams are away from the dashboard.",
      items: ["Alert monitoring", "Review case triage", "Social inbox checks"],
      status: "planned",
    },
    {
      title: "Adaptive Policy Memory",
      description:
        "A developing intelligence layer that lets teams turn repeated scams, coded harassment, and resolved review cases into reusable moderation memory.",
      items: ["Review case learning", "Customer-specific patterns", "Coded abuse detection"],
      status: "developing",
    },
  ];

  return (
    <section id="next-update" className="relative overflow-hidden border-t border-border bg-slate-50 py-16 dark:bg-slate-900">
      <CyberSecurityBackdrop />
      <div className="container relative">
        <div className="grid items-center gap-8 lg:grid-cols-[0.85fr_1.15fr]">
          <div>
            <Badge variant="secondary" className="mb-4">
              Upcoming updates
            </Badge>
            <h2 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-white">
              Mobile review app is planned, and adaptive policy memory is developing.
            </h2>
            <p className="mt-4 text-slate-600 dark:text-slate-300">
              Guard API is expanding beyond the web dashboard with mobile moderation workflows and a practical
              memory layer for evolving abuse patterns. These updates are not current production features yet.
            </p>
            <div className="mt-6 grid gap-4">
              {upcomingUpdates.map((update) => (
                <div key={update.title} className="rounded-lg border border-border bg-background p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-950 dark:text-white">{update.title}</p>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{update.description}</p>
                    </div>
                    <Badge variant="outline">{update.status}</Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {update.items.map((item) => (
                      <Badge key={item} variant="secondary">{item}</Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border border-border bg-slate-950 shadow-sm">
            <img
              src="/mobile-app-coming-soon.png"
              alt="Guard API mobile app coming soon"
              className="aspect-[21/9] w-full object-cover"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function PublicAboutDeveloperSection() {
  return (
    <section id="built-by" className="bg-slate-50 py-16 dark:bg-slate-900">
      <div className="container">
        <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
          <div>
            <Badge variant="outline" className="mb-4">
              Built by
            </Badge>
            <h2 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-white">
              Independent product engineering for practical moderation.
            </h2>
          </div>
          <Card className="border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-slate-950/80">
            <CardContent className="p-6">
              <p className="text-sm leading-6 text-slate-700 dark:text-slate-200">
                Guard API is built by an independent developer focused on trust-and-safety tooling for social,
                marketplace, creator, and dating apps. The product is designed to help teams check text, images,
                audio, and video before harmful content reaches users.
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <ApiDocTile label="Focus" value="Trust and safety APIs" />
                <ApiDocTile label="Audience" value="Apps with user content" />
                <ApiDocTile label="Goal" value="Allow, review, or block before publish" />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}

function PublicFaqSection() {
  const [openQuestion, setOpenQuestion] = useState(publicFaqs[0]?.question ?? "");

  return (
    <section id="faq" className="bg-white py-16 dark:bg-slate-950">
      <div className="container">
        <div className="max-w-2xl">
          <Badge variant="outline" className="mb-4">
            FAQ
          </Badge>
          <h2 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-white">
            Questions before connecting Guard API
          </h2>
          <p className="mt-3 text-slate-600 dark:text-slate-300">
            Short answers for founders, creators, and teams deciding how to use moderation in their product.
          </p>
        </div>

        <div className="mt-8 grid gap-3">
          {publicFaqs.map((item) => (
            <div key={item.question} className="rounded-lg border border-slate-200 bg-slate-50/70 dark:border-white/10 dark:bg-white/[0.06]">
              <button
                type="button"
                onClick={() => setOpenQuestion((current) => (current === item.question ? "" : item.question))}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                aria-expanded={openQuestion === item.question}
              >
                <span className="text-base font-semibold text-slate-950 dark:text-white">{item.question}</span>
                <ChevronDown
                  className={cn(
                    "h-5 w-5 shrink-0 text-muted-foreground transition-transform",
                    openQuestion === item.question ? "rotate-180" : "",
                  )}
                />
              </button>
              <AnimatePresence initial={false}>
                {openQuestion === item.question ? (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <p className="border-t border-border px-5 py-4 text-sm leading-6 text-muted-foreground">
                      {item.answer}
                    </p>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function AuthActions({ clerkEnabled, onDashboard }: { clerkEnabled: boolean; onDashboard: () => void }) {
  if (!clerkEnabled) {
    return (
      <Button variant="secondary" onClick={onDashboard}>
        Configure auth
        <LayoutDashboard className="h-4 w-4" />
      </Button>
    );
  }

  return (
    <>
      <Show when="signed-out">
        <SignInButton mode="modal" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard">
          <Button variant="outline" size="sm">Sign in</Button>
        </SignInButton>
        <SignUpButton mode="modal" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard">
          <Button size="sm">
            Create account
            <ArrowRight className="h-4 w-4" />
          </Button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <Button variant="secondary" onClick={onDashboard}>
          Dashboard
          <LayoutDashboard className="h-4 w-4" />
        </Button>
        <UserButton />
      </Show>
    </>
  );
}

function AuthPrimaryAction({ clerkEnabled, onDashboard }: { clerkEnabled: boolean; onDashboard: () => void }) {
  if (!clerkEnabled) {
    return (
      <Button size="lg" variant="secondary" onClick={onDashboard}>
        Configure Clerk
        <ArrowRight className="h-4 w-4" />
      </Button>
    );
  }

  return (
    <>
      <Show when="signed-out">
        <SignUpButton mode="modal" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard">
          <Button size="lg" variant="secondary">
            Create account
            <ArrowRight className="h-4 w-4" />
          </Button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <Button size="lg" variant="secondary" onClick={onDashboard}>
          Open dashboard
          <LayoutDashboard className="h-4 w-4" />
        </Button>
      </Show>
    </>
  );
}

function CyberSecurityBackdrop({
  fixed = false,
  intensity = "standard",
}: {
  fixed?: boolean;
  intensity?: "standard" | "strong";
}) {
  const traces = [
    { className: "left-[6%] top-[18%] h-16 w-48 border-l border-t", delay: 0 },
    { className: "right-[8%] top-[14%] h-24 w-56 border-r border-t", delay: 0.45 },
    { className: "left-[16%] bottom-[12%] h-20 w-64 border-b border-l", delay: 0.9 },
    { className: "right-[18%] bottom-[20%] h-16 w-44 border-b border-r", delay: 1.25 },
  ];
  const dataColumns = [
    "left-[10%] top-[34%]",
    "left-[76%] top-[26%]",
    "left-[86%] top-[58%]",
  ];

  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none inset-0 overflow-hidden",
        fixed ? "fixed" : "absolute",
        intensity === "strong" ? "opacity-100" : "opacity-80",
      )}
    >
      <div className="absolute inset-0 bg-[linear-gradient(125deg,rgba(240,253,250,0.96),rgba(241,245,249,0.84)_34%,rgba(236,253,245,0.72)_70%,rgba(255,247,237,0.58))] dark:bg-[linear-gradient(125deg,rgba(2,6,23,0.98),rgba(15,23,42,0.88)_42%,rgba(4,47,46,0.76)_74%,rgba(15,23,42,0.9))]" />
      <div className="absolute inset-0 bg-[repeating-linear-gradient(120deg,rgba(15,23,42,0.045)_0px,rgba(15,23,42,0.045)_1px,transparent_1px,transparent_24px)] opacity-55 dark:bg-[repeating-linear-gradient(120deg,rgba(45,212,191,0.065)_0px,rgba(45,212,191,0.065)_1px,transparent_1px,transparent_28px)] dark:opacity-70" />
      <div
        className="absolute -right-24 top-8 h-64 w-[42rem] border border-teal-500/14 bg-white/22 shadow-[0_30px_120px_rgba(20,184,166,0.16)] backdrop-blur-sm dark:border-teal-300/12 dark:bg-teal-300/[0.035]"
        style={{ clipPath: "polygon(14% 0, 100% 0, 86% 100%, 0 100%)" }}
      />
      <div
        className="absolute -left-20 bottom-0 h-56 w-[34rem] border border-amber-500/12 bg-white/18 backdrop-blur-sm dark:border-amber-300/10 dark:bg-amber-300/[0.025]"
        style={{ clipPath: "polygon(0 0, 86% 0, 100% 100%, 10% 100%)" }}
      />
      {traces.map((trace) => (
        <motion.div
          key={trace.className}
          className={cn("absolute border-teal-600/22 dark:border-teal-300/22", trace.className)}
          animate={{ opacity: [0.18, 0.68, 0.18] }}
          transition={{ duration: 3.4, repeat: Infinity, delay: trace.delay, ease: "easeInOut" }}
        >
          <motion.span
            className="absolute -right-1 -top-1 h-2 w-2 rounded-sm border border-teal-500/50 bg-background shadow-[0_0_18px_rgba(20,184,166,0.34)] dark:border-teal-300/55 dark:bg-slate-950"
            animate={{ opacity: [0.35, 1, 0.35] }}
            transition={{ duration: 2.1, repeat: Infinity, delay: trace.delay }}
          />
        </motion.div>
      ))}
      {dataColumns.map((position, index) => (
        <motion.div
          key={position}
          className={cn("absolute flex h-32 w-10 flex-col justify-between opacity-45 dark:opacity-55", position)}
          animate={{ y: [0, 12, 0] }}
          transition={{ duration: 4.8, repeat: Infinity, delay: index * 0.5, ease: "easeInOut" }}
        >
          {Array.from({ length: 7 }).map((_, barIndex) => (
            <span
              key={barIndex}
              className={cn(
                "block h-1 rounded-sm bg-slate-500/32 dark:bg-teal-200/35",
                barIndex % 3 === 0 ? "w-10" : barIndex % 2 === 0 ? "w-6" : "w-3",
              )}
            />
          ))}
        </motion.div>
      ))}
      <motion.div
        className="absolute left-[-12%] top-[36%] h-24 w-[124%] bg-[linear-gradient(100deg,transparent,rgba(20,184,166,0.13)_42%,rgba(14,165,233,0.10)_52%,transparent_68%)] dark:bg-[linear-gradient(100deg,transparent,rgba(45,212,191,0.18)_42%,rgba(56,189,248,0.13)_52%,transparent_68%)]"
        animate={{ x: ["-10%", "10%"], opacity: [0.16, 0.44, 0.16] }}
        transition={{ duration: 8.2, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-[-18%] top-[58%] h-16 w-[118%] bg-[linear-gradient(78deg,transparent,rgba(244,63,94,0.08)_38%,rgba(245,158,11,0.08)_50%,transparent_66%)] dark:bg-[linear-gradient(78deg,transparent,rgba(251,113,133,0.10)_38%,rgba(251,191,36,0.08)_50%,transparent_66%)]"
        animate={{ x: ["9%", "-9%"], opacity: [0.08, 0.28, 0.08] }}
        transition={{ duration: 10.5, repeat: Infinity, ease: "easeInOut", delay: 0.7 }}
      />
      <div className="absolute inset-x-0 bottom-0 h-36 bg-gradient-to-t from-background via-background/76 to-transparent dark:from-slate-950 dark:via-slate-950/72" />
    </div>
  );
}

function PublicPricingSection({ onDashboard }: { onDashboard: () => void }) {
  return (
    <section id="pricing" className="relative overflow-hidden border-y border-border bg-slate-50 py-16 dark:bg-slate-900/55">
      <CyberSecurityBackdrop />
      <div className="container relative">
        <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
          <div>
            <Badge variant="secondary" className="mb-4 gap-2">
              <CreditCard className="h-3.5 w-3.5 text-teal-700" />
              Plans and trial
            </Badge>
            <h2 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-white">
              Start with a 15-day free trial.
            </h2>
            <p className="mt-3 text-slate-600 dark:text-slate-300">
              Create a workspace, test real moderation traffic, and upgrade when your volume grows.
            </p>
          </div>
          <div className="rounded-lg border border-teal-200 bg-white p-5 shadow-sm dark:border-teal-400/20 dark:bg-slate-950">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-900 dark:text-white">Starter trial includes 3,000 moderation credits</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Text is 1 credit, image and audio are 10 credits, and video is 25 credits per check.
                </p>
              </div>
              <Button onClick={onDashboard}>
                Start free trial
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-8 grid gap-4 lg:grid-cols-3">
          {billingPlans.map((plan) => (
            <Card key={plan.name} className="relative h-full border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-slate-950/70">
              {plan.badge ? (
                <Badge className="absolute right-4 top-4" variant="secondary">
                  {plan.badge}
                </Badge>
              ) : null}
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="capitalize">{plan.name}</CardTitle>
                  {"trial" in plan ? <Badge variant="success">{plan.trial}</Badge> : null}
                </div>
                <div className="flex items-end gap-1 pt-2">
                  <span className="text-3xl font-semibold text-slate-950 dark:text-white">{plan.price}</span>
                  <span className="pb-1 text-sm text-muted-foreground">/{plan.cadence}</span>
                </div>
                <CardDescription>{plan.audience}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
                  <p className="text-sm font-medium text-slate-900 dark:text-white">{plan.quota.toLocaleString()} credits/month</p>
                  <p className="mt-1 text-xs text-muted-foreground">{plan.overage}</p>
                </div>
                <div className="mt-4 grid gap-2">
                  {plan.features.map((feature) => (
                    <div key={feature} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" />
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-400/25 dark:bg-amber-950/35 dark:text-amber-100">
          Media-heavy apps should watch credit use closely. Credit weights: text 1, image 10, audio 10, video 25.
          Custom media limits can be offered for high-volume customers.
        </div>
      </div>
    </section>
  );
}

function PublicDashboardPreview({
  dashboardPreview,
  previewKeyUsage,
  previewReviewCases,
  onResetPreview,
}: {
  dashboardPreview: DashboardSummary;
  previewKeyUsage: ApiKeyUsage[];
  previewReviewCases: ReviewCase[];
  onResetPreview: () => void;
}) {
  const [policyDraft, setPolicyDraft] = useState(previewDashboard.policy.thresholds);
  const [caseNotes, setCaseNotes] = useState<Record<string, string>>({});
  const [reviewCases, setReviewCases] = useState(previewReviewCases);

  useEffect(() => {
    setReviewCases(previewReviewCases);
  }, [previewReviewCases]);

  function updatePreviewThreshold(category: string, key: keyof PolicyThreshold, value: number) {
    setPolicyDraft((current) => {
      const next = { ...(current[category] ?? {}), [key]: value };
      if (next.review != null && next.block != null && next.review > next.block) {
        if (key === "review") {
          next.block = value;
        } else {
          next.review = value;
        }
      }
      return { ...current, [category]: next };
    });
  }

  function updatePreviewCase(caseId: string, status: ReviewCase["status"]) {
    setReviewCases((current) =>
      current.map((reviewCase) => (reviewCase.case_id === caseId ? { ...reviewCase, status } : reviewCase)),
    );
    setCaseNotes((current) => ({ ...current, [caseId]: "" }));
  }

  return (
    <section id="dashboard-preview" className="relative overflow-hidden bg-slate-50 py-16 dark:bg-slate-900">
      <CyberSecurityBackdrop intensity="strong" />
      <div className="container relative">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <Badge variant="outline" className="mb-4">
              Dashboard preview
            </Badge>
            <h2 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-white">
              See what clients get after connecting a workspace.
            </h2>
            <p className="mt-3 text-slate-600 dark:text-slate-300">
              This preview is separate from the real dashboard and uses example data with a credit limit of 10.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant={dashboardPreview.usage.remaining_requests === 0 ? "danger" : "secondary"}>
              Example credits: {dashboardPreview.usage.total_requests}/10
            </Badge>
            <Button variant="outline" size="sm" onClick={onResetPreview}>
              <RefreshCw className="h-4 w-4" />
              Reset preview credits
            </Button>
          </div>
        </div>

        <ClientDashboard
          apiKey=""
          setApiKey={() => undefined}
          dashboard={{ ...dashboardPreview, policy: { ...dashboardPreview.policy, thresholds: policyDraft } }}
          thresholdRows={Object.entries(policyDraft).sort(([left], [right]) => left.localeCompare(right))}
          loading={false}
          error=""
          saved=""
          apiKeys={previewApiKeys}
          apiKeyUsage={previewKeyUsage}
          billingStatus={previewBillingStatus}
          workspaces={[]}
          reviewCases={reviewCases}
          connectedAccounts={[]}
          socialEvents={[]}
          caseNotes={caseNotes}
          clerkEnabled
          workspaceLookupLoading={false}
          previewMode
          newKeyName="server-moderation-key"
          createdApiKey=""
          workspaceName="Marketplace"
          workspaceRename=""
          onboardingModerationKey=""
          workspaceShieldTenant=""
          setNewKeyName={() => undefined}
          setWorkspaceName={() => undefined}
          setWorkspaceRename={() => undefined}
          setCaseNotes={setCaseNotes}
          onLogin={() => undefined}
          onCreateWorkspace={() => undefined}
          onSwitchWorkspace={() => undefined}
          onRenameWorkspace={() => undefined}
          onDeleteWorkspace={() => undefined}
          onRefresh={() => undefined}
          onThresholdChange={updatePreviewThreshold}
          onPolicyFlagChange={() => undefined}
          onSave={() => undefined}
          onCreateModerationKey={() => undefined}
          onDeactivateApiKey={() => undefined}
          onRotateApiKey={() => undefined}
          onUpdateReviewCase={updatePreviewCase}
          onConnectSocialAccount={() => undefined}
          onStartMetaOAuth={() => undefined}
          onDisconnectSocialAccount={() => undefined}
          onDeleteSocialAccount={() => undefined}
          onCreateSocialEvent={() => undefined}
          onApplySocialAction={() => undefined}
          onStartBillingCheckout={() => undefined}
          onOpenBillingPortal={() => undefined}
          onUpdateBillingScope={() => undefined}
          onWorkspaceShieldComplete={() => undefined}
          dashboardToken=""
          onPlaygroundComplete={() => undefined}
        />
      </div>
    </section>
  );
}

function PublicFooter({ navigate }: { navigate: (path: string) => void }) {
  const links = [
    ["/terms", "Terms"],
    ["/privacy", "Privacy"],
    ["/refund", "Refunds"],
    ["/acceptable-use", "Acceptable use"],
    ["/data-retention", "Data retention"],
  ];

  return (
    <footer className="border-t border-border bg-slate-950 py-8 text-slate-300">
      <div className="container flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="font-semibold text-white">Guard API</p>
          <p className="mt-1 text-sm text-slate-400">Real-time trust and safety API for UGC products.</p>
        </div>
        <div className="flex flex-wrap gap-3 text-sm">
          {links.map(([href, label]) => (
            <button key={href} type="button" className="transition hover:text-white" onClick={() => navigate(href)}>
              {label}
            </button>
          ))}
        </div>
      </div>
    </footer>
  );
}

function LegalPage({
  page,
  theme,
  setTheme,
  navigate,
}: {
  page: (typeof legalPages)[keyof typeof legalPages];
  theme: "light" | "dark";
  setTheme: Dispatch<SetStateAction<"light" | "dark">>;
  navigate: (path: string) => void;
}) {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-background/90 backdrop-blur">
        <div className="container flex h-16 items-center justify-between gap-4">
          <button className="flex items-center gap-3" type="button" onClick={() => navigate("/")}>
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <span className="text-lg font-semibold">Guard API</span>
          </button>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate("/")}>
              Public site
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </header>
      <section className="py-12">
        <div className="container max-w-3xl">
          <Badge variant="secondary" className="mb-4">Updated {page.updated}</Badge>
          <h1 className="text-4xl font-semibold tracking-normal text-slate-950 dark:text-white">{page.title}</h1>
          <p className="mt-4 text-slate-600 dark:text-slate-300">
            This launch-ready draft should be reviewed by counsel before public paid launch.
          </p>
          <div className="mt-8 grid gap-4">
            {page.sections.map(([title, body]) => (
              <Card key={title} className="dark:border-white/10">
                <CardHeader>
                  <CardTitle className="text-lg">{title}</CardTitle>
                  <CardDescription className="text-sm leading-6">{body}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>
      <PublicFooter navigate={navigate} />
    </main>
  );
}

function DashboardRoute({
  clerkEnabled,
  theme,
  setTheme,
  navigate,
  children,
}: {
  clerkEnabled: boolean;
  theme: "light" | "dark";
  setTheme: Dispatch<SetStateAction<"light" | "dark">>;
  navigate: (path: string) => void;
  children: ReactNode;
}) {
  return (
    <main className="relative min-h-screen overflow-x-hidden bg-slate-50 text-foreground dark:bg-slate-950">
      <CyberSecurityBackdrop fixed intensity="strong" />
      <header className="relative z-10 border-b border-border bg-background/82 backdrop-blur-xl dark:bg-slate-950/76">
        <div className="container flex h-16 max-w-[1480px] items-center justify-between gap-4">
          <button className="flex items-center gap-3" type="button" onClick={() => navigate("/")}>
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <span className="text-lg font-semibold">Guard API</span>
          </button>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate("/")}>
              Public site
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            {clerkEnabled ? (
              <Show when="signed-in">
                <UserButton />
              </Show>
            ) : null}
          </div>
        </div>
      </header>

      <section className="relative z-10 py-8">
        <div className="container max-w-[1480px]">
          {clerkEnabled ? (
            <>
              <Show when="signed-in">{children}</Show>
              <Show when="signed-out">
                <Card className="mx-auto max-w-md dark:border-white/10">
                  <CardHeader>
                    <CardTitle>Sign in to continue</CardTitle>
                    <CardDescription>Create an account or sign in to access the client dashboard.</CardDescription>
                  </CardHeader>
                  <CardContent className="flex gap-3">
                    <SignInButton mode="modal" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard">
                      <Button variant="outline">Sign in</Button>
                    </SignInButton>
                    <SignUpButton mode="modal" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard">
                      <Button>Create account</Button>
                    </SignUpButton>
                  </CardContent>
                </Card>
              </Show>
            </>
          ) : (
            <Card className="mx-auto max-w-xl dark:border-white/10">
              <CardHeader>
                <CardTitle>Clerk is not configured</CardTitle>
                <CardDescription>
                  Add your Clerk publishable key to `frontend/.env.development.local` as `VITE_CLERK_PUBLISHABLE_KEY`,
                  then restart the Vite dev server.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </div>
      </section>
    </main>
  );
}

type ClientDashboardProps = {
  apiKey: string;
  setApiKey: (value: string) => void;
  dashboard: DashboardSummary | null;
  thresholdRows: Array<[string, PolicyThreshold]>;
  loading: boolean;
  error: string;
  saved: string;
  apiKeys: ApiKeyInfo[];
  apiKeyUsage: ApiKeyUsage[];
  billingStatus: BillingStatus | null;
  workspaces: WorkspaceInfo[];
  reviewCases: ReviewCase[];
  connectedAccounts: ConnectedAccount[];
  socialEvents: SocialEvent[];
  caseNotes: Record<string, string>;
  clerkEnabled: boolean;
  workspaceLookupLoading: boolean;
  previewMode?: boolean;
  newKeyName: string;
  createdApiKey: string;
  workspaceName: string;
  workspaceRename: string;
  onboardingModerationKey: string;
  workspaceShieldTenant: string;
  setNewKeyName: (value: string) => void;
  setWorkspaceName: (value: string) => void;
  setWorkspaceRename: (value: string) => void;
  setCaseNotes: Dispatch<SetStateAction<Record<string, string>>>;
  onLogin: () => void;
  onCreateWorkspace: () => void;
  onSwitchWorkspace: (tenantId: string) => void;
  onRenameWorkspace: () => void;
  onDeleteWorkspace: () => void;
  onRefresh: () => void;
  onThresholdChange: (category: string, key: keyof PolicyThreshold, value: number) => void;
  onPolicyFlagChange: (key: "review_enabled" | "protected_mode", value: boolean) => void;
  onSave: () => void;
  onCreateModerationKey: () => void;
  onDeactivateApiKey: (apiKeyId: string) => void;
  onRotateApiKey: (apiKeyId: string) => void;
  onUpdateReviewCase: (caseId: string, status: ReviewCase["status"]) => void;
  onConnectSocialAccount: (account: {
    platform: string;
    provider_account_id: string;
    display_name: string;
    account_type: string;
    scopes: string[];
  }) => void;
  onStartMetaOAuth: () => void;
  onDisconnectSocialAccount: (accountId: string) => void;
  onDeleteSocialAccount: (accountId: string) => void;
  onCreateSocialEvent: (event: SocialEventCreateInput) => void;
  onApplySocialAction: (eventId: string, actionType: SocialActionType) => void;
  onStartBillingCheckout: (planName: string) => void;
  onOpenBillingPortal: () => void;
  onUpdateBillingScope: (billingScope: "account" | "workspace") => void;
  onWorkspaceShieldComplete: () => void;
  dashboardToken: string;
  onPlaygroundComplete: () => void | Promise<void>;
};

type DashboardSection =
  | "overview"
  | "playground"
  | "guide"
  | "integrations"
  | "docs"
  | "social"
  | "review"
  | "policy"
  | "keys"
  | "billing";

function ClientDashboard({
  apiKey,
  setApiKey,
  dashboard,
  thresholdRows,
  loading,
  error,
  saved,
  apiKeys,
  apiKeyUsage,
  billingStatus,
  workspaces,
  reviewCases,
  connectedAccounts,
  socialEvents,
  caseNotes,
  clerkEnabled,
  workspaceLookupLoading,
  previewMode = false,
  newKeyName,
  createdApiKey,
  workspaceName,
  workspaceRename,
  onboardingModerationKey,
  workspaceShieldTenant,
  setNewKeyName,
  setWorkspaceName,
  setWorkspaceRename,
  setCaseNotes,
  onLogin,
  onCreateWorkspace,
  onSwitchWorkspace,
  onRenameWorkspace,
  onDeleteWorkspace,
  onRefresh,
  onThresholdChange,
  onPolicyFlagChange,
  onSave,
  onCreateModerationKey,
  onDeactivateApiKey,
  onRotateApiKey,
  onUpdateReviewCase,
  onConnectSocialAccount,
  onStartMetaOAuth,
  onDisconnectSocialAccount,
  onDeleteSocialAccount,
  onCreateSocialEvent,
  onApplySocialAction,
  onStartBillingCheckout,
  onOpenBillingPortal,
  onUpdateBillingScope,
  onWorkspaceShieldComplete,
  dashboardToken,
  onPlaygroundComplete,
}: ClientDashboardProps) {
  const [activeSection, setActiveSection] = useState<DashboardSection>("overview");
  const [showWorkspaceCreate, setShowWorkspaceCreate] = useState(false);
  const [showWorkspaceRename, setShowWorkspaceRename] = useState(false);
  const [showWorkspaceDeleteConfirm, setShowWorkspaceDeleteConfirm] = useState(false);
  const [showWorkspaceCreateConfirm, setShowWorkspaceCreateConfirm] = useState(false);
  const [inferenceStatus, setInferenceStatus] = useState<InferenceStatus | null>(
    previewMode
      ? {
          status: "online",
          runtime: "local",
          model: "unitary/toxic-bert",
          model_loaded: true,
          fallback_used: false,
          latency_ms: 24,
          error: null,
        }
      : null,
  );
  const [inferenceLoading, setInferenceLoading] = useState(false);
  const sidebarItems: Array<{ id: DashboardSection; label: string; icon: typeof BarChart3 }> = [
    { id: "overview", label: "Marketplace", icon: BarChart3 },
    { id: "playground", label: "Playground", icon: Radar },
    { id: "guide", label: "How to use", icon: BookOpen },
    { id: "integrations", label: "Integration center", icon: Code2 },
    { id: "docs", label: "API docs", icon: BookOpen },
    { id: "social", label: "Social inbox", icon: Workflow },
    { id: "review", label: "Review cases", icon: Radar },
    { id: "policy", label: "Policy thresholds", icon: SlidersHorizontal },
    { id: "keys", label: "API keys", icon: LockKeyhole },
    { id: "billing", label: "Billing", icon: CreditCard },
  ];
  const activeSidebarItem = sidebarItems.find((item) => item.id === activeSection);

  async function loadInferenceStatus() {
    if (previewMode || !dashboardToken) {
      return;
    }
    setInferenceLoading(true);
    try {
      const response = await fetch(`${API_BASE}/dashboard/inference-status`, {
        headers: { Authorization: `Bearer ${dashboardToken}` },
      });
      if (!response.ok) {
        throw new Error(`Inference status failed: ${response.status}`);
      }
      setInferenceStatus((await response.json()) as InferenceStatus);
    } catch (caught) {
      setInferenceStatus({
        status: "offline",
        runtime: "hosted",
        model: "inference-service-unavailable",
        model_loaded: false,
        fallback_used: true,
        latency_ms: 0,
        error: caught instanceof Error ? caught.message : "Unable to reach inference status.",
      });
    } finally {
      setInferenceLoading(false);
    }
  }

  useEffect(() => {
    if (!dashboard || previewMode) {
      return;
    }
    void loadInferenceStatus();
  }, [dashboard?.tenant.tenant_id, dashboardToken, previewMode]);

  return (
    <>
      <AnimatePresence>
        {dashboard && workspaceShieldTenant === dashboard.tenant.tenant_id ? (
          <WorkspaceShieldMergeAnimation onComplete={onWorkspaceShieldComplete} />
        ) : null}
      </AnimatePresence>
      <div className="grid w-full min-w-0 gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="min-w-0 space-y-4">
        <Badge variant="outline" className="mb-4 gap-2">
          <BarChart3 className="h-3.5 w-3.5" />
          Client dashboard
        </Badge>

        {!clerkEnabled ? (
          <Card className="dark:border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LogIn className="h-5 w-5 text-teal-700" />
                Tenant access
              </CardTitle>
              <CardDescription>Use a tenant admin key. Moderation keys are only for API requests.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3">
                <input
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Paste tenant admin key"
                  type="password"
                />
                <Button onClick={onLogin} disabled={loading || !apiKey.trim()} className="w-full">
                  {loading ? "Loading..." : "Open dashboard"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
              {error ? <p className="mt-3 text-sm text-red-600 dark:text-red-300">{error}</p> : null}
              {saved ? <p className="mt-3 text-sm text-emerald-700 dark:text-emerald-300">{saved}</p> : null}
            </CardContent>
          </Card>
        ) : (
          <Card className="dark:border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LogIn className="h-5 w-5 text-teal-700" />
                {previewMode ? "Example workspace" : "Workspaces"}
              </CardTitle>
              <CardDescription>
                {previewMode
                  ? "Static preview data that mirrors the signed-in client dashboard."
                  : workspaceLookupLoading
                    ? "Checking for an existing workspace..."
                    : "Switch between workspaces or create a separate setup."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {dashboard && !previewMode && workspaces.length ? (
                <select
                  value={dashboard.tenant.tenant_id}
                  onChange={(event) => onSwitchWorkspace(event.target.value)}
                  disabled={loading}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  {workspaces.map((workspace) => (
                    <option key={workspace.tenant_id} value={workspace.tenant_id}>
                      {workspace.tenant_name}
                    </option>
                  ))}
                </select>
              ) : null}

              {dashboard && !previewMode ? (
                <div className="grid gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => {
                      setShowWorkspaceRename((current) => !current);
                      setWorkspaceRename(dashboard.tenant.tenant_name);
                    }}
                  >
                    {showWorkspaceRename ? "Cancel" : "Rename"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => {
                      setShowWorkspaceCreate((current) => !current);
                      setShowWorkspaceCreateConfirm(false);
                    }}
                  >
                    {showWorkspaceCreate ? "Cancel" : "Create workspace"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full whitespace-normal text-red-600 hover:text-red-700 dark:text-red-300"
                    onClick={() => setShowWorkspaceDeleteConfirm(true)}
                    disabled={loading || workspaces.length <= 1}
                    title={workspaces.length <= 1 ? "Create another workspace before deleting this one." : "Delete workspace"}
                  >
                    Delete workspace
                  </Button>
                </div>
              ) : null}

              {dashboard && !previewMode && showWorkspaceDeleteConfirm ? (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-950 dark:border-red-400/25 dark:bg-red-950/35 dark:text-red-100">
                  <p className="font-medium">Are you sure you want to delete this workspace {dashboard.tenant.tenant_name}?</p>
                  <p className="mt-1 text-xs text-red-900/75 dark:text-red-100/70">
                    Its API keys will stop working. Remaining credits stay shared across your existing workspaces.
                  </p>
                  <div className="mt-3 grid gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setShowWorkspaceDeleteConfirm(false)}
                      disabled={loading}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="w-full bg-red-600 text-white hover:bg-red-700"
                      onClick={() => {
                        setShowWorkspaceDeleteConfirm(false);
                        onDeleteWorkspace();
                      }}
                      disabled={loading}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ) : null}

              {dashboard && !previewMode && showWorkspaceRename ? (
                <div className="grid gap-2 rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70">
                  <input
                    value={workspaceRename}
                    onChange={(event) => setWorkspaceRename(event.target.value)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                    placeholder="New workspace name"
                  />
                  <Button
                    onClick={onRenameWorkspace}
                    disabled={
                      loading ||
                      workspaceRename.trim().length < 2 ||
                      workspaceRename.trim() === dashboard.tenant.tenant_name
                    }
                    size="sm"
                  >
                    {loading ? "Renaming..." : "Save name"}
                    <CheckCircle2 className="h-4 w-4" />
                  </Button>
                </div>
              ) : null}

              {dashboard && !previewMode && showWorkspaceCreate ? (
                <div className="grid gap-2 rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70">
                  <input
                    value={workspaceName}
                    onChange={(event) => setWorkspaceName(event.target.value)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Workspace name"
                  />
                  <Button
                    onClick={() => setShowWorkspaceCreateConfirm(true)}
                    disabled={loading || workspaceName.trim().length < 2}
                    size="sm"
                  >
                    {loading ? "Creating..." : "Create"}
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </div>
              ) : null}

              {dashboard && !previewMode && showWorkspaceCreateConfirm ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-400/25 dark:bg-amber-950/35 dark:text-amber-100">
                  <p className="font-medium">Create another workspace?</p>
                  <p className="mt-1 text-xs text-amber-900/80 dark:text-amber-100/75">
                    New workspaces use shared account billing by default. This means the workspace will use your current plan
                    and draw from the same monthly credits unless you switch it to separate workspace billing later.
                  </p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setShowWorkspaceCreateConfirm(false)}
                      disabled={loading}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        setShowWorkspaceCreateConfirm(false);
                        onCreateWorkspace();
                      }}
                      disabled={loading}
                    >
                      Create
                    </Button>
                  </div>
                </div>
              ) : null}

              {error ? <p className="text-sm text-red-600 dark:text-red-300">{error}</p> : null}
              {saved ? <p className="text-sm text-emerald-700 dark:text-emerald-300">{saved}</p> : null}
            </CardContent>
          </Card>
        )}

        {dashboard ? (
          <nav className="rounded-lg border border-border bg-background p-2 dark:border-white/10">
            {sidebarItems.map((item) => {
              const lockedPreviewItem = previewMode && item.id !== "overview";
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveSection(item.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium transition",
                    activeSection === item.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  <span className="min-w-0 flex-1">{item.label}</span>
                  {lockedPreviewItem ? <LockKeyhole className="h-3.5 w-3.5" /> : null}
                </button>
              );
            })}
          </nav>
        ) : null}
      </aside>

      <div className="min-w-0 space-y-5">
        {dashboard ? (
          <>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-2xl font-semibold tracking-normal text-slate-950 dark:text-white">
                    {dashboard.tenant.tenant_name}
                  </h2>
                  <Badge variant={dashboard.usage.billing_scope === "workspace" ? "secondary" : "outline"} className="capitalize">
                    {dashboard.usage.plan_name}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {dashboard.policy.labels.join(", ")} | usage month {dashboard.usage.month}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading || previewMode}>
                <RefreshCw className="h-4 w-4" />
                {previewMode ? "Preview" : "Refresh"}
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <UsageTile
                label={`${dashboard.usage.billing_scope === "workspace" ? "Workspace" : "Shared"} credits of ${dashboard.usage.monthly_quota}`}
                value={dashboard.usage.total_requests}
                icon={BarChart3}
              />
              <UsageTile label="Credits left" value={dashboard.usage.remaining_requests} icon={Gauge} />
              <UsageTile label="Approved" value={dashboard.usage.allow} icon={CheckCircle2} tone="success" />
              <UsageTile label="Review" value={dashboard.usage.review} icon={Radar} tone="warning" />
              <UsageTile label="Blocked" value={dashboard.usage.block} icon={XCircle} tone="danger" />
            </div>

            {!previewMode ? (
              <InferenceStatusPanel
                status={inferenceStatus}
                loading={inferenceLoading}
                onRefresh={loadInferenceStatus}
              />
            ) : null}

            {!previewMode ? (
              <OnboardingChecklist
                dashboard={dashboard}
                apiKeys={apiKeys}
                reviewCases={reviewCases}
                billingStatus={billingStatus}
              />
            ) : null}

            {activeSection === "overview" ? (
              <MarketplaceOverview dashboard={dashboard} />
            ) : null}

            {previewMode && activeSection !== "overview" ? (
              <LockedPreviewPanel title={activeSidebarItem?.label ?? "Dashboard feature"} />
            ) : null}

            {!previewMode && activeSection === "playground" ? (
              <ModerationPlaygroundPanel
                dashboardToken={dashboardToken}
                loading={loading}
                onComplete={onPlaygroundComplete}
              />
            ) : null}

            {!previewMode && activeSection === "guide" ? (
              <DashboardHowToUsePanel onSelectSection={setActiveSection} />
            ) : null}

            {!previewMode && activeSection === "integrations" ? (
              <IntegrationCenterPanel
                dashboard={dashboard}
                apiKeys={apiKeys}
                billingStatus={billingStatus}
                reviewCases={reviewCases}
              />
            ) : null}

            {!previewMode && activeSection === "docs" ? (
              <ApiDocsPanel apiKeys={apiKeys} />
            ) : null}

            {!previewMode && activeSection === "social" ? (
              <SocialInboxPanel
                connectedAccounts={connectedAccounts}
                socialEvents={socialEvents}
                loading={loading}
                onConnectSocialAccount={onConnectSocialAccount}
                onStartMetaOAuth={onStartMetaOAuth}
                onDisconnectSocialAccount={onDisconnectSocialAccount}
                onDeleteSocialAccount={onDeleteSocialAccount}
                onCreateSocialEvent={onCreateSocialEvent}
                onApplySocialAction={onApplySocialAction}
              />
            ) : null}

            {!previewMode && activeSection === "review" ? (
              <ReviewCasesPanel
                reviewCases={reviewCases}
                caseNotes={caseNotes}
                loading={loading}
                setCaseNotes={setCaseNotes}
                onUpdateReviewCase={onUpdateReviewCase}
              />
            ) : null}

            {!previewMode && activeSection === "policy" ? (
              <PolicyThresholdsPanel
                policy={dashboard.policy}
                thresholdRows={thresholdRows}
                loading={loading}
                onThresholdChange={onThresholdChange}
                onPolicyFlagChange={onPolicyFlagChange}
                onSave={onSave}
              />
            ) : null}

            {!previewMode && activeSection === "keys" ? (
              <ApiKeysPanel
                apiKeys={apiKeys}
                apiKeyUsage={apiKeyUsage}
                newKeyName={newKeyName}
                createdApiKey={createdApiKey}
                loading={loading}
                setNewKeyName={setNewKeyName}
                onCreateModerationKey={onCreateModerationKey}
                onDeactivateApiKey={onDeactivateApiKey}
                onRotateApiKey={onRotateApiKey}
              />
            ) : null}

            {!previewMode && activeSection === "billing" ? (
              <BillingPanel
                billingStatus={billingStatus}
                usage={dashboard.usage}
                loading={loading}
                onStartCheckout={onStartBillingCheckout}
                onOpenPortal={onOpenBillingPortal}
                onUpdateBillingScope={onUpdateBillingScope}
              />
            ) : null}
          </>
        ) : workspaceLookupLoading ? (
          <Card className="min-h-80 items-center justify-center border-dashed bg-white/70 dark:border-white/10 dark:bg-white/[0.04]">
            <CardContent className="flex min-h-80 flex-col items-center justify-center text-center">
              <RefreshCw className="mb-4 h-10 w-10 animate-spin text-teal-700" />
              <p className="text-lg font-semibold text-slate-950 dark:text-white">Checking workspace</p>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Loading the workspace connected to your Clerk account.
              </p>
            </CardContent>
          </Card>
        ) : clerkEnabled ? (
          <Card className="dark:border-white/10">
            <CardHeader>
              <CardTitle>Create your first workspace</CardTitle>
              <CardDescription>
                Name the app, community, marketplace, or creator account you want to protect.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-5 grid gap-3 md:grid-cols-3">
                {[
                  "Create the workspace",
                  "Copy the one-time moderation key",
                  "Run the first API call",
                ].map((step, index) => (
                  <div key={step} className="rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70">
                    <span className="mb-2 flex h-7 w-7 items-center justify-center rounded-md bg-teal-600 text-xs font-semibold text-white">
                      {index + 1}
                    </span>
                    <p className="text-sm font-medium text-slate-900 dark:text-white">{step}</p>
                  </div>
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <input
                  value={workspaceName}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Workspace name"
                />
                <Button onClick={onCreateWorkspace} disabled={loading || workspaceName.trim().length < 2}>
                  {loading ? "Creating..." : "Create workspace"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-5 rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
                <p className="text-sm font-medium text-slate-900 dark:text-white">Already created a workspace?</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Sign in with the same account and it will open automatically. API keys are shown separately after setup.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="min-h-80 items-center justify-center border-dashed bg-white/70 dark:border-white/10 dark:bg-white/[0.04]">
            <CardContent className="flex min-h-80 flex-col items-center justify-center text-center">
              <LockKeyhole className="mb-4 h-10 w-10 text-teal-700" />
              <p className="text-lg font-semibold text-slate-950 dark:text-white">Dashboard locked</p>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Enter a tenant admin key in the sidebar to load usage, decisions, and policy controls.
              </p>
            </CardContent>
          </Card>
        )}

        {dashboard && onboardingModerationKey ? (
          <>
            <OneTimeKeyBox title="Your first moderation API key" apiKey={onboardingModerationKey} />
            <FirstApiCallPanel apiKey={onboardingModerationKey} workspaceId={dashboard.tenant.tenant_id} />
          </>
        ) : null}
      </div>
      </div>
    </>
  );
}

function WorkspaceShieldMergeAnimation({ onComplete }: { onComplete: () => void }) {
  useEffect(() => {
    const timeoutId = window.setTimeout(onComplete, 2200);
    return () => window.clearTimeout(timeoutId);
  }, [onComplete]);

  return (
    <motion.div
      className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <motion.div
        className="relative flex h-44 w-44 items-center justify-center"
        initial={{ scale: 0.92 }}
        animate={{ scale: [0.92, 1, 1, 0.84], opacity: [1, 1, 1, 0] }}
        transition={{ duration: 1.85, times: [0, 0.36, 0.72, 1], ease: "easeInOut" }}
      >
        <motion.span
          className="absolute h-40 w-40 rounded-full border border-teal-300/60"
          initial={{ opacity: 0, scale: 0.65 }}
          animate={{ opacity: [0, 0.7, 0], scale: [0.65, 1.18, 1.5] }}
          transition={{ delay: 0.58, duration: 0.95, ease: "easeOut" }}
        />
        <motion.span
          className="absolute h-24 w-24 rounded-full bg-teal-400/15 blur-xl"
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: [0, 1, 0], scale: [0.6, 1.35, 1.55] }}
          transition={{ delay: 0.5, duration: 1.05, ease: "easeOut" }}
        />
        <div className="relative h-28 w-28">
          <motion.div
            className="absolute inset-0 overflow-hidden text-teal-200 drop-shadow-[0_0_22px_rgba(45,212,191,0.75)]"
            style={{ clipPath: "inset(0 50% 0 0)" }}
            initial={{ x: -170, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 0.62, ease: [0.16, 1, 0.3, 1] }}
          >
            <ShieldCheck strokeWidth={1.7} className="h-28 w-28" />
          </motion.div>
          <motion.div
            className="absolute inset-0 overflow-hidden text-teal-200 drop-shadow-[0_0_22px_rgba(45,212,191,0.75)]"
            style={{ clipPath: "inset(0 0 0 50%)" }}
            initial={{ x: 170, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 0.62, ease: [0.16, 1, 0.3, 1] }}
          >
            <ShieldCheck strokeWidth={1.7} className="h-28 w-28" />
          </motion.div>
          <motion.div
            className="absolute inset-0 text-white"
            initial={{ opacity: 0, scale: 0.86 }}
            animate={{ opacity: [0, 1, 1, 0], scale: [0.86, 1, 1.02, 0.92] }}
            transition={{ delay: 0.62, duration: 1.1, times: [0, 0.2, 0.62, 1], ease: "easeOut" }}
          >
            <ShieldCheck strokeWidth={2.3} className="h-28 w-28" />
          </motion.div>
        </div>
      </motion.div>
    </motion.div>
  );
}

function InferenceStatusPanel({
  status,
  loading,
  onRefresh,
}: {
  status: InferenceStatus | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const online = status?.status === "online" && status.model_loaded && !status.fallback_used;
  const title = online ? "Inference online" : status ? "Inference fallback active" : "Checking inference";
  const modelLabel = status?.model ?? "checking";
  const runtimeLabel = status ? `${status.runtime} service` : "unknown service";

  return (
    <Card className="dark:border-white/10">
      <CardContent className="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-md",
              online
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
                : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-200",
            )}
          >
            <Activity className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium text-slate-950 dark:text-white">{title}</p>
              <Badge variant={online ? "success" : "secondary"}>{status?.status ?? "checking"}</Badge>
              <Badge variant="outline">{runtimeLabel}</Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Model {modelLabel}
              {status?.latency_ms ? ` | ${status.latency_ms}ms health check` : ""}
            </p>
            {!online ? (
              <p className="mt-2 text-sm text-amber-700 dark:text-amber-200">
                Text moderation will still run, but results are lower-confidence when the transformer service is unavailable.
              </p>
            ) : null}
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          <RefreshCw className={cn("h-4 w-4", loading ? "animate-spin" : "")} />
          Refresh
        </Button>
      </CardContent>
    </Card>
  );
}

function OnboardingChecklist({
  dashboard,
  apiKeys,
  reviewCases,
  billingStatus,
}: {
  dashboard: DashboardSummary;
  apiKeys: ApiKeyInfo[];
  reviewCases: ReviewCase[];
  billingStatus: BillingStatus | null;
}) {
  const steps = getIntegrationReadiness({ dashboard, apiKeys, reviewCases, billingStatus });

  return (
    <Card className="dark:border-white/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-teal-700" />
          Workspace checklist
        </CardTitle>
        <CardDescription>Complete these steps to move this workspace from setup to production use.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-5">
          {steps.map((step) => (
            <div key={step.label} className="rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-900 dark:text-white">{step.label}</p>
                <Badge variant={step.done ? "success" : "outline"}>{step.done ? "done" : "todo"}</Badge>
              </div>
              <p className="text-xs text-muted-foreground">{step.detail}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

type IntegrationReadinessStep = {
  label: string;
  done: boolean;
  detail: string;
  action: string;
};

function getIntegrationReadiness({
  dashboard,
  apiKeys,
  reviewCases,
  billingStatus,
}: {
  dashboard: DashboardSummary;
  apiKeys: ApiKeyInfo[];
  reviewCases: ReviewCase[];
  billingStatus: BillingStatus | null;
}): IntegrationReadinessStep[] {
  const hasModerationKey = apiKeys.some((key) => key.is_active && key.scopes.includes("moderation"));

  return [
    {
      label: "Create workspace",
      done: Boolean(dashboard.tenant.tenant_id),
      detail: "Tenant identity exists and can be used for dashboard ownership.",
      action: "Create a workspace so traffic, keys, policy, and billing stay isolated.",
    },
    {
      label: "Create moderation key",
      done: hasModerationKey,
      detail: "Use a moderation key only from your server or trusted backend.",
      action: "Open API keys and create an active moderation key for server requests.",
    },
    {
      label: "Send first request",
      done: dashboard.usage.total_requests > 0,
      detail: "Live requests appear in marketplace decisions, usage, and review queues.",
      action: "Run the smoke test below from a terminal with your moderation key.",
    },
    {
      label: "Review flagged content",
      done: reviewCases.some((reviewCase) => reviewCase.status !== "open"),
      detail: "A real workflow needs start, resolve, dismiss, and assignee handling.",
      action: "Trigger a review decision, then resolve or dismiss one case from the review queue.",
    },
    {
      label: "Confirm billing plan",
      done: Boolean(billingStatus && billingStatus.subscription_status !== "trialing"),
      detail: "Production traffic should have clear credits, a plan, and an upgrade path.",
      action: "Keep trial for testing, then select the plan before real customer traffic.",
    },
  ];
}

function DashboardHowToUsePanel({ onSelectSection }: { onSelectSection: (section: DashboardSection) => void }) {
  const [selectedPathId, setSelectedPathId] = useState<GuideAudience>("nontechnical");
  const selectedPath = howToUsePaths.find((path) => path.id === selectedPathId) ?? howToUsePaths[0];
  const actionTargets: Partial<Record<string, DashboardSection>> = {
    Marketplace: "overview",
    Playground: "playground",
    "Integration center": "integrations",
    "API docs": "docs",
    "Social inbox": "social",
    "Review cases": "review",
    "Policy thresholds": "policy",
    "API keys": "keys",
    Billing: "billing",
  };

  return (
    <div className="grid gap-5">
      <Card className="dark:border-white/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-teal-700" />
            How to use Guard API
          </CardTitle>
          <CardDescription>
            Pick a path based on whether you are operating the dashboard, integrating the API, or rolling it out for a team.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {howToUsePaths.map((path) => (
              <button
                key={path.id}
                type="button"
                onClick={() => setSelectedPathId(path.id)}
                className={cn(
                  "rounded-lg border p-4 text-left transition",
                  selectedPath.id === path.id
                    ? "border-teal-500 bg-teal-50 text-slate-950 shadow-sm dark:bg-teal-950/30 dark:text-white"
                    : "border-border bg-background hover:bg-accent",
                )}
              >
                <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-white text-teal-700 shadow-sm dark:bg-slate-950 dark:text-teal-200">
                  <path.icon className="h-5 w-5" />
                </span>
                <span className="block text-sm font-medium">{path.label}</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">{path.summary}</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="dark:border-white/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <selectedPath.icon className="h-5 w-5 text-teal-700" />
              {selectedPath.title}
            </CardTitle>
            <CardDescription>{selectedPath.summary}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3">
              {selectedPath.steps.map((step, index) => (
                <div key={step} className="grid grid-cols-[34px_1fr] gap-3 rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-600 text-sm font-semibold text-white">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-6 text-slate-700 dark:text-slate-200">{step}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="dark:border-white/10">
          <CardHeader>
            <CardTitle className="text-base">Open the right area</CardTitle>
            <CardDescription>Jump to the dashboard section that matches this guide.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2">
              {selectedPath.dashboardActions.map((action) => {
                const target = actionTargets[action];
                return target ? (
                  <Button key={action} type="button" variant="outline" className="justify-start" onClick={() => onSelectSection(target)}>
                    <ArrowRight className="h-4 w-4" />
                    {action}
                  </Button>
                ) : (
                  <div key={action} className="rounded-lg border border-border bg-slate-50 p-3 text-sm text-muted-foreground dark:bg-slate-950/70">
                    {action}
                  </div>
                );
              })}
            </div>

            <div className="mt-5 rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
              <p className="text-sm font-medium text-slate-900 dark:text-white">Best for</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedPath.useCases.map((useCase) => (
                  <Badge key={useCase} variant="secondary">{useCase}</Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function IntegrationCenterPanel({
  dashboard,
  apiKeys,
  billingStatus,
  reviewCases,
}: {
  dashboard: DashboardSummary;
  apiKeys: ApiKeyInfo[];
  billingStatus: BillingStatus | null;
  reviewCases: ReviewCase[];
}) {
  const activeModerationKey = apiKeys.find((key) => key.is_active && key.scopes.includes("moderation"));
  const keyPlaceholder = activeModerationKey ? `${activeModerationKey.key_prefix}...` : "rtcm_your_moderation_key";
  const steps = getIntegrationReadiness({ dashboard, apiKeys, reviewCases, billingStatus });
  const completedSteps = steps.filter((step) => step.done).length;
  const readinessPercent = Math.round((completedSteps / steps.length) * 100);
  const nextStep = steps.find((step) => !step.done);
  const smokeTestCurl = `curl -X POST ${API_BASE}/moderate/text \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${keyPlaceholder}" \\
  -d '{
    "text": "Can you check this marketplace message before it is posted?",
    "metadata": {
      "channel": "marketplace_chat",
      "workspace": "${dashboard.tenant.tenant_id}"
    }
  }'`;
  const serverEnv = `RTCM_API_BASE_URL=${API_BASE}
RTCM_MODERATION_KEY=${keyPlaceholder}
RTCM_WEBHOOK_SECRET=generate-a-long-random-secret`;

  return (
    <div className="grid gap-5">
      <Card className="dark:border-white/10">
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-teal-700" />
              Integration readiness
            </CardTitle>
            <CardDescription>Customer-facing launch checks for this workspace.</CardDescription>
          </div>
          <Badge variant={readinessPercent === 100 ? "success" : "secondary"}>{readinessPercent}% ready</Badge>
        </CardHeader>
        <CardContent>
          <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <div>
              <div className="mb-3 h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                <div className="h-2 rounded-full bg-teal-600" style={{ width: `${readinessPercent}%` }} />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {steps.map((step) => (
                  <ReadinessStepTile key={step.label} step={step} />
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
              <p className="text-sm font-medium text-slate-900 dark:text-white">Next best action</p>
              <p className="mt-2 text-sm text-muted-foreground">
                {nextStep ? nextStep.action : "This workspace has the internal checklist complete. Keep testing with real user flows before public launch."}
              </p>
              <div className="mt-4 grid gap-2">
                <ApiDocTile label="Workspace" value={dashboard.tenant.tenant_name} />
                <ApiDocTile label="Tenant ID" value={dashboard.tenant.tenant_id} />
                <ApiDocTile label="Moderation key" value={keyPlaceholder} />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <CodeSnippet title="Smoke test command" subtitle="Run after creating a moderation key" code={smokeTestCurl} />
        <CodeSnippet title="Server environment" subtitle="Keep secrets outside the frontend" code={serverEnv} />
      </div>

      <CustomerCodeExamples />

      <Card className="dark:border-white/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Code2 className="h-5 w-5 text-teal-700" />
            Product wiring map
          </CardTitle>
          <CardDescription>Connect moderation decisions to concrete actions in the customer app.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <ApiDocTile label="allow" value="Publish immediately and store the request ID for audit." />
            <ApiDocTile label="review" value="Hold content, show pending state, and route the case to reviewers." />
            <ApiDocTile label="block" value="Stop submission, show a policy-safe message, and log the reason." />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ReadinessStepTile({ step }: { step: IntegrationReadinessStep }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-slate-900 dark:text-white">{step.label}</p>
        <Badge variant={step.done ? "success" : "outline"}>{step.done ? "done" : "todo"}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">{step.detail}</p>
    </div>
  );
}

function CustomerCodeExamples() {
  const [selectedExample, setSelectedExample] = useState<"node" | "python">("node");
  const [selectedEndpoint, setSelectedEndpoint] = useState<"text" | "image" | "audio" | "video">("text");
  const endpointOptions: Array<{ id: "text" | "image" | "audio" | "video"; label: string; subtitle: string }> = [
    { id: "text", label: "Text", subtitle: "Comments, chat, captions" },
    { id: "image", label: "Image", subtitle: "Uploads, screenshots, OCR" },
    { id: "audio", label: "Audio", subtitle: "Voice notes, calls, clips" },
    { id: "video", label: "Video", subtitle: "Uploads, reels, livestream clips" },
  ];
  const codeByEndpoint = {
    text: {
      title: selectedExample === "node" ? "Node Express text route" : "Python FastAPI text route",
      subtitle: "POST /moderate/text with decision handling",
      code: selectedExample === "node" ? nodeExpressTemplate : pythonFastApiTemplate,
    },
    image: {
      title: selectedExample === "node" ? "Node image upload" : "Python image upload",
      subtitle: "POST /moderate/image with file, caption, and OCR fields",
      code: selectedExample === "node" ? nodeImageTemplate : pythonImageTemplate,
    },
    audio: {
      title: selectedExample === "node" ? "Node audio upload" : "Python audio upload",
      subtitle: "POST /moderate/audio with file and optional transcript hint",
      code: selectedExample === "node" ? nodeAudioTemplate : pythonAudioTemplate,
    },
    video: {
      title: selectedExample === "node" ? "Node video upload" : "Python video upload",
      subtitle: "POST /moderate/video with file, transcript, frame, OCR, and object hints",
      code: selectedExample === "node" ? nodeVideoTemplate : pythonVideoTemplate,
    },
  };
  const activeCode = codeByEndpoint[selectedEndpoint];

  return (
    <Card className="dark:border-white/10">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Code2 className="h-5 w-5 text-teal-700" />
              Customer integration code
            </CardTitle>
            <CardDescription>
              Use these as backend templates. Customers must add their own Guard key, request fields, and publish/review/block logic.
            </CardDescription>
          </div>
          <div className="flex rounded-lg border border-border bg-slate-50 p-1 dark:bg-slate-950/70">
            <button
              type="button"
              onClick={() => setSelectedExample("node")}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition",
                selectedExample === "node" ? "bg-background text-slate-950 shadow-sm dark:text-white" : "text-muted-foreground",
              )}
            >
              Node
            </button>
            <button
              type="button"
              onClick={() => setSelectedExample("python")}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition",
                selectedExample === "python" ? "bg-background text-slate-950 shadow-sm dark:text-white" : "text-muted-foreground",
              )}
            >
              Python
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <ApiDocTile label="Set env vars" value="Add GUARD_API_URL and GUARD_API_KEY on the backend only." />
          <ApiDocTile label="Map app data" value="Replace sample fields with your real text, file, user ID, and content ID." />
          <ApiDocTile label="Wire decisions" value="Replace publish, hold, and reject placeholders with your app logic." />
        </div>
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-400/25 dark:bg-amber-950/35 dark:text-amber-100">
          The code is not a zero-change drop-in. It shows where to call Guard API and how to read the decision. Functions such as publishImage,
          holdForModerator, and rejectVideo must be connected to the customer's own database, upload storage, queue, or publishing system.
        </div>
        <div className="mb-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {endpointOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setSelectedEndpoint(option.id)}
              className={cn(
                "rounded-lg border p-3 text-left transition",
                selectedEndpoint === option.id
                  ? "border-teal-500 bg-teal-50 text-slate-950 shadow-sm dark:bg-teal-950/30 dark:text-white"
                  : "border-border bg-background hover:bg-accent",
              )}
            >
              <span className="block text-sm font-medium">{option.label}</span>
              <span className="mt-1 block text-xs text-muted-foreground">{option.subtitle}</span>
            </button>
          ))}
        </div>
        <CodeSnippet title={activeCode.title} subtitle={activeCode.subtitle} code={activeCode.code} />
      </CardContent>
    </Card>
  );
}

function EmptyStatePanel({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof BarChart3;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-slate-50 p-6 text-center dark:bg-slate-950/70">
      <span className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-200">
        <Icon className="h-5 w-5" />
      </span>
      <p className="text-sm font-medium text-slate-900 dark:text-white">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

type PlaygroundMode = "text" | "image" | "audio" | "video" | "social";

const playgroundModes: Array<{ id: PlaygroundMode; label: string; icon: typeof Radar }> = [
  { id: "text", label: "Text", icon: Code2 },
  { id: "image", label: "Image", icon: ImageIcon },
  { id: "audio", label: "Audio", icon: FileAudio },
  { id: "video", label: "Video", icon: Film },
  { id: "social", label: "Social comment", icon: Workflow },
];

const playgroundSamples = [
  {
    label: "Marketplace scam",
    text: "Guaranteed profit investment. Send OTP and bank details now.",
  },
  {
    label: "Harassment",
    text: "You are worthless and I will find you after school.",
  },
  {
    label: "Safe message",
    text: "Thanks for the quick delivery. Can you share the invoice?",
  },
];

function ModerationPlaygroundPanel({
  dashboardToken,
  loading,
  onComplete,
}: {
  dashboardToken: string;
  loading: boolean;
  onComplete: () => void | Promise<void>;
}) {
  const [mode, setMode] = useState<PlaygroundMode>("text");
  const [text, setText] = useState(playgroundSamples[0].text);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageCaption, setImageCaption] = useState("Marketplace upload showing payment proof and a WhatsApp number.");
  const [imageObjects, setImageObjects] = useState("phone, payment screenshot, cash");
  const [imageOcr, setImageOcr] = useState("guaranteed profit send otp");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioTranscript, setAudioTranscript] = useState("Send your OTP right now or your account will be blocked.");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoTranscript, setVideoTranscript] = useState("Message me on Telegram for guaranteed profit.");
  const [videoFrameDescription, setVideoFrameDescription] = useState("A screen recording showing payment instructions.");
  const [videoOcr, setVideoOcr] = useState("send money now guaranteed return");
  const [videoObjects, setVideoObjects] = useState("phone, chat, payment app");
  const [socialActor, setSocialActor] = useState("beta_user");
  const [result, setResult] = useState<ModerationResult | null>(null);
  const [socialResult, setSocialResult] = useState<SocialEvent | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const disabled = loading || submitting || !dashboardToken;

  async function submitPlayground() {
    setSubmitting(true);
    setError("");
    setResult(null);
    setSocialResult(null);
    try {
      const response = await sendPlaygroundRequest();
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`Playground request failed: ${response.status} ${detail}`);
      }
      if (mode === "social") {
        setSocialResult((await response.json()) as SocialEvent);
      } else {
        setResult((await response.json()) as ModerationResult);
      }
      await onComplete();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to run playground scan.");
    } finally {
      setSubmitting(false);
    }
  }

  async function sendPlaygroundRequest() {
    const authHeaders = { Authorization: `Bearer ${dashboardToken}` };
    const metadata = { channel: `playground_${mode}`, region: "global" };
    if (mode === "text") {
      return fetch(`${API_BASE}/playground/moderate/text`, {
        method: "POST",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ text, metadata }),
      });
    }
    if (mode === "image") {
      if (imageFile) {
        const formData = new FormData();
        formData.append("image", imageFile);
        formData.append("image_caption", imageCaption);
        formData.append("detected_objects", imageObjects);
        formData.append("ocr_text", imageOcr);
        formData.append("channel", "playground_image");
        formData.append("region", "global");
        return fetch(`${API_BASE}/playground/moderate/image`, {
          method: "POST",
          headers: authHeaders,
          body: formData,
        });
      }
      return fetch(`${API_BASE}/playground/moderate/image`, {
        method: "POST",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({
          image_caption: imageCaption,
          detected_objects: splitCommaList(imageObjects),
          ocr_text: imageOcr,
          metadata,
        }),
      });
    }
    if (mode === "audio") {
      if (audioFile) {
        const formData = new FormData();
        formData.append("audio", audioFile);
        formData.append("transcript_hint", audioTranscript);
        formData.append("channel", "playground_audio");
        formData.append("region", "global");
        return fetch(`${API_BASE}/playground/moderate/audio`, {
          method: "POST",
          headers: authHeaders,
          body: formData,
        });
      }
      return fetch(`${API_BASE}/playground/moderate/audio`, {
        method: "POST",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ transcript_hint: audioTranscript, metadata }),
      });
    }
    if (mode === "video") {
      const frame = {
        timestamp_ms: 1000,
        description: videoFrameDescription,
        ocr_text: videoOcr,
        detected_objects: splitCommaList(videoObjects),
      };
      if (videoFile) {
        const formData = new FormData();
        formData.append("video", videoFile);
        formData.append("transcript_hint", videoTranscript);
        formData.append("frames", JSON.stringify([frame]));
        formData.append("channel", "playground_video");
        formData.append("region", "global");
        return fetch(`${API_BASE}/playground/moderate/video`, {
          method: "POST",
          headers: authHeaders,
          body: formData,
        });
      }
      return fetch(`${API_BASE}/playground/moderate/video`, {
        method: "POST",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ transcript_hint: videoTranscript, frames: [frame], metadata }),
      });
    }
    return fetch(`${API_BASE}/connectors/webhook/events`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({
        platform: "webhook",
        source_type: "comment",
        actor_handle: socialActor,
        external_event_id: `playground_${Date.now()}`,
        content_text: text,
        raw_payload: { source: "dashboard-playground" },
        metadata,
      }),
    });
  }

  const visibleResult = result ?? socialResult;
  const action = result?.decision.action ?? socialResult?.decision_action;
  const triggeredCategories =
    result?.decision.triggered_categories ?? socialResult?.triggered_categories ?? [];

  return (
    <div className="grid gap-5">
      <Card className="dark:border-white/10">
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Radar className="h-5 w-5 text-teal-700" />
              Moderation playground
            </CardTitle>
            <CardDescription>
              Test moderation inside this workspace without building an app or copying a raw API key.
            </CardDescription>
          </div>
          <Badge variant="secondary">Saved to workspace</Badge>
        </CardHeader>
        <CardContent>
          <div className="mb-5 grid gap-2 sm:grid-cols-5">
            {playgroundModes.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setMode(item.id);
                  setError("");
                  setResult(null);
                  setSocialResult(null);
                }}
                className={cn(
                  "flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition",
                  mode === item.id
                    ? "border-teal-500 bg-teal-50 text-teal-900 dark:bg-teal-950/35 dark:text-teal-100"
                    : "border-border bg-background text-muted-foreground hover:bg-accent",
                )}
              >
                <item.icon className="h-4 w-4" />
                <span>{item.label}</span>
              </button>
            ))}
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
            <div className="space-y-4">
              {mode === "text" || mode === "social" ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    {playgroundSamples.map((sample) => (
                      <Button key={sample.label} type="button" variant="outline" size="sm" onClick={() => setText(sample.text)}>
                        {sample.label}
                      </Button>
                    ))}
                  </div>
                  {mode === "social" ? (
                    <input
                      value={socialActor}
                      onChange={(event) => setSocialActor(event.target.value)}
                      className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                      placeholder="Actor handle"
                    />
                  ) : null}
                  <Textarea
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    className="min-h-40"
                    placeholder="Paste a message, comment, listing, review, or form submission"
                  />
                </>
              ) : null}

              {mode === "image" ? (
                <div className="space-y-3">
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-slate-50 p-6 text-center dark:bg-slate-950/70">
                    <UploadCloud className="mb-2 h-8 w-8 text-teal-700" />
                    <span className="text-sm font-medium text-slate-900 dark:text-white">
                      {imageFile ? imageFile.name : "Upload an image or use the fields below"}
                    </span>
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      className="hidden"
                      onChange={(event) => setImageFile(event.target.files?.[0] ?? null)}
                    />
                  </label>
                  <Textarea value={imageCaption} onChange={(event) => setImageCaption(event.target.value)} placeholder="Image caption or scene description" />
                  <input value={imageObjects} onChange={(event) => setImageObjects(event.target.value)} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring" placeholder="Detected objects, comma separated" />
                  <input value={imageOcr} onChange={(event) => setImageOcr(event.target.value)} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring" placeholder="OCR text from image" />
                </div>
              ) : null}

              {mode === "audio" ? (
                <div className="space-y-3">
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-slate-50 p-6 text-center dark:bg-slate-950/70">
                    <UploadCloud className="mb-2 h-8 w-8 text-teal-700" />
                    <span className="text-sm font-medium text-slate-900 dark:text-white">
                      {audioFile ? audioFile.name : "Upload audio or use the transcript field below"}
                    </span>
                    <span className="mt-1 text-xs text-muted-foreground">MP3, WAV, M4A, MP4, or WEBM up to 25 MB</span>
                    <input
                      type="file"
                      accept="audio/mpeg,audio/mp4,audio/wav,audio/webm,audio/x-m4a,audio/mp4,video/mp4"
                      className="hidden"
                      onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)}
                    />
                  </label>
                  <Textarea
                    value={audioTranscript}
                    onChange={(event) => setAudioTranscript(event.target.value)}
                    className="min-h-32"
                    placeholder="Optional transcript hint or fallback transcript"
                  />
                  <div className="flex flex-wrap gap-2">
                    {audioSamples.map((sample) => (
                      <Button
                        key={sample.label}
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setAudioTranscript(sample.transcript)}
                      >
                        {sample.label}
                      </Button>
                    ))}
                  </div>
                </div>
              ) : null}

              {mode === "video" ? (
                <div className="space-y-3">
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-slate-50 p-6 text-center dark:bg-slate-950/70">
                    <Film className="mb-2 h-8 w-8 text-teal-700" />
                    <span className="text-sm font-medium text-slate-900 dark:text-white">
                      {videoFile ? videoFile.name : "Upload a short video or describe sampled frames"}
                    </span>
                    <input
                      type="file"
                      accept="video/mp4,video/quicktime,video/webm,video/x-msvideo"
                      className="hidden"
                      onChange={(event) => setVideoFile(event.target.files?.[0] ?? null)}
                    />
                  </label>
                  <Textarea value={videoTranscript} onChange={(event) => setVideoTranscript(event.target.value)} placeholder="Transcript hint" />
                  <input value={videoFrameDescription} onChange={(event) => setVideoFrameDescription(event.target.value)} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring" placeholder="Frame description" />
                  <input value={videoOcr} onChange={(event) => setVideoOcr(event.target.value)} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring" placeholder="OCR text from frame" />
                  <input value={videoObjects} onChange={(event) => setVideoObjects(event.target.value)} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring" placeholder="Detected objects, comma separated" />
                </div>
              ) : null}

              <Button type="button" onClick={submitPlayground} disabled={disabled}>
                {submitting ? "Scanning..." : mode === "social" ? "Scan social comment" : "Run moderation"}
                <Radar className="h-4 w-4" />
              </Button>
              {error ? <p className="text-sm text-red-600 dark:text-red-300">{error}</p> : null}
            </div>

            <div className="rounded-lg border border-dashed border-border bg-background p-5 dark:border-white/10">
              <div className="mb-4">
                <p className="text-base font-semibold text-slate-950 dark:text-white">Result</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Results are persisted to Marketplace, Review cases, and Social inbox when applicable.
                </p>
              </div>
                {visibleResult ? (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={action === "block" ? "danger" : action === "review" ? "secondary" : "success"}
                      >
                        {action}
                      </Badge>
                      {mode === "social" && socialResult ? <Badge variant="outline">{socialResult.status}</Badge> : null}
                    </div>
                    {result ? (
                      <p className="text-sm leading-6 text-slate-700 dark:text-slate-200">{result.decision.explanation}</p>
                    ) : null}
                    {result ? <ConfidenceNotice fallbackModel={result.metadata.fallback_model} /> : null}
                    <div className="grid gap-2">
                      <ApiDocTile label="Request ID" value={result?.request_id ?? socialResult?.moderation_request_id ?? "saved social event"} />
                      <ApiDocTile label="Review case" value={result?.review_case_id ?? "created when the decision needs review"} />
                      {result ? <ApiDocTile label="Model path" value={modelPathLabel(result.metadata.fallback_model)} /> : null}
                    </div>
                    {triggeredCategories.length ? (
                      <div className="flex flex-wrap gap-2">
                        {triggeredCategories.map((category) => (
                          <Badge key={category} variant="outline">{formatCategoryLabel(String(category))}</Badge>
                        ))}
                      </div>
                    ) : null}
                    {result?.category_scores.length ? (
                      <div className="grid gap-2">
                        {[...result.category_scores]
                          .sort((left, right) => right.score - left.score)
                          .slice(0, 4)
                          .map((score) => (
                            <div key={score.category} className="flex items-center justify-between rounded-lg border border-border bg-slate-50 p-2 text-sm dark:bg-slate-950/70">
                              <span>{formatCategoryLabel(String(score.category))}</span>
                              <span className="font-medium">{Math.round(score.score * 100)}%</span>
                            </div>
                          ))}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <EmptyStatePanel
                    icon={Radar}
                    title="No playground result yet"
                    description="Run a scan to see the decision, explanation, category scores, and where the result is saved."
                  />
                )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function modelPathLabel(fallbackModel: string) {
  if (!fallbackModel || fallbackModel === "not_used") {
    return "rules-only";
  }
  if (fallbackModel === "inference-service-unavailable") {
    return "rules-only fallback";
  }
  if (fallbackModel === "heuristic-context-v1") {
    return "rules + heuristic context";
  }
  return `rules + ${fallbackModel}`;
}

function isLowerConfidenceFallback(fallbackModel: string) {
  return fallbackModel === "inference-service-unavailable";
}

function ConfidenceNotice({ fallbackModel }: { fallbackModel: string }) {
  if (!fallbackModel || fallbackModel === "not_used") {
    return null;
  }

  const lowerConfidence = isLowerConfidenceFallback(fallbackModel);
  return (
    <div
      className={cn(
        "rounded-lg border p-3 text-sm",
        lowerConfidence
          ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-400/25 dark:bg-amber-950/35 dark:text-amber-100"
          : "border-teal-200 bg-teal-50 text-teal-800 dark:border-teal-400/25 dark:bg-teal-950/35 dark:text-teal-100",
      )}
    >
      <p className="font-medium">
        {lowerConfidence ? "Lower confidence result" : "Enhanced model path"}
      </p>
      <p className="mt-1">
        {lowerConfidence
          ? "The transformer inference service was unavailable, so this decision used local rules and should be reviewed more carefully."
          : `This decision used ${modelPathLabel(fallbackModel)}.`}
      </p>
    </div>
  );
}

function splitCommaList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function MarketplaceOverview({ dashboard }: { dashboard: DashboardSummary }) {
  return (
    <div className="grid gap-5">
      <UsageCharts dashboard={dashboard} />
      <Card className="dark:border-white/10">
        <CardHeader>
          <CardTitle>Recent marketplace decisions</CardTitle>
          <CardDescription>Latest moderation outcomes for this tenant.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            {dashboard.recent_decisions.length ? (
              dashboard.recent_decisions.slice(0, 8).map((decision) => (
                <div
                  key={decision.request_id}
                  className="rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          decision.action === "block"
                            ? "danger"
                            : decision.action === "review"
                              ? "secondary"
                              : "success"
                        }
                      >
                        {decision.action}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{decision.modality}</span>
                      {decision.fallback_model && decision.fallback_model !== "not_used" ? (
                        <Badge variant={isLowerConfidenceFallback(decision.fallback_model) ? "secondary" : "outline"}>
                          {modelPathLabel(decision.fallback_model)}
                        </Badge>
                      ) : null}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(decision.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 dark:text-slate-200">{decision.content_preview || "No preview"}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{decision.explanation}</p>
                  {isLowerConfidenceFallback(decision.fallback_model) ? (
                    <p className="mt-2 text-xs font-medium text-amber-700 dark:text-amber-200">
                      Lower confidence: transformer inference was unavailable for this decision.
                    </p>
                  ) : null}
                </div>
              ))
            ) : (
              <EmptyStatePanel
                icon={Radar}
                title="No moderation traffic yet"
                description="Send a text or image request from API docs or Integration center. Recent allow, review, and block decisions will appear here."
              />
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function UsageCharts({ dashboard }: { dashboard: DashboardSummary }) {
  const actions = [
    { label: "Allow", value: dashboard.usage.allow, tone: "bg-emerald-500" },
    { label: "Review", value: dashboard.usage.review, tone: "bg-amber-500" },
    { label: "Block", value: dashboard.usage.block, tone: "bg-red-500" },
  ];
  const maxAction = Math.max(...actions.map((action) => action.value), 1);
  const quota = Math.max(dashboard.usage.monthly_quota, 1);
  const usedPercent = Math.min(100, Math.round((dashboard.usage.total_requests / quota) * 100));

  return (
    <Card className="dark:border-white/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LineChart className="h-5 w-5 text-teal-700" />
          Usage charts
        </CardTitle>
        <CardDescription>Credit use and current-month decision mix.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium text-slate-900 dark:text-white">Credits used</span>
              <span className="text-muted-foreground">{usedPercent}%</span>
            </div>
            <div className="h-3 rounded-full bg-slate-100 dark:bg-slate-800">
              <div className="h-3 rounded-full bg-teal-600" style={{ width: `${usedPercent}%` }} />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {dashboard.usage.total_requests} of {dashboard.usage.monthly_quota} credits used.
            </p>
          </div>
          <div className="grid gap-3">
            {actions.map((action) => (
              <div key={action.label} className="grid grid-cols-[72px_1fr_36px] items-center gap-3 text-sm">
                <span className="text-muted-foreground">{action.label}</span>
                <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className={cn("h-2 rounded-full", action.tone)}
                    style={{ width: `${Math.max(4, (action.value / maxAction) * 100)}%` }}
                  />
                </div>
                <span className="text-right font-medium text-slate-900 dark:text-white">{action.value}</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ApiDocsPanel({ apiKeys }: { apiKeys: ApiKeyInfo[] }) {
  const activeKey = apiKeys.find((key) => key.is_active);
  const keyPlaceholder = activeKey ? `${activeKey.key_prefix}...` : "rtcm_your_moderation_key";
  const textCurl = `curl -X POST ${API_BASE}/moderate/text \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${keyPlaceholder}" \\
  -d '{
    "text": "Text to moderate",
    "metadata": {
      "channel": "marketplace_chat",
      "region": "global"
    }
  }'`;
  const imageCurl = `curl -X POST ${API_BASE}/moderate/image \\
  -H "X-API-Key: ${keyPlaceholder}" \\
  -F "image=@./upload.jpg" \\
  -F "channel=marketplace_listing" \\
  -F "region=global"`;
  const audioCurl = `curl -X POST ${API_BASE}/moderate/audio \\
  -H "X-API-Key: ${keyPlaceholder}" \\
  -F "audio=@./voice-note.mp3" \\
  -F "transcript_hint=Optional context or fallback transcript" \\
  -F "channel=voice_message" \\
  -F "region=global"`;
  const javascriptFetch = `const response = await fetch("${API_BASE}/moderate/text", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": process.env.RTCM_MODERATION_KEY,
  },
  body: JSON.stringify({
    text: userMessage,
    metadata: { channel: "marketplace_chat" },
  }),
});

const result = await response.json();`;
  const pythonExample = `import os
import requests

response = requests.post(
    "${API_BASE}/moderate/text",
    headers={"X-API-Key": os.environ["RTCM_MODERATION_KEY"]},
    json={
        "text": user_message,
        "metadata": {"channel": "marketplace_chat"},
    },
    timeout=10,
)
response.raise_for_status()
decision = response.json()["decision"]["action"]`;
  const webhookSignature = `import crypto from "node:crypto";

const body = JSON.stringify(event);
const signature = crypto
  .createHmac("sha256", process.env.RTCM_WEBHOOK_SECRET)
  .update(body)
  .digest("hex");

await fetch("${API_BASE}/connectors/webhook/events", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer DASHBOARD_SESSION_TOKEN",
    "X-RTCM-Signature": \`sha256=\${signature}\`,
  },
  body,
});`;

  return (
    <div className="grid gap-5">
      <Card className="dark:border-white/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-teal-700" />
            API docs
          </CardTitle>
          <CardDescription>Use moderation keys for API requests. Dashboard access is handled by Clerk.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <ApiDocTile label="Base URL" value={API_BASE} />
            <ApiDocTile label="Auth header" value="X-API-Key" />
            <ApiDocTile label="Key to use" value={keyPlaceholder} />
          </div>
          <div className="mt-4 rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
            <p className="text-sm font-medium text-slate-900 dark:text-white">First API call checklist</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-4">
              {["Create moderation key", "Store it server-side", "Send content", "Act on decision"].map((step, index) => (
                <div key={step} className="rounded-md border border-border bg-background p-3 text-sm">
                  <span className="mb-2 flex h-6 w-6 items-center justify-center rounded bg-teal-600 text-xs font-semibold text-white">
                    {index + 1}
                  </span>
                  <span className="font-medium text-slate-900 dark:text-white">{step}</span>
                </div>
              ))}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Successful calls return category scores, a final decision, triggered categories, latency, policy version,
              and a review case ID when the request needs review.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <CodeSnippet title="Text moderation" subtitle="POST /moderate/text" code={textCurl} />
        <CodeSnippet title="Image moderation" subtitle="POST /moderate/image" code={imageCurl} />
        <CodeSnippet title="Audio moderation" subtitle="POST /moderate/audio" code={audioCurl} />
      </div>

      <CodeSnippet title="JavaScript fetch" subtitle="Server-side example" code={javascriptFetch} />
      <CodeSnippet title="Python requests" subtitle="Server-side example" code={pythonExample} />
      <CodeSnippet title="Signed webhook event" subtitle="Optional connector webhook HMAC scaffold" code={webhookSignature} />
      <CustomerCodeExamples />

      <Card className="dark:border-white/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Code2 className="h-5 w-5 text-teal-700" />
            Decision actions
          </CardTitle>
          <CardDescription>Use the action field to decide what your product should do next.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <ApiDocTile label="allow" value="Accept the content." />
            <ApiDocTile label="review" value="Queue for manual review." />
            <ApiDocTile label="block" value="Stop the content." />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function FirstApiCallPanel({ apiKey, workspaceId }: { apiKey: string; workspaceId: string }) {
  const curl = `curl -X POST ${API_BASE}/moderate/text \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${apiKey}" \\
  -d '{
    "text": "Can you review this comment before it goes live?",
    "metadata": {
      "channel": "signup_onboarding",
      "workspace": "${workspaceId}"
    }
  }'`;
  const node = `const response = await fetch("${API_BASE}/moderate/text", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": process.env.RTCM_MODERATION_KEY
  },
  body: JSON.stringify({ text: "Can you review this comment before it goes live?" })
});

const decision = await response.json();
console.log(decision.decision.action);`;
  const python = `import os
import requests

response = requests.post(
    "${API_BASE}/moderate/text",
    headers={"X-API-Key": os.environ["RTCM_MODERATION_KEY"]},
    json={"text": "Can you review this comment before it goes live?"},
    timeout=10,
)
print(response.json()["decision"]["action"])`;

  return (
    <Card className="dark:border-white/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Code2 className="h-5 w-5 text-teal-700" />
          Make your first API call
        </CardTitle>
        <CardDescription>
          Run this from your server or terminal. Keep the key out of frontend code and mobile apps.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-5 xl:grid-cols-3">
          <CodeSnippet title="Terminal smoke test" subtitle="Copy and run once" code={curl} />
          <CodeSnippet title="Node backend" subtitle="Use an environment variable" code={node} />
          <CodeSnippet title="Python backend" subtitle="Server-side request" code={python} />
        </div>
      </CardContent>
    </Card>
  );
}

function LockedPreviewPanel({ title }: { title: string }) {
  return (
    <Card className="min-h-80 border-dashed bg-white/80 dark:border-white/10 dark:bg-white/[0.04]">
      <CardContent className="flex min-h-80 flex-col items-center justify-center text-center">
        <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-200">
          <LockKeyhole className="h-6 w-6" />
        </span>
        <p className="text-lg font-semibold text-slate-950 dark:text-white">{title} is locked in preview</p>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">
          Create an account to unlock API docs, review operations, policy controls, and API key management for your own workspace.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <Show when="signed-out">
            <SignUpButton mode="modal" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard">
              <Button>
                Create account
                <ArrowRight className="h-4 w-4" />
              </Button>
            </SignUpButton>
            <SignInButton mode="modal" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard">
              <Button variant="outline">Sign in</Button>
            </SignInButton>
          </Show>
          <Show when="signed-in">
            <Button asChild>
              <a href="/dashboard">
                Open dashboard
                <LayoutDashboard className="h-4 w-4" />
              </a>
            </Button>
          </Show>
        </div>
      </CardContent>
    </Card>
  );
}

function ApiDocTile({ label, value }: { label: string; value: string }) {
  const shouldBreakAnywhere = /[_:/\\]/.test(value) || value.length > 44;
  return (
    <div className="rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70">
      <p className="text-xs font-medium uppercase text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-sm font-medium text-slate-900 dark:text-white", shouldBreakAnywhere ? "break-all" : "break-words")}>
        {value}
      </p>
    </div>
  );
}

function CodeSnippet({ title, subtitle, code }: { title: string; subtitle: string; code: string }) {
  const [copied, setCopied] = useState(false);

  async function copyCode() {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(code);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Card className="dark:border-white/10">
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            <Code2 className="h-5 w-5 text-teal-700" />
            {title}
          </CardTitle>
          <CardDescription>{subtitle}</CardDescription>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={copyCode}>
          <Copy className="h-4 w-4" />
          {copied ? "Copied" : "Copy"}
        </Button>
      </CardHeader>
      <CardContent>
        <pre className="overflow-x-auto rounded-lg border border-border bg-slate-950 p-4 text-xs leading-5 text-slate-100">
          <code>{code}</code>
        </pre>
      </CardContent>
    </Card>
  );
}

function formatCategoryLabel(category: string) {
  return category.replace(/_/g, " ");
}

function formatCaseDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function SocialInboxPanel({
  connectedAccounts,
  socialEvents,
  loading,
  onConnectSocialAccount,
  onStartMetaOAuth,
  onDisconnectSocialAccount,
  onDeleteSocialAccount,
  onCreateSocialEvent,
  onApplySocialAction,
}: {
  connectedAccounts: ConnectedAccount[];
  socialEvents: SocialEvent[];
  loading: boolean;
  onConnectSocialAccount: (account: {
    platform: string;
    provider_account_id: string;
    display_name: string;
    account_type: string;
    scopes: string[];
  }) => void;
  onStartMetaOAuth: () => void;
  onDisconnectSocialAccount: (accountId: string) => void;
  onDeleteSocialAccount: (accountId: string) => void;
  onCreateSocialEvent: (event: SocialEventCreateInput) => void;
  onApplySocialAction: (eventId: string, actionType: SocialActionType) => void;
}) {
  const [platform, setPlatform] = useState("instagram");
  const [providerAccountId, setProviderAccountId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [accountType, setAccountType] = useState("creator");
  const [scopeText, setScopeText] = useState("comments");
  const [eventPlatform, setEventPlatform] = useState("instagram");
  const [eventAccountId, setEventAccountId] = useState("");
  const [eventSourceType, setEventSourceType] = useState("comment");
  const [eventActor, setEventActor] = useState("");
  const [eventExternalId, setEventExternalId] = useState("");
  const [eventText, setEventText] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | SocialEvent["status"]>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const accountById = useMemo(
    () => new Map(connectedAccounts.map((account) => [account.id, account])),
    [connectedAccounts],
  );
  const visibleConnectedAccounts = connectedAccounts.filter((account) => account.status !== "deleted");
  const activeConnectedAccounts = visibleConnectedAccounts.filter((account) => account.status !== "disconnected");
  const socialStats = [
    { label: "Open", value: socialEvents.filter((event) => event.status === "open").length },
    { label: "Review", value: socialEvents.filter((event) => event.decision_action === "review").length },
    { label: "Blocked", value: socialEvents.filter((event) => event.decision_action === "block").length },
    { label: "Accounts", value: activeConnectedAccounts.length },
  ];
  const filteredEvents = socialEvents.filter((event) => {
    const matchesStatus = statusFilter === "all" || event.status === statusFilter;
    const query = searchQuery.trim().toLowerCase();
    const account = event.connected_account_id ? accountById.get(event.connected_account_id) : null;
    const matchesSearch =
      !query ||
      event.content_text.toLowerCase().includes(query) ||
      event.platform.toLowerCase().includes(query) ||
      event.source_type.toLowerCase().includes(query) ||
      (event.actor_handle || "").toLowerCase().includes(query) ||
      (account?.display_name || "").toLowerCase().includes(query);
    return matchesStatus && matchesSearch;
  });

  const submitConnectedAccount = () => {
    if (!providerAccountId.trim() || !displayName.trim()) {
      return;
    }
    onConnectSocialAccount({
      platform,
      provider_account_id: providerAccountId.trim(),
      display_name: displayName.trim(),
      account_type: accountType.trim() || "business",
      scopes: scopeText
        .split(",")
        .map((scope) => scope.trim())
        .filter(Boolean),
    });
    setProviderAccountId("");
    setDisplayName("");
  };

  const submitSocialEvent = () => {
    if (!eventText.trim()) {
      return;
    }
    const selectedAccount = eventAccountId ? accountById.get(eventAccountId) : null;
    onCreateSocialEvent({
      connected_account_id: eventAccountId || undefined,
      platform: selectedAccount?.platform || eventPlatform,
      external_event_id: eventExternalId.trim() || undefined,
      source_type: eventSourceType,
      actor_handle: eventActor.trim() || undefined,
      content_text: eventText.trim(),
    });
    setEventText("");
    setEventActor("");
    setEventExternalId("");
  };

  const statusBadgeVariant = (status: SocialEvent["status"]): "secondary" | "success" | "danger" | "outline" => {
    if (status === "open" || status === "in_review") {
      return "secondary";
    }
    if (status === "allowed" || status === "reviewed") {
      return "success";
    }
    if (status === "deleted" || status === "blocked_user") {
      return "danger";
    }
    return "outline";
  };

  const accountStatusVariant = (status: string): "secondary" | "success" | "danger" | "outline" => {
    if (status === "connected") {
      return "success";
    }
    if (status === "pending_auth") {
      return "secondary";
    }
    if (status === "disconnected") {
      return "danger";
    }
    return "outline";
  };

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {socialStats.map((stat) => (
          <div key={stat.label} className="rounded-lg border border-border bg-background p-3">
            <p className="text-xs font-medium uppercase text-muted-foreground">{stat.label}</p>
            <p className="mt-1 text-2xl font-semibold">{stat.value}</p>
          </div>
        ))}
      </div>

      <Card className="dark:border-white/10">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Workflow className="h-5 w-5 text-teal-700" />
                Connected accounts
              </CardTitle>
              <CardDescription>
                Manual IDs are saved as pending auth. Meta OAuth verifies Facebook Pages and Instagram professional accounts.
              </CardDescription>
            </div>
            <Button type="button" onClick={onStartMetaOAuth} disabled={loading}>
              Connect Meta
              <LogIn className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 lg:grid-cols-3 xl:grid-cols-[1fr_1fr_1fr_1fr_1fr_auto]">
            <select
              value={platform}
              onChange={(event) => setPlatform(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="email">Email</option>
              <option value="webhook">Website/API webhook</option>
            </select>
            <select
              value={accountType}
              onChange={(event) => setAccountType(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="creator">Creator</option>
              <option value="business">Business</option>
              <option value="page">Page</option>
              <option value="inbox">Inbox</option>
            </select>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Display name"
            />
            <input
              value={providerAccountId}
              onChange={(event) => setProviderAccountId(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Provider account ID"
            />
            <input
              value={scopeText}
              onChange={(event) => setScopeText(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Scopes"
            />
            <Button
              type="button"
              onClick={submitConnectedAccount}
              disabled={loading || !providerAccountId.trim() || !displayName.trim()}
            >
              Save ID
              <BadgeCheck className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-3 grid gap-2">
            {visibleConnectedAccounts.length ? (
              visibleConnectedAccounts.map((account) => (
                <div
                  key={account.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-background p-2"
                >
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <Badge variant={accountStatusVariant(account.status)}>{account.status.replace("_", " ")}</Badge>
                    <span className="text-sm font-medium text-slate-900 dark:text-white">
                      {account.display_name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {account.platform} | {account.account_type} | {account.provider_account_id}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => onDisconnectSocialAccount(account.id)}
                      disabled={loading || account.status === "disconnected"}
                    >
                      Disconnect
                      <XCircle className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => onDeleteSocialAccount(account.id)}
                      disabled={loading}
                      className="border-red-200 text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950"
                    >
                      Delete
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <EmptyStatePanel
                icon={Workflow}
                title="No accounts connected"
                description="Connect Meta when OAuth is configured, or save a provider account ID to test inbox workflows before launch."
              />
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="dark:border-white/10">
        <CardHeader>
          <CardTitle>Scan social event</CardTitle>
          <CardDescription>Create an inbox item from a comment, DM, email, form message, or webhook payload.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="grid gap-3 lg:grid-cols-4">
            <select
              value={eventAccountId}
              onChange={(changeEvent) => {
                const accountId = changeEvent.target.value;
                setEventAccountId(accountId);
                const selectedAccount = accountById.get(accountId);
                if (selectedAccount) {
                  setEventPlatform(selectedAccount.platform);
                }
              }}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">No account</option>
              {activeConnectedAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.display_name} ({account.platform})
                </option>
              ))}
            </select>
            <select
              value={eventPlatform}
              onChange={(event) => setEventPlatform(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
              disabled={Boolean(eventAccountId)}
            >
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="email">Email</option>
              <option value="webhook">Website/API webhook</option>
            </select>
            <select
              value={eventSourceType}
              onChange={(event) => setEventSourceType(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="comment">Comment</option>
              <option value="dm">DM</option>
              <option value="email">Email</option>
              <option value="form">Form</option>
              <option value="webhook">Webhook</option>
            </select>
            <input
              value={eventActor}
              onChange={(event) => setEventActor(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Actor handle"
            />
          </div>
          <Textarea
            value={eventText}
            onChange={(event) => setEventText(event.target.value)}
            className="min-h-28"
            placeholder="Paste the comment, DM, email text, or webhook message"
          />
          <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
            <input
              value={eventExternalId}
              onChange={(event) => setEventExternalId(event.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="External event ID"
            />
            <Button type="button" onClick={submitSocialEvent} disabled={loading || !eventText.trim()}>
              Scan event
              <Radar className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="dark:border-white/10">
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Inbox events</CardTitle>
            <CardDescription>
              Showing {filteredEvents.length} of {socialEvents.length} social moderation events.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_auto]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                placeholder="Search social text, platform, or actor"
              />
            </label>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as "all" | SocialEvent["status"])}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="all">All statuses</option>
              <option value="open">Open</option>
              <option value="allowed">Allowed</option>
              <option value="hidden">Hidden</option>
              <option value="deleted">Deleted</option>
              <option value="blocked_user">Blocked user</option>
              <option value="reviewed">Reviewed</option>
            </select>
          </div>
          <div className="grid gap-3">
            {filteredEvents.length ? (
              filteredEvents.map((event) => {
                const account = event.connected_account_id ? accountById.get(event.connected_account_id) : null;
                return (
                <div key={event.id} className="rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{event.platform}</Badge>
                      {account ? <Badge variant="outline">{account.display_name}</Badge> : null}
                      <Badge variant="secondary">{event.source_type}</Badge>
                      <Badge
                        variant={
                          event.decision_action === "block"
                            ? "danger"
                            : event.decision_action === "review"
                              ? "secondary"
                              : "success"
                        }
                      >
                        {event.decision_action}
                      </Badge>
                    </div>
                    <Badge variant={statusBadgeVariant(event.status)}>
                      {event.status.replace("_", " ")}
                    </Badge>
                  </div>
                  <p className="text-sm text-slate-700 dark:text-slate-200">{event.content_text}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>{event.actor_handle || "Unknown actor"}</span>
                    <span>{formatCaseDate(event.created_at)}</span>
                    <span>{event.external_event_id || event.id.slice(0, 8)}</span>
                    {event.triggered_categories.length ? <span>{event.triggered_categories.join(", ")}</span> : null}
                    {event.last_action_at ? <span>Last action {formatCaseDate(event.last_action_at)}</span> : null}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onApplySocialAction(event.id, "hide")}
                      disabled={loading || event.status === "hidden"}
                    >
                      Hide
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onApplySocialAction(event.id, "delete")}
                      disabled={loading || event.status === "deleted"}
                    >
                      Delete
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onApplySocialAction(event.id, "allow")}
                      disabled={loading || event.status === "allowed"}
                    >
                      Allow
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onApplySocialAction(event.id, "block-user")}
                      disabled={loading || event.status === "blocked_user"}
                    >
                      Block user
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onApplySocialAction(event.id, "mark-reviewed")}
                      disabled={loading || event.status === "reviewed"}
                    >
                      Mark reviewed
                    </Button>
                  </div>
                </div>
                );
              })
            ) : (
              <EmptyStatePanel
                icon={Search}
                title="No social events match this view"
                description="Scan a comment, DM, email, form message, or webhook event. Matching inbox items will appear with action controls."
              />
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ReviewCasesPanel({
  reviewCases,
  caseNotes,
  loading,
  setCaseNotes,
  onUpdateReviewCase,
}: {
  reviewCases: ReviewCase[];
  caseNotes: Record<string, string>;
  loading: boolean;
  setCaseNotes: Dispatch<SetStateAction<Record<string, string>>>;
  onUpdateReviewCase: (caseId: string, status: ReviewCase["status"]) => void;
}) {
  const [showPreviousCases, setShowPreviousCases] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"all" | ReviewCase["status"]>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const filteredCases = reviewCases.filter((reviewCase) => {
    const matchesStatus = statusFilter === "all" || reviewCase.status === statusFilter;
    const query = searchQuery.trim().toLowerCase();
    const matchesSearch =
      !query ||
      reviewCase.submitted_text.toLowerCase().includes(query) ||
      (reviewCase.assignee || "").toLowerCase().includes(query) ||
      reviewCase.action.toLowerCase().includes(query);
    return matchesStatus && matchesSearch;
  });
  const visibleCases = showPreviousCases ? filteredCases : filteredCases.slice(0, 10);

  return (
    <Card className="dark:border-white/10">
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Radar className="h-5 w-5 text-teal-700" />
            Review cases
          </CardTitle>
          <CardDescription>
            Showing {visibleCases.length} of {filteredCases.length} matching cases.
          </CardDescription>
        </div>
        {filteredCases.length > 10 ? (
          <Button variant="outline" size="sm" onClick={() => setShowPreviousCases((current) => !current)}>
            {showPreviousCases ? "Recent cases" : "Previous cases"}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent>
        <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_auto]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Search text, action, or assignee"
            />
          </label>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as "all" | ReviewCase["status"])}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="in_review">In review</option>
            <option value="resolved">Resolved</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>
        <div className="grid gap-3">
          {visibleCases.length ? (
            visibleCases.map((reviewCase) => {
              const topScore = [...reviewCase.category_scores].sort((left, right) => right.score - left.score)[0];
              return (
                <div
                  key={reviewCase.case_id}
                  className="rounded-lg border border-border bg-slate-50 p-3 dark:bg-slate-950/70"
                >
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        reviewCase.status === "resolved"
                          ? "success"
                          : reviewCase.status === "dismissed"
                            ? "outline"
                            : "secondary"
                      }
                    >
                      {reviewCase.status.replace("_", " ")}
                    </Badge>
                    <span className="text-xs text-muted-foreground">priority {reviewCase.priority}</span>
                  </div>
                  <Badge variant={reviewCase.action === "block" ? "danger" : "secondary"}>{reviewCase.action}</Badge>
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-200">{reviewCase.submitted_text || "No preview"}</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <UserRound className="h-3.5 w-3.5" />
                    {reviewCase.assignee || "Unassigned"}
                  </span>
                  <span>{formatCaseDate(reviewCase.created_at)}</span>
                  <span>{reviewCase.request_id.slice(0, 8)}</span>
                  {topScore ? (
                    <span>
                      {formatCategoryLabel(topScore.category)} {Math.round(topScore.score * 100)}%
                    </span>
                  ) : null}
                </div>
                {reviewCase.notes.length ? (
                  <p className="mt-1 text-xs text-muted-foreground">{reviewCase.notes[reviewCase.notes.length - 1]}</p>
                ) : null}
                <div className="mt-3 grid gap-2 lg:grid-cols-[1fr_180px_auto_auto_auto]">
                  <input
                    value={caseNotes[reviewCase.case_id] ?? ""}
                    onChange={(event) =>
                      setCaseNotes((current) => ({
                        ...current,
                        [reviewCase.case_id]: event.target.value,
                      }))
                    }
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Optional reviewer note"
                  />
                  <input
                    value={caseNotes[`${reviewCase.case_id}:assignee`] ?? reviewCase.assignee ?? ""}
                    onChange={(event) =>
                      setCaseNotes((current) => ({
                        ...current,
                        [`${reviewCase.case_id}:assignee`]: event.target.value,
                      }))
                    }
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Assignee"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onUpdateReviewCase(reviewCase.case_id, "in_review")}
                    disabled={loading || reviewCase.status === "in_review"}
                  >
                    Start
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onUpdateReviewCase(reviewCase.case_id, "resolved")}
                    disabled={loading || reviewCase.status === "resolved"}
                  >
                    Resolve
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onUpdateReviewCase(reviewCase.case_id, "dismissed")}
                    disabled={loading || reviewCase.status === "dismissed"}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
              );
            })
          ) : (
            <EmptyStatePanel
              icon={Radar}
              title="No review cases match this view"
              description="Review cases are created when moderation returns a review decision. Use the Integration center smoke test or lower thresholds to test this workflow."
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function PolicyThresholdsPanel({
  policy,
  thresholdRows,
  loading,
  onThresholdChange,
  onPolicyFlagChange,
  onSave,
}: {
  policy: DashboardSummary["policy"];
  thresholdRows: Array<[string, PolicyThreshold]>;
  loading: boolean;
  onThresholdChange: (category: string, key: keyof PolicyThreshold, value: number) => void;
  onPolicyFlagChange: (key: "review_enabled" | "protected_mode", value: boolean) => void;
  onSave: () => void;
}) {
  return (
    <Card className="dark:border-white/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <SlidersHorizontal className="h-5 w-5 text-teal-700" />
          Policy thresholds
        </CardTitle>
        <CardDescription>Lower thresholds create more reviews or blocks. Review cannot exceed block.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-5 grid gap-3 md:grid-cols-2">
          <label className="flex items-start justify-between gap-4 rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
            <span>
              <span className="block text-sm font-medium text-slate-900 dark:text-white">Manual review</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                Queue content that crosses review thresholds instead of allowing it through.
              </span>
            </span>
            <input
              type="checkbox"
              checked={policy.review_enabled}
              onChange={(event) => onPolicyFlagChange("review_enabled", event.target.checked)}
              className="mt-1 h-5 w-5 accent-teal-700"
            />
          </label>
          <label className="flex items-start justify-between gap-4 rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
            <span>
              <span className="block text-sm font-medium text-slate-900 dark:text-white">Protected mode</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                Apply stricter review and block thresholds for safety-sensitive workspaces.
              </span>
            </span>
            <input
              type="checkbox"
              checked={policy.protected_mode}
              onChange={(event) => onPolicyFlagChange("protected_mode", event.target.checked)}
              className="mt-1 h-5 w-5 accent-teal-700"
            />
          </label>
        </div>
        <div className="space-y-5">
          {thresholdRows.map(([category, threshold]) => (
            <div key={category} className="rounded-lg border border-border p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-sm font-medium capitalize text-slate-900 dark:text-white">
                  {formatCategoryLabel(category)}
                </p>
                <p className="text-xs text-muted-foreground">
                  review {Math.round((threshold.review ?? 0) * 100)}% | block{" "}
                  {Math.round((threshold.block ?? 0) * 100)}%
                </p>
              </div>
              <SliderRow
                label="Review"
                value={threshold.review ?? 0.05}
                onChange={(value) => onThresholdChange(category, "review", value)}
              />
              <SliderRow
                label="Block"
                value={threshold.block ?? 0.05}
                onChange={(value) => onThresholdChange(category, "block", value)}
              />
            </div>
          ))}
        </div>
        <Button className="mt-5" onClick={onSave} disabled={loading || !thresholdRows.length}>
          Save policy
          <SlidersHorizontal className="h-4 w-4" />
        </Button>
      </CardContent>
    </Card>
  );
}

function BillingPanel({
  billingStatus,
  usage,
  loading,
  onStartCheckout,
  onOpenPortal,
  onUpdateBillingScope,
}: {
  billingStatus: BillingStatus | null;
  usage: DashboardSummary["usage"];
  loading: boolean;
  onStartCheckout: (planName: string) => void;
  onOpenPortal: () => void;
  onUpdateBillingScope: (billingScope: "account" | "workspace") => void;
}) {
  const currentPlan = billingStatus?.plan_name ?? usage.plan_name;
  const activeQuota = billingStatus?.monthly_quota ?? usage.monthly_quota;
  const billingScope = billingStatus?.billing_scope ?? usage.billing_scope;
  const usedPercent = Math.min(100, Math.round((usage.total_requests / Math.max(activeQuota, 1)) * 100));

  return (
    <Card className="dark:border-white/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CreditCard className="h-5 w-5 text-teal-700" />
          Billing
        </CardTitle>
        <CardDescription>Manage moderation credits, billing scope, and checkout when billing is configured.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-5 rounded-lg border border-border bg-background p-4 dark:bg-slate-950/70">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-slate-900 dark:text-white">Billing scope</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {billingScope === "workspace"
                  ? "This workspace has its own plan, credits, and billing."
                  : "Unlimited workspaces can share this account credit pool until a workspace buys a separate plan."}
              </p>
            </div>
            <Badge variant={billingScope === "workspace" ? "secondary" : "success"}>
              {billingScope === "workspace" ? "workspace billing" : "account billing"}
            </Badge>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Button
              type="button"
              variant={billingScope === "account" ? "default" : "outline"}
              disabled={loading || billingScope === "account"}
              onClick={() => onUpdateBillingScope("account")}
            >
              Shared account billing
            </Button>
            <Button
              type="button"
              variant={billingScope === "workspace" ? "default" : "outline"}
              disabled={loading || billingScope === "workspace"}
              onClick={() => onUpdateBillingScope("workspace")}
            >
              Separate workspace billing
            </Button>
          </div>
        </div>

        <div className="mb-5 rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-slate-900 dark:text-white">Current subscription</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {currentPlan} plan | {billingStatus?.subscription_status ?? "unknown"} | {activeQuota.toLocaleString()} credits/month
              </p>
            </div>
            <Badge variant={usage.remaining_requests <= Math.ceil(activeQuota * 0.15) ? "secondary" : "success"}>
              {usage.remaining_requests.toLocaleString()} left
            </Badge>
          </div>
          <div className="mt-4 h-2 rounded-full bg-slate-200 dark:bg-slate-800">
            <div className="h-2 rounded-full bg-teal-600" style={{ width: `${usedPercent}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {usage.total_requests.toLocaleString()} credits used this month.{" "}
            {billingScope === "workspace" ? "This count is for this workspace." : "This count is shared across account-billed workspaces."}
          </p>
          {usage.remaining_requests <= 0 ? (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-400/25 dark:bg-red-950/35 dark:text-red-100">
              This workspace has used its monthly credit quota. Upgrade below or manage billing before sending more production traffic.
            </div>
          ) : usage.remaining_requests <= Math.ceil(activeQuota * 0.15) ? (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-400/25 dark:bg-amber-950/35 dark:text-amber-100">
              Credits are running low. Upgrade before production traffic is blocked.
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onOpenPortal}
              disabled={loading || !billingStatus?.stripe_customer_id}
              title={!billingStatus?.stripe_customer_id ? "Choose a Stripe plan before opening the customer portal." : "Manage payment method or cancel subscription"}
            >
              Manage payment
              <ExternalLink className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          {billingPlans.map((plan) => (
            <div
              key={plan.name}
              className={cn(
                "relative rounded-lg border bg-background p-5 shadow-sm dark:bg-slate-950/70",
                currentPlan.toLowerCase() === plan.name ? "border-teal-500 ring-1 ring-teal-500/30" : "border-border",
              )}
            >
              {plan.badge ? (
                <Badge className="absolute right-4 top-4" variant="secondary">
                  {plan.badge}
                </Badge>
              ) : null}
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="font-medium capitalize text-slate-900 dark:text-white">{plan.name}</p>
                {currentPlan.toLowerCase() === plan.name ? <Badge variant="success">current</Badge> : null}
              </div>
              {"trial" in plan ? (
                <Badge variant="secondary" className="mb-3">
                  {plan.trial}
                </Badge>
              ) : null}
              <div className="flex items-end gap-1">
                <p className="text-3xl font-semibold text-slate-950 dark:text-white">{plan.price}</p>
                <p className="pb-1 text-sm text-muted-foreground">/{plan.cadence}</p>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{plan.audience}</p>
              <div className="mt-4 rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
                <p className="text-sm font-medium text-slate-900 dark:text-white">{plan.quota.toLocaleString()} credits/month</p>
                <p className="mt-1 text-xs text-muted-foreground">{plan.overage}</p>
              </div>
              <div className="mt-4 grid gap-2">
                {plan.features.map((feature) => (
                  <div key={feature} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" />
                    <span>{feature}</span>
                  </div>
                ))}
              </div>
              <Button
                className="mt-5 w-full"
                variant={currentPlan.toLowerCase() === plan.name ? "outline" : "default"}
                disabled={loading || currentPlan.toLowerCase() === plan.name}
                onClick={() => onStartCheckout(plan.name)}
              >
                {currentPlan.toLowerCase() === plan.name ? "Current plan" : `Choose ${plan.name}`}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ApiKeysPanel({
  apiKeys,
  apiKeyUsage,
  newKeyName,
  createdApiKey,
  loading,
  setNewKeyName,
  onCreateModerationKey,
  onDeactivateApiKey,
  onRotateApiKey,
}: {
  apiKeys: ApiKeyInfo[];
  apiKeyUsage: ApiKeyUsage[];
  newKeyName: string;
  createdApiKey: string;
  loading: boolean;
  setNewKeyName: (value: string) => void;
  onCreateModerationKey: () => void;
  onDeactivateApiKey: (apiKeyId: string) => void;
  onRotateApiKey: (apiKeyId: string) => void;
}) {
  const usageByKey = new Map(apiKeyUsage.map((key) => [key.id, key.total_requests]));

  return (
    <Card className="dark:border-white/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LockKeyhole className="h-5 w-5 text-teal-700" />
          API keys
        </CardTitle>
        <CardDescription>Create moderation-only keys for production apps and webhooks.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <input
            value={newKeyName}
            onChange={(event) => setNewKeyName(event.target.value)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
            placeholder="Key name"
          />
          <Button onClick={onCreateModerationKey} disabled={loading || newKeyName.trim().length < 2}>
            Create moderation key
            <LockKeyhole className="h-4 w-4" />
          </Button>
        </div>
        {createdApiKey ? (
          <OneTimeKeyBox title="New key" apiKey={createdApiKey} className="mt-4" />
        ) : null}
        <div className="mt-4 grid gap-2">
          {apiKeys.map((key) => (
            <div
              key={key.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-slate-50 p-3 text-sm dark:bg-slate-950/70"
            >
              <div>
                <p className="font-medium text-slate-900 dark:text-white">{key.name}</p>
                <p className="text-xs text-muted-foreground">
                  {key.key_prefix}... | {key.scopes.join(", ")} | {usageByKey.get(key.id) ?? 0} requests
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={key.is_active ? "success" : "outline"}>{key.is_active ? "active" : "inactive"}</Badge>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onRotateApiKey(key.id)}
                  disabled={loading || !key.is_active}
                >
                  Rotate
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onDeactivateApiKey(key.id)}
                  disabled={loading || !key.is_active}
                >
                  Deactivate
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function OneTimeKeyBox({ title, apiKey, className }: { title: string; apiKey: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  async function copyKey() {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(apiKey);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-400/25 dark:bg-amber-950/45 dark:text-amber-100",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">{title}, shown once</p>
          <p className="mt-1 text-xs">Copy this key now. After you leave or reload this screen, only its prefix/status will remain.</p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={copyKey}>
          <Copy className="h-4 w-4" />
          {copied ? "Copied" : "Copy key"}
        </Button>
      </div>
      <code className="mt-3 block break-all rounded bg-white/70 p-2 text-xs dark:bg-slate-950">
        {apiKey}
      </code>
    </div>
  );
}

function UsageTile({
  label,
  value,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: number;
  icon: typeof BarChart3;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  const toneClass = {
    neutral: "text-teal-700 bg-teal-50 dark:bg-teal-950 dark:text-teal-200",
    success: "text-emerald-700 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-200",
    warning: "text-amber-700 bg-amber-50 dark:bg-amber-950 dark:text-amber-200",
    danger: "text-red-700 bg-red-50 dark:bg-red-950 dark:text-red-200",
  }[tone];

  return (
    <Card className="min-w-0 dark:border-white/10">
      <CardContent className="p-4">
        <span className={cn("mb-3 flex h-9 w-9 items-center justify-center rounded-md", toneClass)}>
          <Icon className="h-4 w-4" />
        </span>
        <p className="text-2xl font-semibold text-slate-950 dark:text-white">{value}</p>
        <p className="break-words text-xs text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

function SliderRow({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="mt-3 grid gap-2 sm:grid-cols-[72px_1fr_48px] sm:items-center">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <input
        type="range"
        min="0.05"
        max="1"
        step="0.01"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 w-full cursor-pointer accent-teal-700"
      />
      <span className="text-right text-xs text-muted-foreground">{Math.round(value * 100)}%</span>
    </label>
  );
}

type ModerationConsoleProps = {
  text: string;
  setText: (value: string) => void;
  textLanguage: string;
  setTextLanguage: (value: string) => void;
  result: ModerationResult | null;
  topScores: ModerationResult["category_scores"];
  demoMode: DemoMode;
  setDemoMode: (mode: DemoMode) => void;
  textLoading: boolean;
  imageLoading: boolean;
  audioLoading: boolean;
  videoLoading: boolean;
  error: string;
  imageFile: File | null;
  imagePreview: string;
  setImageFile: (file: File | null) => void;
  audioFile: File | null;
  setAudioFile: (file: File | null) => void;
  audioTranscript: string;
  setAudioTranscript: (value: string) => void;
  videoTranscript: string;
  setVideoTranscript: (value: string) => void;
  videoFrameDescription: string;
  setVideoFrameDescription: (value: string) => void;
  videoOcrText: string;
  setVideoOcrText: (value: string) => void;
  videoObjects: string;
  setVideoObjects: (value: string) => void;
  videoFile: File | null;
  setVideoFile: (file: File | null) => void;
  onVideoFileChange: (file: File | null) => void;
  onRun: () => void;
  onSample: (sample: TextSample) => void;
  onImageRun: () => void;
  onAudioRun: () => void;
  onVideoRun: () => void;
};

function ModerationConsole({
  text,
  setText,
  textLanguage,
  setTextLanguage,
  result,
  topScores,
  demoMode,
  setDemoMode,
  textLoading,
  imageLoading,
  audioLoading,
  videoLoading,
  error,
  imageFile,
  imagePreview,
  setImageFile,
  audioFile,
  setAudioFile,
  audioTranscript,
  setAudioTranscript,
  videoTranscript,
  setVideoTranscript,
  videoFrameDescription,
  setVideoFrameDescription,
  videoOcrText,
  setVideoOcrText,
  videoObjects,
  setVideoObjects,
  videoFile,
  setVideoFile,
  onVideoFileChange,
  onRun,
  onSample,
  onImageRun,
  onAudioRun,
  onVideoRun,
}: ModerationConsoleProps) {
  const action = result?.decision.action ?? "allow";
  const actionClass =
    action === "block"
      ? "border-red-200 bg-red-50 text-red-700"
      : action === "review"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-emerald-200 bg-emerald-50 text-emerald-700";

  return (
    <Card className="border-white/70 bg-white shadow-glow backdrop-blur dark:border-slate-700 dark:bg-slate-900">
      <CardHeader className="border-b border-border dark:border-slate-700">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-slate-950 dark:text-white">
              <Activity className="h-5 w-5 text-teal-700 dark:text-teal-300" />
              Live moderation console
            </CardTitle>
            <CardDescription className="text-slate-600 dark:text-slate-300">
              Test text and real image upload moderation against the running backend.
            </CardDescription>
          </div>
          <Badge className={cn("shrink-0", actionClass)}>{result ? action : "ready"}</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-5">
        <div className="mb-5 grid grid-cols-2 rounded-lg border border-border bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-950 md:grid-cols-4">
          <button
            type="button"
            onClick={() => setDemoMode("text")}
            className={cn(
              "flex h-10 items-center justify-center gap-2 rounded-md text-sm font-medium transition",
              demoMode === "text"
                ? "bg-white text-slate-950 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-600 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white",
            )}
          >
            <Gauge className="h-4 w-4" />
            Text
          </button>
          <button
            type="button"
            onClick={() => setDemoMode("image")}
            className={cn(
              "flex h-10 items-center justify-center gap-2 rounded-md text-sm font-medium transition",
              demoMode === "image"
                ? "bg-white text-slate-950 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-600 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white",
            )}
          >
            <ImageIcon className="h-4 w-4" />
            Image
          </button>
          <button
            type="button"
            onClick={() => setDemoMode("audio")}
            className={cn(
              "flex h-10 items-center justify-center gap-2 rounded-md text-sm font-medium transition",
              demoMode === "audio"
                ? "bg-white text-slate-950 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-600 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white",
            )}
          >
            <FileAudio className="h-4 w-4" />
            Audio
          </button>
          <button
            type="button"
            onClick={() => setDemoMode("video")}
            className={cn(
              "flex h-10 items-center justify-center gap-2 rounded-md text-sm font-medium transition",
              demoMode === "video"
                ? "bg-white text-slate-950 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-600 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white",
            )}
          >
            <Film className="h-4 w-4" />
            Video
          </button>
        </div>

        {demoMode === "text" ? (
          <div className="grid gap-4">
            <Textarea value={text} onChange={(event) => setText(event.target.value)} />
            <div className="flex flex-wrap gap-2">
              {sampleTexts.map((sample) => (
                <Button key={sample.label} type="button" variant="outline" size="sm" onClick={() => onSample(sample)}>
                  {sample.label}
                </Button>
              ))}
            </div>
            <Button onClick={onRun} disabled={textLoading || !text.trim()}>
              {textLoading ? "Scanning text..." : "Scan text"}
              <Gauge className="h-4 w-4" />
            </Button>
          </div>
        ) : demoMode === "image" ? (
          <div className="rounded-lg border border-border bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 text-sm font-medium text-slate-950 dark:text-white">
                  <ImageIcon className="h-4 w-4 text-teal-700 dark:text-teal-300" />
                  Real image scanning
                </p>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                  Upload an image for Vision labels, OCR, and SafeSearch scoring.
                </p>
              </div>
              <Badge variant="outline">kids-safe</Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <label className="flex min-h-24 cursor-pointer items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600 transition hover:border-teal-500 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-teal-300">
                {imagePreview ? (
                  <img src={imagePreview} alt="" className="h-16 w-16 rounded-md object-cover" />
                ) : (
                  <span className="flex h-12 w-12 items-center justify-center rounded-md bg-teal-50 text-teal-700 dark:bg-teal-900 dark:text-teal-100">
                    <UploadCloud className="h-5 w-5" />
                  </span>
                )}
                <span className="min-w-0">
                  <span className="block truncate font-medium text-slate-800 dark:text-slate-100">
                    {imageFile ? imageFile.name : "Choose an image"}
                  </span>
                  <span className="mt-1 block text-xs text-slate-500 dark:text-slate-300">PNG, JPG, or WEBP up to 6 MB</span>
                </span>
                <input
                  className="sr-only"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(event) => setImageFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <Button onClick={onImageRun} disabled={imageLoading || !imageFile} className="sm:self-stretch">
                {imageLoading ? "Scanning image..." : "Scan image"}
                <Radar className="h-4 w-4" />
              </Button>
            </div>
          </div>
        ) : demoMode === "audio" ? (
          <div className="rounded-lg border border-border bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 text-sm font-medium text-slate-950 dark:text-white">
                  <FileAudio className="h-4 w-4 text-teal-700 dark:text-teal-300" />
                  Real audio scanning
                </p>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                  Upload a voice note or paste a transcript. Transcription runs when configured on the backend.
                </p>
              </div>
              <Badge variant="outline">/moderate/audio</Badge>
            </div>
            <label className="mb-3 flex min-h-20 cursor-pointer items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600 transition hover:border-teal-500 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-teal-300">
              <span className="flex h-12 w-12 items-center justify-center rounded-md bg-teal-50 text-teal-700 dark:bg-teal-900 dark:text-teal-100">
                <UploadCloud className="h-5 w-5" />
              </span>
              <span className="min-w-0">
                <span className="block truncate font-medium text-slate-800 dark:text-slate-100">
                  {audioFile ? audioFile.name : "Choose an audio file"}
                </span>
                <span className="mt-1 block text-xs text-slate-500 dark:text-slate-300">MP3, WAV, M4A, MP4, or WEBM up to 25 MB</span>
              </span>
              <input
                className="sr-only"
                type="file"
                accept="audio/mpeg,audio/mp4,audio/wav,audio/webm,audio/x-m4a,audio/mp4,video/mp4"
                onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <Textarea
              value={audioTranscript}
              onChange={(event) => setAudioTranscript(event.target.value)}
              placeholder="Optional transcript hint or fallback transcript"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {audioSamples.map((sample) => (
                <Button
                  key={sample.label}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAudioTranscript(sample.transcript)}
                >
                  {sample.label}
                </Button>
              ))}
            </div>
            <Button onClick={onAudioRun} disabled={audioLoading || (!audioFile && !audioTranscript.trim())} className="mt-3">
              {audioLoading ? "Scanning audio..." : "Scan audio"}
              <FileAudio className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 text-sm font-medium text-slate-950 dark:text-white">
                  <Film className="h-4 w-4 text-teal-700 dark:text-teal-300" />
                  Video frame fusion
                </p>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                  Combine transcript, frame description, OCR text, and detected objects for the video endpoint.
                </p>
              </div>
              <Badge variant="outline">/moderate/video</Badge>
            </div>
            <div className="grid gap-3">
              <label className="flex min-h-20 cursor-pointer items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600 transition hover:border-teal-500 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-teal-300">
                <span className="flex h-12 w-12 items-center justify-center rounded-md bg-teal-50 text-teal-700 dark:bg-teal-900 dark:text-teal-100">
                  <UploadCloud className="h-5 w-5" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium text-slate-800 dark:text-slate-100">
                    {videoFile ? videoFile.name : "Choose a video file"}
                  </span>
                  <span className="mt-1 block text-xs text-slate-500 dark:text-slate-300">MP4, MOV, WEBM, or AVI up to 60 MB</span>
                </span>
                <input
                  className="sr-only"
                  type="file"
                  accept="video/mp4,video/quicktime,video/webm,video/x-msvideo"
                  onChange={(event) => onVideoFileChange(event.target.files?.[0] ?? null)}
                />
              </label>
              <Textarea
                value={videoTranscript}
                onChange={(event) => setVideoTranscript(event.target.value)}
                placeholder="Optional transcript or spoken words"
              />
              <div className="grid gap-3 md:grid-cols-3">
                <input
                  value={videoFrameDescription}
                  onChange={(event) => setVideoFrameDescription(event.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Frame description"
                />
                <input
                  value={videoOcrText}
                  onChange={(event) => setVideoOcrText(event.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Frame OCR text"
                />
                <input
                  value={videoObjects}
                  onChange={(event) => setVideoObjects(event.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Objects, comma separated"
                />
              </div>
              <Button
                onClick={onVideoRun}
                disabled={
                  videoLoading ||
                  (!videoFile && ![videoTranscript, videoFrameDescription, videoOcrText, videoObjects].some((value) => value.trim()))
                }
              >
                {videoLoading ? "Scanning video..." : "Scan video"}
                <Film className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}

        {error ? (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-400/25 dark:bg-red-950/45 dark:text-red-200">{error}</div>
        ) : null}

        <AnimatePresence mode="wait">
          {result ? (
            <motion.div
              key={result.request_id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="mt-5 space-y-4"
            >
              <div className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-950/70">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-950 dark:text-white">{result.decision.explanation}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      Tenant {result.tenant_id} | {result.metadata.latency_ms}ms | {result.metadata.policy_version} |{" "}
                      {modelPathLabel(result.metadata.fallback_model)}
                    </p>
                  </div>
                  <Badge variant={action === "block" ? "danger" : action === "allow" ? "success" : "secondary"}>
                    {result.decision.triggered_categories.join(", ") || "no risk"}
                  </Badge>
                </div>
                {result.metadata.fallback_model !== "not_used" ? (
                  <div className="mt-3">
                    <ConfidenceNotice fallbackModel={result.metadata.fallback_model} />
                  </div>
                ) : null}
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {topScores.map((score) => (
                  <div key={score.category} className="rounded-lg border border-border bg-white p-4 dark:bg-slate-950/70">
                    <div className="mb-2 flex items-center justify-between text-sm">
                      <span className="font-medium text-slate-800 dark:text-slate-100">{score.category}</span>
                      <span className="text-slate-500 dark:text-slate-400">{Math.round(score.score * 100)}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                      <div
                        className={cn(
                          "h-2 rounded-full",
                          score.score >= 0.72 ? "bg-red-500" : score.score >= 0.45 ? "bg-amber-500" : "bg-teal-500",
                        )}
                        style={{ width: `${Math.max(4, score.score * 100)}%` }}
                      />
                    </div>
                    <p className="mt-2 min-h-8 text-xs text-slate-500 dark:text-slate-400">{score.reasons[0] ?? score.severity}</p>
                  </div>
                ))}
              </div>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-5 grid gap-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 sm:grid-cols-3"
            >
              <div className="flex items-center gap-2">
                <LockKeyhole className="h-4 w-4 text-teal-700 dark:text-teal-300" />
                API-key scoped
              </div>
              <div className="flex items-center gap-2">
                <BadgeCheck className="h-4 w-4 text-teal-700 dark:text-teal-300" />
                Policy evaluated
              </div>
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-teal-700 dark:text-teal-300" />
                Stored for audit
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}
