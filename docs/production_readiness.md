# Guard API Production Readiness

Guard API is usable as a local prototype, but paid monthly use needs operational controls around security, billing, deployment, and support.

## Fixed in the first hardening pass

- Production startup now rejects unsafe demo defaults.
- Policy threshold updates validate values between `0.0` and `1.0`.
- Policy updates are written to the audit log.
- API requests have a simple per-key/per-IP rate limit.
- Image uploads reject unsupported MIME types before scanning.
- Dashboard API keys are kept in `sessionStorage` instead of long-lived `localStorage`.
- Tenant API keys now have scopes:
  - `moderation` for production API integrations.
  - `dashboard` for dashboard access.
  - `policy:write` for policy and key administration.
- Tenant admins can create new moderation-only keys from the dashboard or `/api-keys`.
- Tenants have a monthly Guard credit quota and requests are rejected once the credit quota is exhausted.
- Dashboard admin keys are exchanged for short-lived bearer session tokens before dashboard calls.
- Stripe checkout and webhook endpoints are available for plan/quota synchronization.
- Dashboard demo keys and API URLs are loaded from frontend environment variables instead of being hardcoded in the React bundle.
- Tenant admins can deactivate API keys.
- Review cases can be moved through `open`, `in_review`, `resolved`, and `dismissed` states with reviewer notes.
- Policy thresholds below `0.05` are rejected to avoid accidentally reviewing or blocking every request.
- Clerk authentication gates the frontend dashboard route and redirects sign-in/sign-up users to `/dashboard`.
- Signed-in users can create a local/private-beta workspace from `/dashboard`, which creates a tenant, starts a dashboard session, and shows the first moderation key once.
- Tests cover dashboard data, policy update audit events, invalid thresholds, unsafe production config, and image upload MIME rejection.

## Must do before charging customers

- Use PostgreSQL in production. Do not use SQLite.
- Disable bootstrap demo keys:
  - `RTCM_BOOTSTRAP_API_KEYS=false`
  - replace all `rtcm_*_live_key` demo values with generated customer keys.
- Set production CORS origins only, for example:
  - `RTCM_CORS_ALLOWED_ORIGINS=["https://app.guardapi.example"]`
- Store secrets in a managed secret store, not in source files or frontend code.
- Put the API behind HTTPS.
- Create real Stripe products/prices and configure live billing secrets.
- Add persistent distributed rate limiting. The current limiter is in-memory and per process.
- Configure Clerk backend verification with `RTCM_CLERK_JWKS_URL` or `RTCM_CLERK_JWT_KEY`, plus issuer and authorized-party checks for the deployed frontend origin.
- Run Alembic migrations in deploys instead of relying on `create_all`.
- Add structured logs, request IDs, and error monitoring.
- Add backups and restore testing for the production database.
- Extend the review workflow with assignment, filtering, SLA tracking, and bulk actions.
- Add legal pages and customer terms for moderation data retention and acceptable use.
- Use `/ready` as the deploy readiness check and keep `/health` as the liveness check.
- Follow `docs/launch_runbook.md` for the eight launch workstreams.

## Recommended launch path

1. Deploy API, inference, and Postgres in a private cloud environment.
2. Configure Google Cloud Vision credentials through the hosting platform secret manager.
3. Create a real tenant onboarding flow that generates scoped keys.
4. Add Stripe subscriptions and store plan limits per tenant.
5. Add persistent quota/rate-limit counters in Redis or Postgres.
6. Run a private beta with two or three users before public launch.
