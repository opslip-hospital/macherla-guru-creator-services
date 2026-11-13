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

## Current limitations

A successful deployment at this stage provides only the registration/sign-in shell and the initial customer/admin dashboard views. It does not yet provide Google OAuth, YouTube upload, customer approval, scheduled publishing, SEO operations, billing, or production-ready support workflows. Those must be implemented and security-tested before accepting real customer channels.
