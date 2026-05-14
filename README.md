# Guard API

`Guard API` is a startup-ready trust-and-safety API for UGC products. It includes persistent moderation storage, tenant API-key auth, durable audit logs, a separate inference service for transformer-backed text scoring, and a React marketing/demo UI.

## What is implemented

- PostgreSQL/SQLAlchemy-backed persistence for tenants, API keys, policies, moderation requests, results, review cases, and audit events
- API-key authentication with tenant scoping through the `X-API-Key` header
- Transactional moderation persistence and audit logging
- A multimodal moderation API for text, image, audio, and video
- A separate FastAPI inference service for HuggingFace `unitary/toxic-bert` text scoring
- Google Cloud Vision image upload scanning for labels, OCR, and SafeSearch signals
- Optional local CLIP-style visual safety scanning for images and sampled video frames
- Cloud-ready config, Dockerfiles, and `docker-compose.yml`
- Alembic migration scaffolding for schema management

## Architecture

1. The main API authenticates each request with an API key and resolves the tenant from the key.
2. Fast local rules score content immediately for low latency.
3. Ambiguous text is sent to the separate inference service for transformer-backed scoring.
4. The API fuses model signals, evaluates policy, and persists results transactionally.
5. Review cases and audit events are stored durably for downstream operations and analytics.

## API surface

- `GET /health`
- `POST /moderate/text`
- `POST /moderate/image`
- `POST /moderate/audio`
- `POST /moderate/video`
- `GET /policies/me`
- `GET /cases`

Customer integration examples are in [`examples/`](examples/):

- Node reusable client and Express server.
- Python reusable client and FastAPI server.
- Decision handling for `allow`, `review`, and `block`.

Example request:

```json
{
  "text": "Guaranteed profit investment, whatsapp me for deal.",
  "metadata": {
    "content_id": "c_123",
    "user_id": "u_999",
    "language": "en",
    "channel": "listing_chat",
    "region": "global"
  }
}
```

Use it with:

```bash
curl -X POST http://127.0.0.1:8000/moderate/text ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: rtcm_market_live_key" ^
  -d "{\"text\":\"Guaranteed profit investment, whatsapp me for deal.\"}"
```

Dashboard/admin routes require an admin-scoped key:

```bash
curl http://127.0.0.1:8000/dashboard ^
  -H "X-API-Key: rtcm_market_admin_key"
```

Create a moderation-only integration key:

```bash
curl -X POST http://127.0.0.1:8000/api-keys ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: rtcm_market_admin_key" ^
  -d "{\"name\":\"production-webhook\",\"scopes\":[\"moderation\"]}"
```

Start Stripe checkout for a plan after Stripe is configured:

```bash
curl -X POST http://127.0.0.1:8000/billing/checkout ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: rtcm_market_admin_key" ^
  -d "{\"plan_name\":\"growth\"}"
```

Example image request:

```json
{
  "tenant_id": "kids-safe",
  "image_caption": "Uploaded image from a direct message",
  "detected_objects": ["child", "bedroom"],
  "ocr_text": "underage pics"
}
```

Example real image upload:

```bash
curl -X POST http://127.0.0.1:8000/moderate/image ^
  -H "X-API-Key: rtcm_kids_live_key" ^
  -F "image=@C:\path\to\image.jpg" ^
  -F "channel=profile_upload"
```

Example real audio upload:

```bash
curl -X POST http://127.0.0.1:8000/moderate/audio ^
  -H "X-API-Key: rtcm_market_live_key" ^
  -F "audio=@C:\path\to\voice-note.mp3" ^
  -F "transcript_hint=Optional context or fallback transcript" ^
  -F "channel=voice_message"
```

Uploaded audio is transcribed when `RTCM_OPENAI_API_KEY` is configured. Set `RTCM_AUDIO_TRANSCRIPTION_REQUIRED=true`
in production if you sell audio-file moderation as a paid feature.

Example video request:

```json
{
  "tenant_id": "marketplace",
  "transcript_hint": "message me on telegram for guaranteed profit",
  "frames": [
    {
      "timestamp_ms": 1000,
      "description": "close-up of pills on a table",
      "ocr_text": "buy now",
      "detected_objects": ["drugs", "cash"]
    }
  ]
}
```

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .[dev]
copy .env.example .env
uvicorn app.main:app --reload
uvicorn inference_service.main:app --port 8001
pytest
```

For local visual image/video safety scanning, install ML extras instead:

```bash
pip install -e .[dev,ml]
```

## Run the UI

```bash
cd frontend
npm install
copy .env.example .env.development.local
npm run dev
```

Open `http://127.0.0.1:5173` after the API and inference service are running.
Set `VITE_DEMO_TEXT_API_KEY`, `VITE_DEMO_IMAGE_API_KEY`, and `VITE_DEMO_ADMIN_API_KEY` in `frontend/.env.development.local` only for local demos.

