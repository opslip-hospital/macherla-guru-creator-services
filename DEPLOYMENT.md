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

## AI YouTube SEO generation

The customer dashboard includes **Generate YouTube SEO** for each uploaded video. It creates a title, description, tags, up to five hashtags, and a short caption; the customer can edit and save the result before uploading.

In the dedicated Supabase project's **Edge Functions > Secrets**, add:

- `GEMINI_API_KEY` — a Google AI Studio / Gemini API key for the Creator Services project.

Keep this key only in Supabase Edge Function secrets. Do not add it to Streamlit secrets, GitHub, or chat. The Edge Function calls Gemini server-side and checks that the signed-in user owns the video's workspace before generating or saving metadata. It uses the Gemini `generateContent` REST endpoint and structured JSON output.

## Customer self-service publishing

Customers can upload their own video to their connected YouTube channel as **PRIVATE**, then choose **Publish now** or **Schedule** from their dashboard. The publish/schedule button is the customer's explicit action; there is no separate platform-admin video approval. Google OAuth publishing permission is still required for changing video visibility or scheduling. Customers must reconnect their channel if the requested publishing scope was not granted.

The OAuth flow requests only `youtube.upload` and `youtube.readonly`. A short-lived, one-use state is stored as a hash. The refresh token is encrypted with AES-256-GCM before it is stored in the private schema. Only the channel identity and granted scopes are returned to the customer UI.

## Current limitations

OAuth endpoints and the customer connection entry point are deployed, but Google credentials and the encryption key still need to be configured. Do not treat OAuth as live until a real test account connects and the channel appears in the customer workspace. The AI SEO and customer self-service upload/publish code is deployed, but live Gemini generation and real YouTube upload/publish actions are not verified until the Gemini secret is set and a valid YouTube channel completes end-to-end testing. Billing/payment processing is not enabled.
