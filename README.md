# Macherla Guru Creator Services

A separate, private managed YouTube creator service. It is independent of the existing Macherla Guru YouTube AI Manager.

## Architecture

- **Customer workspace:** planned secure sign-in, own YouTube channel connection, upload status, and explicit approval before public publishing or scheduling.
- **Master admin:** planned server-verified admin workspace for customer management, metadata/SEO, scheduling, support, service health, and reports.
- **Tenant isolation:** PostgreSQL row-level security limits customer reads to tenant memberships. Browser-provided roles and tenant IDs are never trusted.
- **OAuth credentials:** YouTube refresh tokens belong in the non-exposed `private.youtube_connections` schema and must be encrypted by the trusted server before storage.

## Supabase foundation

A dedicated Supabase project named **Macherla Guru Creator Services** has been created in **ap-south-1 (Mumbai)**. It is separate from the existing channel manager's Supabase project.

Migrations are in `supabase/migrations/`:
1. `202611130001_initial_tenant_isolated_schema.sql` — tenant, membership, uploads, metadata, support, audit, billing, private YouTube connection storage, RLS policies and least-privilege grants.
2. `202611130002_create_customer_profile_on_signup.sql` — creates a customer profile on Supabase Auth signup; role is always initialized as customer.

## Current status

The database foundation is deployed and verified. The Streamlit app is still a locked foundation shell. It does **not** yet implement verified login, customer provisioning, admin authorization, Google OAuth, video upload, scheduling, billing, or deployment. Do not use it with real customers until these parts are implemented and tested.

## Local setup

1. Python 3.11+ and a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure only non-secret project URL / publishable key plus trusted server-side secrets as the implementation requires.
4. Run: `streamlit run app.py`.

Never commit `.env`, Google OAuth client secrets, access/refresh tokens, database passwords, Supabase secret/service-role keys, or customer data.

## Protected boundary

Do not modify, import, or deploy code from `opslip-hospital/macherla-guru-ai-agent`. The existing Macherla Guru YouTube AI Manager remains separate and untouched.
