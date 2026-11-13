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
- GitHub Actions CI is manual-only during development; compilation and static security-contract tests are reserved for the owner-authorized final test pass.
- The admin workspace appears only when the database profile has the trusted `admin` role.
- Customer workspace activation and trusted admin provisioning are handled by the Master Admin approval workflow.
- YouTube OAuth start/callback Edge Functions and encrypted refresh-token storage are deployed. The callback now stores only scopes explicitly returned by Google and refuses to record a connection unless upload, read-only, and publishing permissions are present; Analytics read-only is optional. The customer UI displays actionable OAuth completion messages. A real Google test-account connection is still pending.
- Customers can submit support tickets; the Master Admin can view tickets and update their status with an audited admin-only RPC.
- Customer workspace owners generate, edit and save their own video's SEO metadata through the Gemini-backed customer workflow. The Master Admin does not approve or edit individual customer videos.
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
- The Supabase Security Advisor no longer reports exposed SECURITY DEFINER RPC wrappers after the invoker-wrapper refactor. Three INFO findings remain for RLS-enabled tables in the non-exposed private schema with no policies (YouTube connections, OAuth states, and AI rate-limit records); this is intentional default-deny defense in depth because access is mediated through narrowly granted, ownership-checked private functions.
- The final automated and live end-to-end test pass remains intentionally deferred until all development work is complete and the owner authorizes testing.
- The channel-connection listing RPC was checked against the private-schema function lockdown. Its guarded helper has the narrowly scoped authenticated EXECUTE grant required by the public invoker wrapper; it returns only channel ID/title, connection time, and scopes, never OAuth tokens. The live privilege check confirmed authenticated access and no anonymous access.
- Nine customer/admin public RPC wrappers were converted from SECURITY DEFINER to SECURITY INVOKER. The underlying private functions retain the authorization checks and are granted only to authenticated callers where required. A live catalog check confirmed all nine wrappers are invoker functions and none is executable by anonymous callers.
- The customer channel-dashboard refresh Edge Function now checks that the workspace is active on the server before accessing stored YouTube credentials or refreshing channel data; the updated function is deployed as version 5.
- The obsolete separate `customer_approve_upload` RPC has been retired from client execution. The current customer flow uses the Publish now / Schedule action as the explicit consent step; a live privilege query confirmed anonymous and authenticated execution are both revoked for the legacy approval RPC.
- Upload/publish workers return a distinct status-sync warning if YouTube accepted an action but the dashboard update failed. The customer UI now surfaces the YouTube video link and warns against retrying blindly, reducing duplicate-upload or unintended-repeat-action risk.
- Gemini SEO prompts now keep hashtags separate from the description, and the private-upload worker appends only hashtags missing from the edited description while reserving space under YouTube's 5,000-character description limit.
- Storage intake inserts are now bound to a real draft upload job: the path must contain exactly tenant/job/file segments, the tenant must be active and owned by the caller, and the job's stored filename must match. This prevents customers from filling the private bucket with arbitrary orphaned objects.
- Sign-out and expired-session handling now schedule a full Streamlit session-state clear at the beginning of the next run, before widgets are recreated. This prevents password fields, form inputs, AI drafts, and prior customer widget values from carrying into another login in the same browser session.
- AI SEO now incorporates the connected channel's stored title as a branding hint when one is available, while retaining a safe generic fallback when the customer has not connected a channel yet.
- Customer SEO and channel-dashboard Edge Functions no longer query the non-exposed `private` schema through PostgREST. They use guarded public RPCs: channel metadata listing for SEO and the server-only analytics claim RPC for the encrypted credential needed by the channel refresh worker.
- The final database hardening migrations are ordered after the schema, workflow, storage, and worker migrations so a clean project replay creates the target functions/tables/policies before applying global grants, function lockdown, indexes, and the final storage policy.

### Current deployed Edge Function versions (13 Nov 2026)