## Local data safety

Use PostgreSQL for day-to-day development so workspaces, API keys, review cases, social inbox data, and audit history persist across app restarts. The project `.env` should contain a PostgreSQL URL:

```bash
RTCM_DATABASE_URL=postgresql+psycopg://guard_api:guard_api_password@127.0.0.1:5432/guard_api
```

The backend loads the repository-root `.env` by absolute path, so starting the API from another folder will still use the same configured database. If older data was created in the local SQLite file, copy missing rows into PostgreSQL with:

```bash
.venv\\Scripts\\python.exe scripts\\migrate_sqlite_to_postgres.py
.venv\\Scripts\\python.exe scripts\\migrate_sqlite_to_postgres.py --execute
```

The first command is a dry run. The second commits the copy and skips duplicate records.

## Beta smoke test

Before sending the app to beta testers, run the end-to-end smoke flow against the local API:

```bash
.venv\\Scripts\\python.exe scripts\\beta_smoke.py
```

The script verifies the core beta workflow: health check, workspace reopen/create, dashboard session, dashboard playground moderation without an external app, moderation API key creation, risky text moderation, dashboard decision visibility, review case resolution, social inbox ingestion, and social action recording. It uses the configured PostgreSQL-backed API at `http://127.0.0.1:8100` by default.

## Beta deployment

Use [docs/beta_deployment_runbook.md](docs/beta_deployment_runbook.md) to deploy the private beta. The repo includes:

- `render.yaml` for the Render API, private inference service, and PostgreSQL database.
- `vercel.json` for deploying the Vite frontend from the repo root.
- `scripts/beta_smoke.py` for post-deploy end-to-end verification.

## Clerk authentication

The public page is separate from the authenticated client dashboard. Clerk gates `/dashboard`, and sign-in/sign-up buttons redirect users there after authentication.

1. Create a Clerk application in the Clerk Dashboard.
2. Copy the Clerk publishable key.
3. Add it to `frontend/.env.development.local`:

```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_key_here
```

4. Restart the Vite dev server after changing env files.

After Clerk sign-in, new users can create a workspace from `/dashboard`. This creates a tenant, starts a dashboard session, and shows the first moderation API key once. Existing tenants can still paste a tenant admin key in the sidebar.

The backend verifies Clerk bearer tokens and maps the Clerk user or active organization to a tenant. Configure either `RTCM_CLERK_JWKS_URL` or `RTCM_CLERK_JWT_KEY` before enabling self-service onboarding outside local development. In Clerk, find the JWKS URL / JWT public key on the API keys or JWT templates page, then set:

```bash
RTCM_SELF_SERVICE_ONBOARDING_ENABLED=true
RTCM_CLERK_JWKS_URL=https://your-clerk-frontend-api/.well-known/jwks.json
RTCM_CLERK_ISSUER=https://your-clerk-issuer
RTCM_CLERK_AUTHORIZED_PARTIES=["http://127.0.0.1:5174"]
```

## Run with Docker

```bash
docker compose up --build
```

Services:
- API: `http://127.0.0.1:8000`
- Inference: `http://127.0.0.1:8001`
- Postgres: `localhost:5432`

## Launch and customer docs

- `docs/customer_integration_quickstart.md`: customer first API call and webhook signing guide.
- `docs/launch_runbook.md`: production auth, payments, database, deployment, and operations workstreams.
- `docs/production-deployment-checklist.md`: release checklist before real customer traffic.
- `docs/legal/`: draft Terms, Privacy, Refund, and Acceptable Use documents for legal review.

## Production notes

- Use `X-API-Key` for tenant auth. The request body tenant field is no longer authoritative.
- Use moderation-scoped keys for content submission and admin-scoped keys for dashboard/policy/key management.
- Default bootstrap keys are defined in `.env.example` for local setup only.
- Set `RTCM_DATABASE_URL` to a PostgreSQL DSN in cloud environments.
- Set `GOOGLE_APPLICATION_CREDENTIALS` to a Google Cloud service-account JSON file to enable real image scanning.
- The inference service is designed so richer multimodal model serving can be added later without changing the main API surface.
- See `docs/integration_guide.md` for text, image, audio, video, Node, Python, and platform integration examples.

## Testing

The suite covers:
- auth and tenant scoping
- text/image/audio/video moderation routes
- audit and review-case persistence
- inference-client integration against the separate inference app
