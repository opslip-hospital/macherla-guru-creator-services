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

The repository contains two deployed Edge Functions in the dedicated Creator Services Supabase project:

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

The project-provided `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` are read inside Edge Functions. Never copy the service-role key into Streamlit or GitHub.

The OAuth flow requests only `youtube.upload` and `youtube.readonly`. A short-lived, one-use state is stored as a hash. The refresh token is encrypted with AES-256-GCM before it is stored in the private schema. Only the channel identity and granted scopes are returned to the customer UI.

## Current limitations

OAuth endpoints and the customer connection entry point are deployed, but Google credentials and the encryption key still need to be configured. Do not treat OAuth as live until a real test account connects and the channel appears in the customer workspace. Video upload, private-first approval, scheduled publishing, SEO operations, billing, and production support workflows are not yet enabled.
