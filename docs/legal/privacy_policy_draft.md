# Privacy Policy Draft

This draft is a starting point and should be reviewed by qualified legal counsel before public launch.

## Data We Process

Guard API may process:

- Account information such as name, email, workspace name, and billing metadata.
- Submitted content such as text, image metadata, transcripts, and moderation payloads.
- Moderation results, review cases, audit logs, and usage counters.
- Technical data such as IP address, request path, status code, and request ID.

## How We Use Data

Data is used to:

- Provide moderation decisions and dashboard workflows.
- Enforce quotas, rate limits, and billing.
- Debug service reliability issues.
- Improve safety quality when customers explicitly allow it.

## Data Minimization

Production logging should avoid raw customer content. Request logs should include metadata such as request ID, route, status code, and latency.

## Third Parties

Depending on configuration, Guard API may use service providers for hosting, database storage, authentication, billing, image scanning, error monitoring, and email support.

## Retention

Define retention windows for moderation requests, review cases, audit logs, and account data before public launch. Customers should be able to request deletion where applicable.

## Security

Guard API should use HTTPS, secret management, scoped API keys, dashboard authentication, audit logging, rate limits, database backups, and least-privilege access controls.
