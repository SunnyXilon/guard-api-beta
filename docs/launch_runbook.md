# Guard API Launch Runbook

This runbook covers the remaining production work for auth, payments, database, image moderation, deployment, security, product readiness, and operations.

## 1. Production Auth

- Create a Clerk production application.
- Set the frontend key in `frontend/.env.production.local`:
  - `VITE_CLERK_PUBLISHABLE_KEY=pk_live_...`
- Set backend verification:
  - `RTCM_SELF_SERVICE_ONBOARDING_ENABLED=true`
  - `RTCM_CLERK_JWKS_URL=https://<clerk-frontend-api>/.well-known/jwks.json`
  - `RTCM_CLERK_ISSUER=https://<clerk-issuer>`
  - `RTCM_CLERK_AUTHORIZED_PARTIES=["https://app.<domain>"]`
- Smoke test sign-up, sign-in, workspace creation, dashboard session creation, and moderation key copy.

## 2. Payments

- Create Stripe products and recurring prices for `starter`, `growth`, and `scale`.
- Set:
  - `RTCM_BILLING_REQUIRED=true`
  - `RTCM_STRIPE_SECRET_KEY=sk_live_...`
  - `RTCM_STRIPE_WEBHOOK_SECRET=whsec_...`
  - `RTCM_BILLING_PLAN_PRICE_IDS={"starter":"price_...","growth":"price_...","scale":"price_..."}`
  - `RTCM_BILLING_SUCCESS_URL=https://app.<domain>?billing=success`
  - `RTCM_BILLING_CANCEL_URL=https://app.<domain>?billing=cancelled`
  - `RTCM_BILLING_PORTAL_RETURN_URL=https://app.<domain>/dashboard`
- Configure Stripe webhook endpoint:
  - `POST https://api.<domain>/billing/webhook`
- Configure the Stripe customer portal so customers can update payment methods and cancel subscriptions.
- Test `checkout.session.completed`, `customer.subscription.updated`, and `customer.subscription.deleted`.

## 3. Database

- Use managed PostgreSQL, not SQLite.
- Set `RTCM_DATABASE_URL=postgresql+psycopg://...`.
- Run `alembic upgrade head` before starting the API.
- Enable daily backups and do one restore test before accepting paid traffic.
- For the included single-host compose file, create `secrets/postgres-password.txt`, set the same password in
  `.env.production`, then run `docker compose -f docker-compose.production.yml up -d postgres redis inference api`.
- Confirm `/ready` reports `database: ok` before routing traffic to the API.

## 4. Image Moderation

- Create a Google Cloud service account with Vision API access.
- Mount the JSON credential outside source control.
- Set:
  - `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-vision-service-account.json`
  - `RTCM_IMAGE_SCANNING_REQUIRED=true`
- Smoke test image upload with a real PNG/JPG/WEBP and confirm scanner metadata is returned.

## 5. Audio Moderation

- Create an OpenAI API key for server-side transcription.
- Set:
  - `RTCM_OPENAI_API_KEY=sk-proj-...`
  - `RTCM_AUDIO_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe`
  - `RTCM_AUDIO_TRANSCRIPTION_REQUIRED=true`
  - `RTCM_AUDIO_UPLOAD_MAX_BYTES=25000000`
- Keep the OpenAI key in the backend secret manager only.
- Smoke test uploaded `.mp3`, `.wav`, `.m4a`, and `.webm` files through `/moderate/audio`.
- Confirm the response includes `metadata.extracted_text` and `modality_details.transcription_provider`.

## 6. Social Connectors

- Create a Meta developer app and request the permissions needed for comment moderation, such as Instagram/Facebook comment management permissions.
- Implement the customer OAuth flow so each influencer or Page owner connects their own account.
- Store the connected account token in the connected account metadata as `access_token` or `page_access_token`.
- Use:
  - `POST /connectors/webhook/events` for generic social/email/website events.
  - `POST /connectors/meta/webhook` for Meta-shaped comment webhook payloads.
  - `GET /social-inbox` for the dashboard inbox.
  - `POST /social-actions/{event_id}/hide` to hide comments.
  - `POST /social-actions/{event_id}/delete` to delete comments.
  - `POST /social-actions/{event_id}/allow` to unhide/allow comments.
- When a token is present, Instagram hide actions call Meta Graph with `hide=true`; Facebook hide actions call `is_hidden=true`.
- When no token is present, the action is recorded locally so demos and review workflows still work.
- Before launch, test with a real Meta sandbox/Page account and confirm the comment changes inside Instagram/Facebook.

## 7. Deployment

- Build API and inference containers from `Dockerfile.api` and `Dockerfile.inference`.
- Use `docker-compose.production.yml` only as a reference or single-host deployment file; prefer managed Postgres in production.
- Expose API through HTTPS at `https://api.<domain>`.
- Deploy the frontend as a static Vite app with `VITE_API_BASE_URL=https://api.<domain>`.
- Keep public Swagger/OpenAPI docs disabled with `RTCM_EXPOSE_API_DOCS=false`; customers should use the signed-in dashboard API docs and examples.
- Configure health checks:
  - `/health` for process liveness.
  - `/ready` for dependency readiness.

## 8. Security

- Set a strong `RTCM_SESSION_SECRET`.
- Set `RTCM_BOOTSTRAP_API_KEYS=false` and remove demo keys.
- Set `RTCM_RATE_LIMIT_REDIS_URL=redis://...` for shared production rate limiting.
- Set `RTCM_CONNECTOR_WEBHOOK_SIGNING_SECRET=<random secret>` for signed connector webhook bodies.
- Restrict `RTCM_CORS_ALLOWED_ORIGINS` to production frontend domains.
- Store Stripe, Clerk, database, Redis, Google, and Meta credentials in the hosting platform secret manager.
- Store OpenAI transcription credentials in the backend secret manager only.
- Keep `secrets/`, `.env`, and `.env.production` out of git.

## 9. Product Polish

- Finalize public pricing and moderation-credit copy.
- Add final Terms, Privacy, Refund, and acceptable-use pages.
- Verify onboarding from blank account to first API call.
- Verify review-case workflow: create risky moderation request, assign, add note, resolve, and confirm audit event.
- Record a short demo video and add screenshots to the landing page before launch.

## 10. Operations

- Add uptime monitoring for `/health` and `/ready`.
- Add error monitoring for API exceptions and frontend runtime failures.
- Set log retention and avoid logging raw customer content in external tools.
- Define support routing, refund handling, and incident response owner.
- Track funnel metrics: signups, workspace creation, checkout started, checkout completed, first API call, and credit usage.
- Use `docs/operations_runbook.md` and `docs/support_and_refund_process.md` as the launch operating checklist.
