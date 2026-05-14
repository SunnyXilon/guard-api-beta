# Private Beta Launch Checklist

This project is now suitable for a private beta after you connect real services.

## Required services

- Managed PostgreSQL.
- HTTPS hosting for the API.
- HTTPS hosting for the frontend.
- Secret manager for database URL, session secret, Google credentials, and billing keys.
- Google Cloud Vision enabled with a service-account JSON.
- Stripe products/prices if you want paid subscriptions.

## Production environment

Start from `.env.production.example`.

Important values:

- `RTCM_ENVIRONMENT=production`
- `RTCM_SESSION_SECRET`: strong random string.
- `RTCM_DATABASE_URL`: managed Postgres DSN.
- `RTCM_CORS_ALLOWED_ORIGINS`: frontend origin only.
- `RTCM_BOOTSTRAP_API_KEYS=false`
- `GOOGLE_APPLICATION_CREDENTIALS`: secret-mounted service account path.
- `RTCM_STRIPE_SECRET_KEY`: live or test Stripe secret key.
- `RTCM_STRIPE_WEBHOOK_SECRET`: webhook signing secret.
- `RTCM_BILLING_PLAN_PRICE_IDS`: JSON map of plan names to Stripe price IDs.
- `RTCM_BILLING_PLAN_QUOTAS`: JSON map of plan names to monthly moderation-credit quotas.
- `RTCM_CONNECTOR_WEBHOOK_SIGNING_SECRET`: random HMAC secret for connector webhook payloads.

The app refuses to start in production if SQLite, demo keys, localhost CORS, or the dev session secret are still configured.

## Tenant onboarding

For each beta customer:

1. Create a tenant row.
2. Set `plan_name` and `monthly_quota` in moderation credits.
3. Create one admin key with `dashboard, policy:write` scopes.
4. Have the customer create moderation-only integration keys from the dashboard.
5. Share only the admin key through a secure channel.

## Stripe setup

1. Create Stripe products and recurring prices for `starter`, `growth`, and `scale`.
2. Put those price IDs in `RTCM_BILLING_PLAN_PRICE_IDS`.
3. Configure a webhook endpoint:
   - `POST https://api.your-domain.example/billing/webhook`
4. Subscribe to:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Put the webhook signing secret in `RTCM_STRIPE_WEBHOOK_SECRET`.

Implemented billing endpoints:

- `GET /billing/status`
- `POST /billing/checkout`
- `POST /billing/webhook`

## Current launch state

Ready for:

- Private demos.
- Private beta with friendly users.
- Metered usage tracking.
- Quota enforcement.
- Scoped API key management.
- Stripe checkout and webhook plumbing after Stripe keys and price IDs are configured.

Not ready for:

- Fully self-serve signup.
- Distributed rate limiting across many API replicas.
- Enterprise SSO or team-member roles.
