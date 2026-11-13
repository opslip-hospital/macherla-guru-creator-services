# Macherla Guru Creator Services

A separate, private project for a managed YouTube creator service. This repository is independent of the existing Macherla Guru YouTube AI Manager.

## Product model

- **Customer dashboard:** a customer can eventually connect their own Google/YouTube account through Google OAuth, upload a video, review status, and explicitly approve publishing or scheduling.
- **Master admin dashboard:** the service operator manages customer accounts, metadata/SEO work, scheduling, support, service status, and reports.
- **Tenant isolation:** every customer can access only their own channel connections, uploads, and reports. Admin access is enforced on the server, never merely by hiding UI elements.

## Current status

This is the secure project foundation, not a production-ready service yet. Authentication, persistent database, Google OAuth consent/configuration, YouTube upload integration, billing, and deployment must be configured and security-tested before real customer data or channels are used. The app fails closed while required authentication configuration is absent.

## Run locally

1. Use Python 3.11 or newer.
2. Create a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill values only after the authentication/database services are configured.
5. Run: `streamlit run app.py`.

Do not commit `.env`, OAuth client secrets, access/refresh tokens, service-role keys, or customer data.

## Environment

See `.env.example`. Never put real secrets in GitHub.

## Planned implementation sequence

1. Authentication and role-based access (customer/admin).
2. Database schema with row-level tenant isolation.
3. Google OAuth with minimum YouTube scopes and per-customer token storage.
4. Private-first upload workflow and explicit customer approval before public/scheduled publishing.
5. Admin-managed SEO/captions/tags, scheduling, support, reports, and audit logs.
6. Billing, monitoring, deployment, and security review.

## Protected boundary

Do not modify, import, or deploy code from `opslip-hospital/macherla-guru-ai-agent`. That existing channel manager remains separate and untouched.
