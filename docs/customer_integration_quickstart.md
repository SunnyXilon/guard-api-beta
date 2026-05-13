# Customer Integration Quickstart

This guide is for a customer integrating Guard API into their app backend.

## 1. Create a moderation key

Open the dashboard, go to **API keys**, and create a key with the `moderation` scope.

Store the key only on your server. Do not put it in browser JavaScript, mobile apps, or public repositories.

## 2. Send your first request

```bash
curl -X POST https://api.your-domain.example/moderate/text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $RTCM_MODERATION_KEY" \
  -d '{
    "text": "Guaranteed profit investment, whatsapp me for deal.",
    "metadata": {
      "content_id": "comment_123",
      "user_id": "user_456",
      "channel": "marketplace_chat",
      "region": "global"
    }
  }'
```

## 3. Act on the decision

The response includes:

- `decision.action`: `allow`, `review`, or `block`
- `decision.triggered_categories`: policy categories that drove the action
- `category_scores`: risk scores by category
- `review_case_id`: present when the item needs human review

Recommended product behavior:

- `allow`: publish or send the content.
- `review`: hold the content and show it in the review queue.
- `block`: stop the content and show a user-safe rejection message.

## 4. Connect webhooks

Use `POST /connectors/webhook/events` when an external system wants Guard API to moderate comments, messages, or form submissions.

If `RTCM_CONNECTOR_WEBHOOK_SIGNING_SECRET` is configured, sign the raw JSON body:

```text
X-RTCM-Signature: sha256=<hmac_sha256_hex>
```

## 5. Production checklist

- Use a production moderation key.
- Send requests from your backend only.
- Pass stable `content_id` and `user_id` metadata.
- Monitor `429` responses and retry with backoff.
- Review dashboard usage daily during launch week.
