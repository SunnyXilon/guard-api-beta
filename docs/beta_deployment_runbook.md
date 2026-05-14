# Beta Deployment Runbook

This is the recommended private beta setup:

- Backend API: Render web service from `render.yaml`
- Inference service: Render private service from `render.yaml`
- Database: Render PostgreSQL from `render.yaml`
- Frontend: Vercel static Vite app from `vercel.json`
- Auth: Clerk production or beta app
- Billing: disabled for beta
- Google Vision: disabled for beta unless credentials are ready

## 1. Push the repository to GitHub

Render and Vercel both deploy from a Git provider. Push the project to a private GitHub repository before creating the services.

Do not commit `.env`, local logs, `.venv`, `frontend/node_modules`, or `rtcm.db`.

## 2. Create the Render backend

In Render, create a Blueprint from the repository root. Render reads `render.yaml` and creates:

- `guard-api-beta`
- `guard-api-inference-beta`
- `guard-api-postgres-beta`

During Blueprint creation, fill the synced variables:

```text
RTCM_CORS_ALLOWED_ORIGINS=["https://your-vercel-beta-url.vercel.app"]
RTCM_CLERK_JWKS_URL=https://your-clerk-domain/.well-known/jwks.json
RTCM_CLERK_ISSUER=https://your-clerk-domain
RTCM_CLERK_AUTHORIZED_PARTIES=["https://your-vercel-beta-url.vercel.app"]
```

Keep these beta values unless you intentionally enable the external services:

```text
RTCM_BILLING_REQUIRED=false
RTCM_IMAGE_SCANNING_REQUIRED=false
RTCM_LOCAL_VISION_SAFETY_ENABLED=false
RTCM_RATE_LIMIT_ENABLED=false
```

After deploy, open:

```text
https://your-render-api.onrender.com/health
https://your-render-api.onrender.com/ready
```

`/health` should be `ok`. `/ready` should be `ok` after Clerk, database, and inference are reachable.

## 3. Create the Vercel frontend

Import the same GitHub repository into Vercel.

Use the root directory of the repository. `vercel.json` handles the frontend build from `frontend/`.

Set Vercel environment variables:

```text
VITE_API_BASE_URL=https://your-render-api.onrender.com
VITE_CLERK_PUBLISHABLE_KEY=pk_live_or_beta_key_from_clerk
VITE_DEMO_TEXT_API_KEY=
VITE_DEMO_IMAGE_API_KEY=
VITE_DEMO_ADMIN_API_KEY=
```

Redeploy after adding environment variables.

## 4. Configure Clerk

In Clerk:

- Add the Vercel beta URL to allowed origins/redirects.
- Set sign-in and sign-up redirects to `/dashboard`.
- Use invite-only access if possible for private beta.
- Copy the frontend API / issuer values into Render.
- Copy the publishable key into Vercel.

## 5. Run the beta smoke test

After backend and frontend are live:

```powershell
$env:BETA_SMOKE_API_BASE="https://your-render-api.onrender.com"
.\.venv\Scripts\python.exe scripts\beta_smoke.py
```

The smoke test must pass before inviting beta users.

## 6. Invite beta users

Send testers the Vercel beta URL and ask them to test:

1. Sign in.
2. Create or open a workspace.
3. Open Playground and scan text/image/audio/video/social examples.
4. Check Marketplace decisions.
5. Resolve a Review case.
6. Try the How to use guide.
7. Report anything confusing, broken, slow, or missing.

## 7. Beta limitations

For this beta profile:

- Playground scans use moderation credits.
- Stripe billing is disabled.
- Google Vision is disabled.
- Local CLIP image/video safety is disabled on the API service to keep deployment lighter.
- The separate inference service handles text model scoring.
- Social platform actions are recorded locally unless Meta OAuth is configured.
