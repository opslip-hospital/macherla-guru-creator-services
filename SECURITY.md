# Security rules

## Non-negotiable controls

- Never ask customers for Google passwords. Use Google's OAuth consent flow.
- Never store OAuth secrets, access tokens, or refresh tokens in Git or browser storage.
- Encrypt refresh tokens at rest using a managed secret/KMS facility.
- Verify identity tokens/JWT signatures server-side; never trust client-provided role or tenant IDs.
- Enforce tenant ownership in every database query and with database row-level security.
- Admin permissions must be checked server-side and audited.
- Upload videos as private by default. Publishing or scheduling requires an explicit customer approval event.
- Keep an immutable audit trail for OAuth connection changes, uploads, approvals, publish actions, and admin access.
- Use least-privilege OAuth scopes and request additional scopes only when needed.
- Apply rate limits, CSRF protection where applicable, secure cookies, HTTPS, and secret rotation.
- Do not upload real customer data until isolation and authorization tests pass.

## Current limitation

The repository currently contains only a locked foundation UI. It does not yet authenticate users, connect Google accounts, upload videos, or store customer data. Do not deploy it as a functioning customer service until those controls are implemented and tested.
