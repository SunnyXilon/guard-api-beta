# Guard API Integration Guide

Guard API exposes tenant-scoped moderation endpoints for text, image, uploaded audio, and video frame fusion. Use moderation-scoped API keys in production apps and admin/dashboard keys only for internal tools.

Ready-to-copy customer examples are available in:

- `examples/node/guard-api-client.mjs`
- `examples/node/express-moderation-server.mjs`
- `examples/python/guard_api_client.py`
- `examples/python/fastapi_moderation_server.py`

## Authentication

Send the tenant moderation key with every moderation request:

```http
X-API-Key: rtcm_customer_live_key
```

Do not ship dashboard/admin keys to client apps. For browsers and mobile apps, call Guard API from your own backend whenever possible.

## Text Moderation

```bash
curl -X POST https://api.example.com/moderate/text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: rtcm_customer_live_key" \
  -d '{
    "text": "Guaranteed profit investment, whatsapp me for deal.",
    "metadata": {
      "content_id": "msg_123",
      "user_id": "user_456",
      "language": "en",
      "channel": "chat",
      "region": "IN"
    }
  }'
```

For Hindi or Hinglish content, set `metadata.language` to values such as `hi`, `hi-Latn`, or `mixed`.

## Image Moderation

Upload a real image when your app has the file bytes:

```bash
curl -X POST https://api.example.com/moderate/image \
  -H "X-API-Key: rtcm_customer_live_key" \
  -F "image=@upload.jpg" \
  -F "channel=profile_upload" \
  -F "region=IN"
```

Send precomputed image metadata when another service already extracted OCR/labels:

```json
{
  "image_caption": "Uploaded product photo",
  "detected_objects": ["pills", "cash"],
  "ocr_text": "buy now",
  "metadata": {
    "content_id": "img_123",
    "channel": "listing_image",
    "region": "IN"
  }
}
```

## Audio Moderation

Upload real audio files when the backend has file bytes. Guard API transcribes the audio when transcription is configured:

```bash
curl -X POST https://api.example.com/moderate/audio \
  -H "X-API-Key: rtcm_customer_live_key" \
  -F "audio=@voice-note.mp3" \
  -F "transcript_hint=Optional context or fallback transcript" \
  -F "content_id=voice_123" \
  -F "channel=voice_message" \
  -F "language=en"
```

If your app already has a transcript, you can also send JSON:

```json
{
  "audio_url": "https://cdn.example.com/audio/msg_123.mp3",
  "transcript_hint": "I will find you and you deserve pain.",
  "metadata": {
    "content_id": "voice_123",
    "channel": "voice_message",
    "language": "en"
  }
}
```

Supported uploads include MP3, MP4/M4A, WAV, and WEBM up to 25 MB.

## Video Moderation

Send transcript cues plus sampled frame metadata:

```bash
curl -X POST https://api.example.com/moderate/video \
  -H "Content-Type: application/json" \
  -H "X-API-Key: rtcm_customer_live_key" \
  -d '{
    "video_url": "https://cdn.example.com/video/clip_123.mp4",
    "transcript_hint": "message me on telegram for guaranteed profit",
    "frames": [
      {
        "timestamp_ms": 1000,
        "description": "close-up of pills on a table",
        "ocr_text": "buy now",
        "detected_objects": ["drugs", "cash"]
      }
    ],
    "metadata": {
      "content_id": "video_123",
      "channel": "listing_video",
      "region": "IN"
    }
  }'
```

You can also upload a video file directly. The API samples frames with OpenCV when local vision safety dependencies are installed:

```bash
curl -X POST https://api.example.com/moderate/video \
  -H "X-API-Key: rtcm_customer_live_key" \
  -F "video=@clip.mp4" \
  -F "transcript_hint=message me on telegram for guaranteed profit" \
  -F "channel=listing_video" \
  -F "region=IN"
```

The local visual safety model uses CLIP-style labels including the original violence labels plus explicit sexual content, nudity, adult content, sexual activity, suggestive image, weapons, blood, gore, drug use, illegal drugs, child unsafe content, and self harm. Install the ML extras with `pip install -e .[ml]` for local file scanning.

## Response Handling

Every moderation response includes:

- `request_id`: store this with your content.
- `decision.action`: `allow`, `review`, or `block`.
- `decision.triggered_categories`: risk categories that crossed policy thresholds.
- `review_case_id`: present when a review or block creates a follow-up case.
- `category_scores`: category-level scores and reasons.

Recommended enforcement:

- `allow`: publish or send content.
- `review`: hold content, hide from public view, or allow with reduced visibility depending on your product.
- `block`: reject content and show a neutral policy message.

## Node/Express Example

```js
app.post("/messages", async (req, res) => {
  const moderation = await fetch(`${process.env.GUARD_API_URL}/moderate/text`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": process.env.GUARD_API_KEY,
    },
    body: JSON.stringify({
      text: req.body.text,
      metadata: {
        content_id: req.body.id,
        user_id: req.user.id,
        language: req.body.language || "en",
        channel: "chat",
        region: "IN",
      },
    }),
  }).then((response) => response.json());

  if (moderation.decision.action === "block") {
    return res.status(422).json({ error: "Message cannot be sent." });
  }

  await saveMessage({
    ...req.body,
    moderationRequestId: moderation.request_id,
    moderationAction: moderation.decision.action,
  });

  res.status(moderation.decision.action === "review" ? 202 : 201).json({ ok: true });
});
```

## Python/FastAPI Example

```py
import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.post("/listings")
async def create_listing(payload: dict):
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            "https://api.example.com/moderate/text",
            headers={"X-API-Key": "rtcm_customer_live_key"},
            json={
                "text": payload["description"],
                "metadata": {
                    "content_id": payload["id"],
                    "user_id": payload["seller_id"],
                    "channel": "listing",
                    "region": "IN",
                },
            },
        )
    response.raise_for_status()
    moderation = response.json()
    if moderation["decision"]["action"] == "block":
        raise HTTPException(status_code=422, detail="Listing failed policy checks.")
    return {"status": moderation["decision"]["action"], "request_id": moderation["request_id"]}
```

## Platform Notes

- Marketplaces: moderate listing titles, descriptions, images, seller messages, and profile bios.
- Social/community apps: moderate posts, comments, DMs, usernames, avatars, and reports.
- Edtech/kids apps: enable protected mode, use stricter thresholds, and route review decisions to human moderation.
- Dating/chat apps: moderate profile images, bios, DMs, voice notes, and link-sharing.
- Creator platforms: moderate uploads before public publishing and use `review_case_id` for creator appeals.

## Operational Guidance

- Store `request_id`, action, and triggered categories on your content records.
- Keep moderation keys server-side.
- Retry only idempotently; duplicate calls create duplicate moderation records.
- Use dashboard review cases for human decisions and audit trails.
- Monitor `402` responses as quota exhaustion and `429` responses as rate limiting.
