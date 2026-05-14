# Operations Runbook

Use this before accepting paid production traffic.

## Monitoring

- Uptime checks:
  - `GET /health` every 60 seconds for process liveness.
  - `GET /ready` every 60 seconds for dependency readiness.
- Alert if `/health` fails twice in a row.
- Alert if `/ready` fails once after production traffic is routed.
- Track p50, p95, and p99 latency for `/moderate/text`, `/moderate/image`, `/billing/*`, and `/dashboard`.

## Error Monitoring

- Add a backend error tracker such as Sentry, Honeybadger, or the hosting provider equivalent.
- Add frontend runtime error tracking for the Vite app.
- Include `X-Request-ID`, route, status code, tenant slug, and latency.
- Do not send raw customer content to external monitoring tools.

## Logs

- Keep structured application logs for at least 30 days.
- Retain security and billing audit logs for at least 12 months.
- Redact API keys, Clerk tokens, Stripe secrets, Google credentials, and raw media payloads.
- Use `X-Request-ID` to connect customer support reports to API logs.

## Database Backups

- Use managed PostgreSQL with daily automated backups.
- Keep at least 7 daily backups and 4 weekly backups.
- Run a restore test before paid launch and once per quarter.
- Document the restore target, duration, and data loss window.

## Release Checks

Run before each production deploy:

```powershell
.\.venv\Scripts\python.exe -m pytest
Push-Location frontend
npm run build
Pop-Location
alembic upgrade head
```

After deploy:

```powershell
Invoke-WebRequest https://api.your-domain.example/health
Invoke-WebRequest https://api.your-domain.example/ready
```

## Incident Severity

- SEV1: API unavailable, billing broken, data exposure, or auth bypass.
- SEV2: moderation degraded, inference unavailable, dashboard unavailable, or credit quota incorrectly blocks customers.
- SEV3: non-critical UI bug, delayed webhook processing, or documentation issue.

## Incident Flow

1. Acknowledge the alert.
2. Assign one owner.
3. Preserve logs and deployment metadata.
4. Roll back if the latest deploy caused the incident.
5. Post customer status if paid users are affected.
6. Write a short postmortem with cause, impact, fix, and prevention.
