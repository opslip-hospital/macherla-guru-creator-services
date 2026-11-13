# Security rules

## Non-negotiable controls

- Never ask customers for Google passwords. Use Google's OAuth consent flow.
- Never store OAuth secrets, access tokens, or refresh tokens in Git or browser storage.
- Encrypt refresh tokens at rest with AES-256-GCM using a dedicated 32-byte Edge Function secret; never expose the key or encrypted token to customers.
- OAuth state is random, stored as a SHA-256 hash, short-lived, and consumed once; the callback validates the active tenant owner before storing a connection.
- Verify identity tokens/JWT signatures server-side; never trust client-provided role or tenant IDs.
- Enforce tenant ownership in every database query and with database row-level security.
- Admin permissions must be checked server-side and audited.
- Upload videos as private by default. Publishing or scheduling requires an explicit customer approval event.
- Keep an immutable audit trail for OAuth connection changes, uploads, approvals, publish actions, and admin access.
- Use least-privilege OAuth scopes and request additional scopes only when needed.
- Apply rate limits, CSRF protection where applicable, secure cookies, HTTPS, and secret rotation.
- Do not upload real customer data until isolation and authorization tests pass.

## Current implementation status

Supabase Auth, tenant-scoped customer workspaces, admin customer approval, Google OAuth start/callback Edge Functions, private refresh-token storage, and safe channel-status reads are implemented. Google OAuth is not live until the required Edge Function secrets are configured and a test channel connection succeeds. Video upload, publish approval, scheduling, SEO, billing, and support workflows remain pending.