- `youtube-oauth-start`: v11 ACTIVE
- `youtube-oauth-callback`: v11 ACTIVE
- `youtube-upload-private`: v23 ACTIVE
- `youtube-publish-approved`: v9 ACTIVE
- `youtube-refresh-analytics`: v7 ACTIVE
- `customer-youtube-seo`: v50 ACTIVE
- `customer-channel-dashboard`: v5 ACTIVE
- `customer-content-studio`: v11 ACTIVE

These are deployment-state checks only, not successful end-to-end tests. The live database migration history and current schema were reviewed; the required storage-binding, analytics/SEO columns, upload status constraint, and final SEO upload guard are present. Idempotent final migrations are committed for clean setup. The final test run remains deferred by request.
- The scheduling date picker uses the India local calendar date, and schedule times are displayed and submitted in 12-hour AM/PM IST. The backend rejects schedule times that are not at least 15 minutes in the future.
- The Streamlit app accepts the preferred `SUPABASE_PUBLISHABLE_KEY` secret and falls back to the legacy `SUPABASE_ANON_KEY` name for existing deployments; neither key is privileged.
- A clean-replay reconciliation migration adds the analytics/SEO JSON fields idempotently. A final post-workflow migration reapplies the `upload_jobs_status_check` constraint with all live states, including `upload_unknown`, so earlier workflow migrations cannot accidentally remove the ambiguous-upload recovery state during a fresh database setup.
- SEO generation and editing are restricted to jobs still in the secure `received` state, before the YouTube private upload. Once uploaded, the saved title/description/tags/hashtags are displayed read-only so the dashboard cannot imply that later edits were synchronized to YouTube.
- The private upload worker records `upload_unknown` if the upload result becomes uncertain after the binary request begins, including interrupted responses or a successful response without a usable video ID. That state is excluded from normal upload claims, and both customer and admin views tell operators to check YouTube Studio before retrying.
- The publish worker distinguishes a definite YouTube rejection from a request that times out before a response. If the outcome is unknown, the job remains held in `publishing` rather than being reset to `uploaded_private`, preventing an unsafe repeat Publish/Schedule action. The customer UI displays a check-YouTube-Studio/support warning. The publish Edge Function is deployed ACTIVE (version 9).
- The customer upload panel now explicitly handles unresolved `upload_unknown` and `publishing` states. It tells customers to check YouTube Studio and prevents blind retries while the dashboard cannot confirm whether YouTube accepted the action.
- The admin read-only upload monitor now labels `upload_unknown` as `Check YouTube — do not retry`, matching the customer warning. Current live deployment inventory was refreshed from Supabase: OAuth start/callback v11, private upload v23, publish v9, analytics v7, customer SEO v50, channel dashboard v5, and content studio v11 are all ACTIVE.
- Current SEO generation and private upload code also validate the actual video container signature (MP4/MOV `ftyp`, WebM EBML header), enforce one connected-channel brand hashtag within exactly five unique hashtags, and prevent ambiguous YouTube upload results from being retried automatically. Safe pre-transfer failures return to the `received` state for retry; uncertain transfer outcomes remain locked as `upload_unknown`.
- The publish worker treats an interrupted request or YouTube 5xx response as an ambiguous outcome and leaves the job in a non-retryable `publishing` state until YouTube Studio is checked. Clear 4xx rejection and pre-request failures remain safely retryable from PRIVATE.
- The database upload-claim function independently enforces completed SEO before it will claim a private YouTube upload: 12–18 unique tags within 450 characters, exactly five unique hashtags including the connected channel's brand hashtag, and five distinct title options. This prevents bypassing the dashboard's SEO-first workflow by calling the RPC directly.
- Publish requests with no response from YouTube are now held in the `publishing` state instead of being reset to private, so the UI cannot accidentally repeat a possibly accepted schedule/publish action.
- Latest final hardening clarifies that any interrupted upload transfer is an unknown outcome, not a confirmed failure. The upload job stays locked as `upload_unknown`; a pre-transfer failure returns it to `received` for safe retry. The upload worker is ACTIVE v23. The SEO worker is deployed ACTIVE v44. The publish worker is deployed ACTIVE v9. The analytics worker is ACTIVE v7. The admin upload monitor explicitly flags unknown uploads as do-not-retry.
- YouTube tag-length validation now counts comma separators and enforces a 450-character cap consistently in Gemini SEO generation, customer-edited metadata, and the final private-upload worker.
- The admin's read-only upload monitor flags both uncertain private uploads and publish/schedule requests still in progress as `Check YouTube — do not retry`; the admin can inspect the record without taking over the customer's publishing decision.
- Streamlit's per-widget `max_upload_size` option requires a newer Streamlit release; the app dependency is now `streamlit>=1.53` and project config sets the global upload cap to 100 MB, matching the private storage bucket and database limits.
- A final ordered migration `20261113292000_finalize_complete_seo_upload_guard.sql` now reapplies the complete SEO validation inside the upload-claim transaction after all workflow migrations. This ensures a fresh database replay cannot overwrite the requirement for 12–18 unique tags, five unique hashtags including the connected channel's brand hashtag, and five unique title options. It is applied to the live Supabase project and committed in the repository.
- SEO tag-length validation now counts the comma separators included in YouTube's tag string, not just the characters inside each tag. Both the customer SEO save endpoint and the database upload-claim guard use the same 450-character budget; SEO Edge Function is deployed ACTIVE (version 44).
- The final private-upload database claim now enforces the complete metadata contract server-side: 12–18 unique tags within 450 characters (including separators), exactly five unique hashtags including the connected channel's brand hashtag, five unique title options, a valid title/description length, and no more than 20 keywords. This guard is mirrored in the committed final migration so clean database setup retains the same rule.
- GitHub Actions CI is intentionally manual-only while development continues, honoring the owner's instruction to run tests once at the end. The final workflow can be started with GitHub Actions → Creator Services CI → Run workflow after the owner authorizes final testing.

