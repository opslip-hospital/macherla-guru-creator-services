# Deployment — Macherla Guru Creator Services

This deployment is for the separate `macherla-guru-creator-services` repository only.

## Recommended first host: Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud with the GitHub account that can access this private repository.
2. Create a new app and select:
   - Repository: `opslip-hospital/macherla-guru-creator-services`
   - Branch: `main`
   - Main file path: `app.py`
3. In the app's **Advanced settings / Secrets** area, add the following values from the dedicated **Macherla Guru Creator Services** Supabase project:
   ```toml
   SUPABASE_URL = "https://gigthhrovhktrpghpnya.supabase.co"
   SUPABASE_PUBLISHABLE_KEY = "YOUR_SUPABASE_PUBLISHABLE_KEY"
   APP_NAME = "Macherla Guru Creator Services"
   ```
4. Save and deploy. Wait for the app health check to complete.
5. Open the app URL and verify that the sign-in and customer registration screens load. Do not create a real customer account until the live authentication test and admin provisioning plan are ready.

## Secret-handling rules

- Use only the Supabase **publishable** key in this Streamlit app.
- Never add a Supabase secret/service-role key, database password, Google OAuth client secret, or YouTube token to Streamlit secrets for this customer-facing app.
- Never commit secrets to GitHub or put them in source code.
- Do not connect this app to the existing Macherla Guru YouTube AI Manager repository or its Supabase project.

## Google YouTube OAuth setup

The repository contains the customer OAuth and YouTube worker Edge Functions deployed in the dedicated Creator Services Supabase project:

- Start: `https://gigthhrovhktrpghpnya.supabase.co/functions/v1/youtube-oauth-start`
- Callback: `https://gigthhrovhktrpghpnya.supabase.co/functions/v1/youtube-oauth-callback`

In Google Cloud Console:

1. Create/select a project and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen. While testing, keep it in Testing and add only approved test Google accounts.
3. Create an OAuth client ID of type **Web application**.
4. Add this exact Authorized redirect URI:
   `https://gigthhrovhktrpghpnya.supabase.co/functions/v1/youtube-oauth-callback`
5. Do not add a client secret to GitHub or Streamlit app secrets.

In the Supabase project's **Edge Functions > Secrets**, set:

- `GOOGLE_CLIENT_ID` — OAuth web client ID
- `GOOGLE_CLIENT_SECRET` — OAuth web client secret
- `GOOGLE_REDIRECT_URI` — the exact callback URI above
- `APP_BASE_URL` — the exact deployed Streamlit Creator Services URL, including https
- `TOKEN_ENCRYPTION_KEY` — base64 encoding of 32 random bytes (generate locally with `openssl rand -base64 32`; never send it in chat)

The project-provided Supabase URL and server credentials are read inside Edge Functions. Never copy the service-role/secret key into Streamlit or GitHub. The Streamlit app uses only the publishable key.

## AI YouTube SEO generation

The customer dashboard lets a workspace owner upload one video and prepare SEO before connecting YouTube. It creates five title options, an SEO description, 12–18 search tags, exactly five separate hashtags, YouTube and Instagram captions, keywords, and a YouTube category; the customer can edit and save the result. Before a channel is connected, the workspace/business name supplies the brand hashtag. After connecting, the customer regenerates SEO so the brand hashtag matches the connected channel.

In the dedicated Supabase project's **Edge Functions > Secrets**, add:

- `GEMINI_API_KEY` — a Google AI Studio / Gemini API key for the Creator Services project.

Keep this key only in Supabase Edge Function secrets. Do not add it to Streamlit secrets, GitHub, or chat. The Edge Function calls Gemini server-side and checks that the signed-in user owns the video's workspace before generating or saving metadata. It uses the Gemini `generateContent` REST endpoint and structured JSON output. Video analysis is blocked until the customer checks the per-video consent box; the service records the consent event before transmitting the video. The UI discloses that the current Gemini API Free Tier may use submitted content to improve Google products. Text prompts and Growth Doctor metrics also require explicit consent before being sent to Gemini. Requests are rate-limited per customer/workspace.

## Customer self-service publishing

After SEO is saved and a YouTube channel is connected with upload permission, customers can upload their video to that channel as **PRIVATE**. The customer-facing dashboard then offers **Schedule** only, using an IST date and AM/PM time. It does not expose Publish Now. Google OAuth publishing permission is required for scheduling; customers must reconnect if the required scope was not granted.

