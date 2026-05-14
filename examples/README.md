# Guard API Customer Integration Examples

These examples show the small backend integration a customer adds to their own app.

Set these environment variables before running examples:

```bash
GUARD_API_URL=https://api.your-domain.example
GUARD_API_KEY=rtcm_customer_moderation_key
```

For local development against this repo:

```bash
GUARD_API_URL=http://127.0.0.1:8100
GUARD_API_KEY=rtcm_market_live_key
```

## What The Customer Code Must Do

1. Receive user content in the customer's backend.
2. Send that content to Guard API.
3. Read `decision.action`.
4. Apply product behavior:
   - `allow`: publish or deliver.
   - `review`: hold and show pending/review state.
   - `block`: reject, hide, or delete before users see it.

## Node

Files:

- `node/guard-api-client.mjs`: reusable Guard API client.
- `node/express-moderation-server.mjs`: Express example with text, image, and audio routes.

Run:

```bash
cd examples/node
npm install express multer dotenv
node express-moderation-server.mjs
```

## Python

Files:

- `python/guard_api_client.py`: reusable Guard API client.
- `python/fastapi_moderation_server.py`: FastAPI example with text, image, and audio routes.

Run:

```bash
cd examples/python
pip install fastapi uvicorn requests python-multipart
uvicorn fastapi_moderation_server:app --reload --port 9000
```

