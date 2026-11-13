# Final test plan — Macherla Guru Creator Services

**Status:** Not run. Development owner requested that all testing be deferred until the end.

## 1. Automated checks
- In GitHub Actions, open **Creator Services CI** and choose **Run workflow**.
- Confirm Python compilation and all security contract tests pass.
- If a failure appears, fix the code first, then rerun the complete workflow only after the owner approves testing.

## 2. Authentication and workspace isolation
- Create a fresh customer account and confirm it starts as **Pending**.
- Sign in as the platform admin, approve the request, and confirm one isolated workspace is created.
- Sign in as the customer and confirm only their own workspace, uploads, billing status, support tickets, channel data, and metadata are visible.
- Use a second test customer and verify neither customer can read the other's rows, files, videos, or analytics.
- Sign out and sign in as the other customer in the same browser session; confirm no prior customer widget/session state remains.

## 3. YouTube OAuth and analytics
- Use a dedicated test Google/YouTube account, not the production channel.
- Connect the channel and confirm upload, read-only, and force-SSL scopes are granted; analytics comparison is optional if the analytics scope is not granted.
- Refresh the customer channel dashboard and confirm channel title, subscribers (or hidden status), views, video count, and recent uploads.
- Refresh analytics and confirm the snapshot and 15-day-vs-previous-15-day comparison are shown when the analytics scope is available.
- Confirm reconnecting without analytics scope does not invent comparison metrics and the customer sees a separate reconnect action to request the optional analytics scope.

## 4. Video intake and AI SEO
- Upload a valid MP4, MOV, and WebM sample within the 100 MB limit; verify unsupported/mismatched file content is rejected.
- Verify the private intake bucket remains private and each file path is bound to that customer's draft upload job.
- Confirm SEO generation is blocked with a clear message until the customer's own YouTube channel is connected. After connecting, generate SEO and confirm five unique title options, 12–18 unique tags within the 450-character limit including separators, exactly five unique hashtags including the connected channel's brand hashtag (for the Macherla Guru channel, **#MacherlaGuru**), description, captions, keywords, and category.
- Edit and save metadata; verify invalid tag counts, duplicate hashtags, missing title options, and excessive keywords are rejected.
- Confirm SEO becomes read-only after the YouTube private upload.
- Use Gemini Content Studio to create a script, idea, Shorts draft, and caption; confirm the output uses the connected channel name and selected language without forcing a fixed character or channel style.
- Confirm the customer upload/SEO/publish workflow contains no thumbnail prompt, thumbnail generation, or thumbnail upload controls.

## 5. YouTube upload and publishing
- On the dedicated test channel, upload the sample video and verify YouTube receives the title, description, tags, category, and exactly five saved hashtags in the description, including that test channel's own brand hashtag (not a hardcoded MacherlaGuru hashtag).
- Confirm the video is **Private** immediately after upload.
- Verify **Publish now** changes the test video to Public only after the customer clicks the explicit action.
- Verify **Schedule** uses IST date and 12-hour AM/PM display, rejects times less than 15 minutes ahead, and appears correctly in YouTube Studio.
- Simulate or inspect ambiguous network outcomes only in a controlled test environment; confirm unknown upload/publish states are locked against blind retries and provide a YouTube Studio check path.

## 6. Admin, support, billing, and audit
- Verify admin can approve/reject customer access, activate/suspend/close workspaces, update plan/status tracking, manage support-ticket status, and inspect audit events.
- Verify the admin upload monitor is read-only and does not approve, publish, or schedule customer videos.
- Confirm billing is status tracking only: no card collection, payment processing, or automatic charges.

## 7. Security and release gate
- Confirm anonymous public-table/RPC access remains revoked and public tables have RLS enabled.
- Confirm service-role credentials never appear in Streamlit code or browser responses.
- Enable Supabase Auth **Leaked Password Protection** in the project Authentication password/security settings before real customer onboarding.
- Confirm Google OAuth test users and redirect URI are configured for the test account. Before real customer onboarding, move the consent screen from Testing to In production and complete Google's verification for required YouTube scopes; external Testing mode is limited to 100 test users and refresh tokens for YouTube scopes expire after 7 days.
- Do not onboard real customers until OAuth, Gemini video analysis, private upload, Publish now, Schedule, analytics, tenant isolation, and admin workflows pass.
- Keep the existing **Macherla Guru YouTube AI Manager** untouched throughout all tests.