- SEO hashtag normalization caps each saved hashtag at 100 characters before the five-tag set is appended to the 5,000-character YouTube description limit.
- Gemini SEO generation now rejects more than 20 keywords before saving, matching the database upload gate and the customer editor's validation contract.
- A single uniquely versioned final migration now runs after all earlier upload/workflow migrations and enforces the complete SEO contract, including comma separators in the 450-character tag budget, exactly five unique hashtags with the connected channel's brand hashtag, five title options, description length, and the 20-keyword maximum. Duplicate migration-version filenames were removed so clean replay has an unambiguous order. The migration is applied to the live database.
- Both video-processing workers now keep the downloaded file as a Blob and read only the first 12 bytes for container validation. Gemini and YouTube receive the Blob directly, avoiding an additional full-size 100 MB Uint8Array copy inside the Edge Function memory budget. Both functions are deployed ACTIVE: customer SEO v50 and private upload v23.
- The complete owner-approved final test checklist is in [`FINAL_TEST_PLAN.md`](FINAL_TEST_PLAN.md). The final test pass is intentionally deferred; an earlier interim CI run exposed two issues that have since been addressed, but no rerun or live end-to-end tests should be started until the owner authorizes the final test pass.
- Production launch requires Google OAuth consent-screen publishing and verification for the requested YouTube scopes. Keep Testing mode for test accounts only: external Testing mode is limited to 100 test users and YouTube-scope refresh tokens expire after 7 days. Full steps and official references are in `DEPLOYMENT.md`.


### Channel-specific hashtag rule (13 Nov 2026)

