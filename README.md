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
- YouTube OAuth start/callback Edge Functions and encrypted refresh-token storage are deployed. The callback now stores only scopes explicitly returned by Google and refuses to record a connection unless upload, read-only, and publishing permissions are present; Analytics read-only is optional. The customer UI displays actionable OAuth completion messages. A real Google test-account connection is still pending.
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

- Public RPC wrappers for customer upload finalization, upload/publish claims, admin workspace/billing updates, customer request approval/rejection, and support ticket status changes execute as invokers. Their privileged callees live in the non-exposed private schema as SECURITY DEFINER functions with empty search paths and explicit auth.uid()/tenant-owner/admin checks. Anonymous/public execution is revoked; authenticated execution is narrowly granted only where required.
- Customer analytics claims now require an active tenant for workspace owners; platform admins retain the administrative refresh path.
- Inactive customer workspaces have the channel refresh control disabled in the customer UI.
- These are development changes, not a substitute for the deferred final test pass. Validate migrations, OAuth, tenant isolation, Gemini video analysis, YouTube private upload, publish/schedule, and admin actions before onboarding real customers.


- Customer SEO bearer-token parsing was corrected so authenticated customer requests are recognized by the SEO Edge Function.
- Generated SEO output is checked before saving: 12–18 YouTube tags within the character budget, exactly five unique hashtags, and five title options. Invalid/incomplete AI output is rejected for retry rather than silently saved.


- Registration lifecycle was checked against the live database: the auth-user trigger creates a customer profile and a pending customer request; customer/admin row-level security policies protect the request and workspace data.
- All core customer/admin data tables inspected have row-level security enabled.
- SEO normalization now removes duplicate tags, hashtags, title options, and keywords; generated output must contain five distinct title options and five distinct hashtags.

## Latest development hardening (13 Nov 2026)

- Anonymous callers have no table or sequence privileges in the public schema, and the live grant check returned zero anonymous public-table grants.
- Authenticated clients have read-only table grants plus the support-ticket insert permission; customer writes to workflow data are performed by owner/admin-checked database functions and trusted Edge Functions.
- Internal functions in the non-exposed `private` schema have default execution revoked from `PUBLIC`, `anon`, and `authenticated`. A narrow authenticated allowlist covers only the RLS helpers and guarded workflow functions required by invoker RPC wrappers; each privileged function validates the authenticated user and role/tenant ownership. Service-role backend workers retain internal execution.
- Public RPC wrappers are callable by authenticated users only (not anonymous callers). Their underlying functions enforce the platform-admin or active tenant-owner checks and write audit events.
- Foreign-key indexes flagged by Supabase's performance advisor were added for OAuth state ownership, analytics connection references, and customer request reviewers. The live database check confirmed all four indexes.
- Private video intake bucket configuration was confirmed: non-public, 100 MB maximum, and MP4/MOV/WebM MIME restrictions. Storage policies scope customer upload/read access to tenant ownership.
- Private upload and publish workers now preserve the YouTube video ID/state if YouTube accepted an action but the subsequent dashboard database update fails. This reduces the risk of duplicate uploads or unsafe retries.
- OAuth start/callback and upload/publish workers were redeployed after the latest backend changes. Their deployment status is active; this does not replace a real customer OAuth/upload/publish test.
- Supabase Security Advisor still reports leaked-password protection disabled. This project Auth setting must be enabled in Supabase Dashboard under Authentication password/security settings before real customer onboarding. It was not changed automatically here.
- The Supabase Security Advisor no longer reports exposed SECURITY DEFINER RPC wrappers after the invoker-wrapper refactor. Two INFO findings remain for RLS-enabled tables in the non-exposed private schema with no policies; this is intentional default-deny defense in depth because access is mediated through narrowly granted, ownership-checked private functions.
- The final automated and live end-to-end test pass remains intentionally deferred until all development work is complete and the owner authorizes testing.
- The channel-connection listing RPC was checked against the private-schema function lockdown. Its guarded helper has the narrowly scoped authenticated EXECUTE grant required by the public invoker wrapper; it returns only channel ID/title, connection time, and scopes, never OAuth tokens. The live privilege check confirmed authenticated access and no anonymous access.
- Nine customer/admin public RPC wrappers were converted from SECURITY DEFINER to SECURITY INVOKER. The underlying private functions retain the authorization checks and are granted only to authenticated callers where required. A live catalog check confirmed all nine wrappers are invoker functions and none is executable by anonymous callers.
- The customer channel-dashboard refresh Edge Function now checks that the workspace is active on the server before accessing stored YouTube credentials or refreshing channel data; the updated function is deployed as version 4.
- The obsolete separate `customer_approve_upload` RPC has been retired from client execution. The current customer flow uses the Publish now / Schedule action as the explicit consent step; a live privilege query confirmed anonymous and authenticated execution are both revoked for the legacy approval RPC.
- Upload/publish workers return a distinct status-sync warning if YouTube accepted an action but the dashboard update failed. The customer UI now surfaces the YouTube video link and warns against retrying blindly, reducing duplicate-upload or unintended-repeat-action risk.
- Gemini SEO prompts now keep hashtags separate from the description, and the private-upload worker appends only hashtags missing from the edited description while reserving space under YouTube's 5,000-character description limit.
- Storage intake inserts are now bound to a real draft upload job: the path must contain exactly tenant/job/file segments, the tenant must be active and owned by the caller, and the job's stored filename must match. This prevents customers from filling the private bucket with arbitrary orphaned objects.
- Sign-out and expired-session handling now schedule a full Streamlit session-state clear at the beginning of the next run, before widgets are recreated. This prevents password fields, form inputs, AI drafts, and prior customer widget values from carrying into another login in the same browser session.
- AI SEO now incorporates the connected channel's stored title as a branding hint when one is available, while retaining a safe generic fallback when the customer has not connected a channel yet.
- Customer SEO and channel-dashboard Edge Functions no longer query the non-exposed `private` schema through PostgREST. They use guarded public RPCs: channel metadata listing for SEO and the server-only analytics claim RPC for the encrypted credential needed by the channel refresh worker.
- The final database hardening migrations are ordered after the schema, workflow, storage, and worker migrations so a clean project replay creates the target functions/tables/policies before applying global grants, function lockdown, indexes, and the final storage policy.
- Customer-edited SEO is validated server-side before saving: 12–18 unique tags within 450 characters, exactly five unique hashtags, five unique title options, and at most 20 SEO keywords. The SEO worker prompt keeps hashtags separate from the description; the private upload worker appends missing hashtags once while respecting YouTube's 5,000-character description limit. The updated SEO Edge Function is deployed ACTIVE (version 26).
- AI SEO now requires the brand hashtag `MacherlaGuru` within the exact five unique generated hashtags. The private upload worker strips stray hashtags from the description and appends the saved AI hashtag list once, keeping the full description within YouTube's 5,000-character limit. YouTube tags are capped using the combined tag text plus separator characters. The updated SEO and private-upload Edge Functions are deployed ACTIVE as versions 28 and 14 respectively.