The OAuth flow requests `youtube.upload`, `youtube.readonly`, and `youtube.force-ssl`; the last permission is needed to publish or schedule a video after the customer chooses that action. A short-lived, one-use state is stored as a hash. The refresh token is encrypted with AES-256-GCM before it is stored in the private schema. Only the channel identity and granted scopes are returned to the customer UI.

## Current limitations

The application, database workflows, and Edge Functions are deployed. Deployment status alone does not prove that Google OAuth, Gemini video analysis, or YouTube publishing works end to end. Confirm that the listed OAuth, encryption, and Gemini secrets are present in the dedicated Supabase project's Edge Function Secrets without copying their values into chat or GitHub. A real test Google account must connect a channel before live OAuth is considered verified. Gemini video SEO, private upload, Schedule, and admin/customer flows remain pending the final authorized test pass. Supabase Auth leaked-password protection is currently reported disabled by Security Advisor; enable it in the project's Authentication password/security settings before onboarding real customers. Billing is administrative status tracking only; payment processing and automatic charges are not enabled.
## Streamlit upload configuration

The app requires Streamlit 1.53 or newer for the per-widget `max_upload_size` setting. The repository pins `streamlit>=1.53,<2.0` and includes `.streamlit/config.toml` with a 200 MB global upload cap. Keep this aligned with the private Supabase bucket and database upload limit.
## Google OAuth production readiness

The Google OAuth consent screen must not remain in **Testing** for real customer use. Google's official OAuth documentation states that external apps in Testing are limited to 100 test users and refresh tokens expire after 7 days when non-basic scopes such as YouTube scopes are requested. Before onboarding real customers, switch the consent screen to **In production** and complete Google's verification process for any sensitive/restricted scopes required by the YouTube integration. Keep a test account in the test-user list while developing. See Google's [OAuth 2.0 refresh-token expiration guidance](https://developers.google.com/identity/protocols/oauth2#expiration) and [OAuth verification policies](https://developers.google.com/identity/protocols/oauth2/policies).
## Required public domain and OAuth verification materials

The current Streamlit URL is a shared `streamlit.app` subdomain. Google requires production OAuth home-page, privacy-policy, terms, redirect, and JavaScript-origin domains to be domains the app owner can verify and control. Do not assume the shared Streamlit subdomain can pass this ownership check. Before requesting production verification, provide a custom domain you own and configure it for the public app/home page. The public home page must describe Creator Services (not be only a login screen) and link to a privacy policy and terms of service hosted on the same verified domain. The repository now includes public Streamlit pages at `pages/Privacy_Policy.py` and `pages/Terms_of_Service.py`, linked from the app home page. They are operator-review drafts, not legal approval; confirm the operator identity, support contact, governing law, data-retention and deletion process, and actual provider settings before publishing them on the verified domain. The privacy policy must accurately explain YouTube/Google data access, use, storage, sharing, refresh-token handling, Gemini video analysis, and the Limited Use commitments. Keep a valid support contact on the OAuth consent screen. Google may request a scope-justification and demonstration video for sensitive-scope review. See Google's [domain and homepage requirements](https://developers.google.com/identity/verification/authentication-policy-compliance), [brand verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification), and [sensitive-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification).
## Gemini API data-use disclosure

The current integration uses the Gemini Developer API. Google's current documentation says Free Tier prompts, responses, and submitted files may be used to improve Google products; Paid Tier content is not used for that purpose. Because this service analyzes customer video files, the customer UI now displays this disclosure, requires an explicit per-video consent before sending a file to Gemini, and records that consent in the tenant audit log. If the service owner later upgrades the Gemini project to a Paid Tier, review and update the notice based on the exact active billing tier and Google's current terms. Do not describe the Free Tier as private/no-training. See Google's [Gemini API billing and tier data-use details](https://ai.google.dev/gemini-api/docs/billing) and [pricing data-use table](https://ai.google.dev/gemini-api/docs/pricing).


## Current customer dashboard workflow

The customer home is intentionally limited to one video workflow: upload one video to the private intake bucket, generate/review/edit/save Gemini SEO, connect YouTube if not already connected, upload privately, then choose an IST schedule time with AM/PM. Customers without a YouTube channel can still prepare SEO using their workspace brand name. Exactly five hashtags are stored; one is the workspace brand until a channel is connected, then the connected channel's brand after regeneration. There is no thumbnail feature, customer analytics panel, Growth Doctor, Content Studio, support panel, billing panel, or Publish Now control in this customer workflow. The Master Admin view remains separate and is used for workspace activation/status.