- Exactly one of the five generated hashtags is the connected customer's own channel brand. It is derived from that workspace's connected YouTube channel title after Unicode normalization and punctuation/space removal; it is never hardcoded to #MacherlaGuru for every customer.
- The remaining four hashtags are topic-relevant and unique. The customer SEO Edge Function requires a connected channel identity before generating SEO, and the database upload-claim guard independently checks that the saved five-hashtag set includes the matching connected-channel brand.
- The rule is deployed in customer-youtube-seo v50 and mirrored in the applied migration 20261113293000_validate_connected_channel_brand_hashtag.sql. The prior hardcoded MacherlaGuru-only upload requirement has been retired.
- Final automated and live end-to-end testing remains intentionally not run until the owner authorizes the final test pass. OAuth consent-screen production verification and Supabase Auth leaked-password protection remain pre-launch requirements.
- SEO reserves one of its five hashtags for the connected YouTube channel's normalized brand name. For the Macherla Guru channel this is `#MacherlaGuru`; customer channels receive their own channel-brand hashtag. The database upload-claim function independently verifies the brand hashtag against the connected channel title.
- Fixed the Unicode normalization regex used to derive each connected channel's brand hashtag. The SEO worker is deployed ACTIVE v44; the corresponding static contract check is included in the final test suite.
- Gemini Content Studio now reads the connected channel title directly through the authenticated tenant-scoped connection RPC, so its prompts use the correct channel brand even before an analytics snapshot has been refreshed. The Content Studio Edge Function is deployed ACTIVE v11.
- Gemini SEO generation now requires an active connected YouTube upload-scope connection before it analyzes the video. This ensures the five-hashtag set includes the correct connected-channel brand; if the customer uploads before connecting, the video remains safely stored and the UI asks them to connect before retrying SEO.
- Gemini video SEO requires explicit per-video consent and records a consent audit event before the uploaded video is sent to the Gemini API. The UI discloses that the current Gemini API Free Tier may use submitted content to improve Google products.
- Gemini Content Studio and Growth Doctor require separate explicit consent before sending customer prompts or channel metrics to Gemini; consent is audited. AI requests are rate-limited per customer/workspace and the rate-limit RPC is callable only by the service role through a public-schema wrapper.
- Customer Content Studio is channel-neutral: it uses the authenticated tenant's connected channel title directly and does not force PJ Babu or another fixed character. The customer upload workflow remains thumbnail-free.
- Macherla Guru's channel title is canonicalized to the exact `#MacherlaGuru` casing even when the YouTube channel title is uppercase or contains decorative characters. The database mirrors the same rule in migration `20261113294000_canonicalize_macherla_guru_brand_hashtag.sql`.
- Production Google OAuth has an additional external launch dependency: a custom domain owned by the service operator, a public homepage with privacy-policy/terms links on that verified domain, and Google's domain/brand/sensitive-scope verification. The shared `streamlit.app` hostname should not be treated as an owned domain. See `DEPLOYMENT.md` before inviting real customers.
- Before any video is sent to Gemini, the customer must explicitly consent per video. The UI discloses that the current Gemini API Free Tier may use submitted content to improve Google products, and the consent is written to the tenant audit log. Paid Tier data-use terms differ; review `DEPLOYMENT.md` before changing tiers.
- Draft public-facing policies are in `PRIVACY_POLICY_DRAFT.md` and `TERMS_OF_SERVICE_DRAFT.md`. They contain owner/legal-review placeholders and must not be published unchanged. Fill the operator identity, public support contact, jurisdiction, retention/deletion process, and legal terms before placing them on the verified custom domain.
- The SEO worker is deployed ACTIVE v47. AI video analysis now requires explicit per-video consent, logs the consent event before sending the file to Gemini, and keeps the Free Tier data-use disclosure visible in the customer upload flow.
- Gemini generation is rate-limited per customer workspace: up to 5 video-SEO generations and 12 Content Studio generations per hour. The counters live in a private RLS-enabled table; only the server-side service role can invoke the guarded rate-limit function. The customer UI reports when the hourly limit resets.
- The same Gemini Free Tier disclosure and separate consent gate also cover Content Studio prompts/instructions and Growth Doctor channel metrics. Those requests are not sent to Gemini until the customer checks the corresponding consent box; the consent events are recorded in the audit log.
