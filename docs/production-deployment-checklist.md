# Production Deployment Checklist

Use this before exposing Guard API to real customer traffic.

## Required Environment

- Set `RTCM_ENVIRONMENT=production`.
- Set `RTCM_DATABASE_URL` to a managed PostgreSQL DSN.
- Set a strong random `RTCM_SESSION_SECRET`.
- Set `RTCM_BOOTSTRAP_API_KEYS=false`.
- Set `RTCM_CORS_ALLOWED_ORIGINS` to the production frontend domains only.
- Set `RTCM_CLERK_JWKS_URL` or `RTCM_CLERK_JWT_KEY`.
- Set `RTCM_CLERK_ISSUER` and `RTCM_CLERK_AUTHORIZED_PARTIES`.
- Set `RTCM_RATE_LIMIT_REDIS_URL` for shared rate limiting across API instances.
- Set `RTCM_IMAGE_SCANNING_REQUIRED=true` when image upload scanning must be live.
- Set `RTCM_BILLING_REQUIRED=true` before enabling paid plans.
- Set `RTCM_CONNECTOR_WEBHOOK_SIGNING_SECRET` so connector webhook bodies can be HMAC verified.

## Billing

- Set `RTCM_STRIPE_SECRET_KEY`.
- Set `RTCM_STRIPE_WEBHOOK_SECRET`.
- Set `RTCM_BILLING_SUCCESS_URL` and `RTCM_BILLING_CANCEL_URL`.
- Set `RTCM_BILLING_TRIAL_DAYS=30` for the first-month free trial.
- Set `RTCM_BILLING_PLAN_PRICE_IDS` with `starter`, `growth`, and `scale` Stripe price IDs.
- Configure the Stripe webhook endpoint: `/billing/webhook`.
- Confirm `/ready` reports billing as configured after secrets are deployed.

## Data And Security

- Run `alembic upgrade head` before starting the API.
- Confirm no demo keys remain in environment variables.
- Confirm dashboard sessions expire at the intended TTL.
- Confirm Google Vision credentials are present if image upload scanning is enabled.
- Confirm connector webhook requests without a valid `X-RTCM-Signature` are rejected.
- Confirm `/ready` returns `200` before routing customer traffic.
- Configure database backups and restore testing.
- Configure log retention and remove sensitive payloads from logs.

## Release Verification

- Run backend tests: `pytest`.
- Run frontend build: `cd frontend && npm run build`.
- Smoke test:
  - Clerk sign-up and sign-in.
  - Workspace creation.
  - One-time moderation key copy.
  - Text moderation request with the moderation key.
  - Dashboard usage update.
  - Review case assignment and resolution.
  - Billing checkout start.
