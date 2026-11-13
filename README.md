# Macherla Guru Creator Services

A separate, private managed YouTube creator service. It is independent of the existing Macherla Guru YouTube AI Manager. Customer workspace owners control their own SEO, private uploads, and explicit publish/schedule actions; the Master Admin manages workspace access and service operations, not individual video approvals.

## Architecture

- **Customer workspace:** email/password account, isolated workspace after team activation, AI SEO editing, private upload, and customer-initiated Publish Now or Schedule.
- **Master admin:** database-verified admin role, customer workspace overview, and server-enforced tenant permissions.
- **Tenant isolation:** PostgreSQL row-level security limits customer reads to tenant memberships. Browser-provided roles and tenant IDs are never trusted.
- **OAuth credentials:** YouTube refresh tokens belong in the non-exposed `private.youtube_connections` schema and must be encrypted by the trusted server before storage.

## Supabase foundation

A dedicated Supabase project named **Macherla Guru Creator Services** has been created in **ap-south-1 (Mumbai)**. It is separate from the existing channel manager's Supabase project.

Migrations are in `supabase/migrations/`:
1. `202611130001_initial_tenant_isolated_schema.sql` — tenant, membership, uploads, metadata, support, audit, billing, private YouTube connection storage, RLS policies and least-privilege grants.
2. `202611130002_create_customer_profile_on_signup.sql` — creates a customer profile on Supabase Auth signup; role is always initialized as customer.

## Current implementation status

- Supabase email/password registration and sign-in are implemented in the Streamlit app.
- Each Streamlit browser session gets its own Supabase client; clients are not shared across customers.
- The signed-in identity is revalidated with Supabase Auth on each rerun.
- The app reads role and tenant membership from RLS-protected database tables. User-editable metadata is not used for authorization.
- New registrations receive the database default `customer` role only. Registration does not create a tenant, membership, or admin permission.
- GitHub Actions CI compiles the app and runs static security-contract tests on pushes and pull requests.
- The admin workspace appears only when the database profile has the trusted `admin` role.
- Customer workspace activation and trusted admin provisioning are handled by the Master Admin approval workflow.
- YouTube OAuth start/callback Edge Functions and encrypted refresh-token storage are deployed. The callback now stores only scopes explicitly returned by Google and refuses to record a connection when upload/read permissions are absent; a real Google test-account connection is still pending.
- Customers can submit support tickets; the Master Admin can view tickets and update their status with an audited admin-only RPC.
- The Master Admin can prepare title, description, tags, hashtags and captions for existing upload jobs through an admin-only audited RPC.
- Customers explicitly initiate Publish Now or Schedule after a private upload exists; the authenticated workspace owner is checked and the action is audited. No separate Master Admin approval is required for an individual video.
- Customer and admin dashboards include upload-queue and billing-status views.
- Customers can submit MP4, MOV, or WebM files up to 100 MB into a private tenant-scoped Supabase Storage bucket. Upload intake is not a YouTube upload.
- The Master Admin can access submitted files through temporary one-hour signed download links; the bucket itself remains private.
- A server-side YouTube upload worker is deployed. The authenticated customer workspace owner claims only their own eligible upload job; the worker decrypts the stored refresh token only inside the Edge Function, uploads with YouTube privacy set to private, and records the returned video ID.
- A separate server-side publish/schedule worker is deployed. It accepts a direct customer-owner action only after a private YouTube video exists, requires the YouTube video-management scope, and can publish immediately or set a future publish time.
- Customers can reconnect to grant the additional video-management permission; Google displays the requested access before consent. The `youtube.force-ssl` scope is broader than upload-only and is required by YouTube's videos.update endpoint.
- Gemini video-file analysis and customer SEO metadata generation are implemented in the deployed `customer-youtube-seo` Edge Function. The function analyzes the uploaded video through Gemini Files API and prepares title options, description, tags, hashtags, captions, keywords, and category. A live Gemini video test is still pending.
- Customer owners can now refresh their own channel overview and recent uploads. The analytics worker stores optional current-vs-previous 15-day YouTube Analytics metrics when the owner grants the read-only YouTube Analytics scope; otherwise public channel/video statistics remain available.
- The upload and publish workers have not yet passed a live Google OAuth/channel test. Payment processing and end-to-end channel tests are not yet complete.

Do not use the app with real customer channels until provisioning, OAuth, upload, publishing approval, audit logging, and live end-to-end security tests are complete. The current CI checks are static guardrails, not a penetration test or live authentication test.

## Local setup

1. Use Python 3.11+ and a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Configure `SUPABASE_URL` and the project's **publishable** API key as `SUPABASE_PUBLISHABLE_KEY`.
5. Run: `streamlit run app.py`.

Never commit `.env`, Google OAuth client secrets, access/refresh tokens, database passwords, Supabase secret/service-role keys, or customer data. The Streamlit customer app must use only the publishable key; privileged keys belong only in a separate trusted backend.

## Protected boundary

Do not modify, import, or deploy code from `opslip-hospital/macherla-guru-ai-agent`. The existing Macherla Guru YouTube AI Manager remains separate and untouched.

## Admin operations and customer-owned publishing

- Master Admin can approve or reject customer access requests and provision isolated workspaces.
- Admin can activate, suspend, or close a workspace through audited database functions.
- Admin can assign a plan code and subscription status for internal billing administration. This is not a payment processor; no card data or automatic charges are collected.
- Admin upload activity is a read-only monitor. Customer workspace owners alone can initiate private uploads and publish/schedule their own videos.
- Database claim functions verify the authenticated caller matches the session and owns the target tenant before returning YouTube credentials to the server-side worker.
- Workspace status and billing changes create audit events.

- Suspended or closed workspaces cannot create new video jobs, write video files to intake storage, generate SEO/content drafts, or claim YouTube upload/publish actions.
- The admin console includes a recent audit-event viewer for workspace, billing, support and customer publishing activity.


## Recent hardening notes

- Public RPC wrappers for customer upload finalization, upload/publish claims, admin workspace/billing updates, customer request approval/rejection, and support ticket status changes are security-definer wrappers with an empty search path. Execution is revoked from anonymous/public roles and granted to authenticated users; the underlying private functions enforce the owner/admin checks.
- Customer analytics claims now require an active tenant for workspace owners; platform admins retain the administrative refresh path.
- Inactive customer workspaces have the channel refresh control disabled in the customer UI.
- These are development changes, not a substitute for the deferred final test pass. Validate migrations, OAuth, tenant isolation, Gemini video analysis, YouTube private upload, publish/schedule, and admin actions before onboarding real customers.
