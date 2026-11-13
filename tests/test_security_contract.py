"""Static guardrails for the customer portal's security boundaries.

These checks are not a substitute for live OAuth, RLS, or penetration tests.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
INITIAL_SCHEMA = (
    ROOT / "supabase/migrations/202611130001_initial_tenant_isolated_schema.sql"
).read_text(encoding="utf-8")
SIGNUP_MIGRATION = (
    ROOT / "supabase/migrations/202611130002_create_customer_profile_on_signup.sql"
).read_text(encoding="utf-8")
HARDENING_MIGRATION = (
    ROOT / "supabase/migrations/20261113060934_harden_private_rls_helpers_and_fk_indexes.sql"
).read_text(encoding="utf-8")
WORKFLOW_MIGRATION = (
    ROOT / "supabase/migrations/20261113171000_creator_service_workflows.sql"
).read_text(encoding="utf-8")
UPLOAD_MIGRATION = (
    ROOT / "supabase/migrations/20261113180000_customer_video_intake_storage.sql"
).read_text(encoding="utf-8")
YOUTUBE_WORKER_MIGRATION = (
    ROOT / "supabase/migrations/20261113190000_youtube_private_upload_worker.sql"
).read_text(encoding="utf-8")
YOUTUBE_WORKER = (
    ROOT / "supabase/functions/youtube-upload-private/index.ts"
).read_text(encoding="utf-8")
PUBLISH_MIGRATION = (
    ROOT / "supabase/migrations/20261113200000_youtube_customer_approved_publish_schedule.sql"
).read_text(encoding="utf-8")
PUBLISH_WORKER = (
    ROOT / "supabase/functions/youtube-publish-approved/index.ts"
).read_text(encoding="utf-8")
OAUTH_START = (
    ROOT / "supabase/functions/youtube-oauth-start/index.ts"
).read_text(encoding="utf-8")
ANALYTICS_MIGRATION = (
    ROOT / "supabase/migrations/20261113210000_tenant_channel_analytics_snapshots.sql"
).read_text(encoding="utf-8")
ANALYTICS_WORKER = (
    ROOT / "supabase/functions/youtube-refresh-analytics/index.ts"
).read_text(encoding="utf-8")
SELF_SERVICE_MIGRATION = (
    ROOT / "supabase/migrations/20261113220000_customer_self_service_youtube_workflow.sql"
).read_text(encoding="utf-8")
CUSTOMER_SEO_FUNCTION = (
    ROOT / "supabase/functions/customer-youtube-seo/index.ts"
).read_text(encoding="utf-8")


class AuthenticationContractTests(unittest.TestCase):
    def test_app_uses_publishable_key_not_privileged_key(self):
        self.assertIn("SUPABASE_PUBLISHABLE_KEY", APP)
        self.assertNotIn("SUPABASE_SECRET_KEY", APP)
        self.assertNotIn("service_role", APP.lower())

    def test_user_identity_is_revalidated(self):
        self.assertIn("supabase.auth.get_user()", APP)
        self.assertIn('str(user.id) != st.session_state["_creator_user_id"]', APP)

    def test_role_is_loaded_from_database_profile(self):
        self.assertIn('select("user_id, display_name, role")', APP)
        self.assertIn('role = profile["role"]', APP)
        self.assertNotIn('user.user_metadata.get("role")', APP)

    def test_signup_never_assigns_admin_or_membership(self):
        self.assertIn("'customer'", SIGNUP_MIGRATION)
        self.assertNotIn("tenant_memberships", SIGNUP_MIGRATION)
        self.assertNotIn('"role": "admin"', APP)
        self.assertIn('"name": display_name.strip()', APP)

    def test_tenant_reads_are_rls_protected(self):
        self.assertIn("alter table public.tenants enable row level security", INITIAL_SCHEMA)
        self.assertIn("alter table public.tenant_memberships enable row level security", INITIAL_SCHEMA)
        self.assertIn("tenants_select_member_or_admin", INITIAL_SCHEMA)
        self.assertIn("memberships_select_self_or_admin", INITIAL_SCHEMA)

    def test_youtube_tokens_are_private_and_not_client_accessible(self):
        self.assertIn("create table private.youtube_connections", INITIAL_SCHEMA)
        self.assertIn("revoke all on schema private from public, anon, authenticated", INITIAL_SCHEMA)
        self.assertIn("grant usage on schema private to authenticated", HARDENING_MIGRATION)
        self.assertIn("revoke all on function private.is_platform_admin() from public, anon", HARDENING_MIGRATION)

    def test_customer_support_uses_existing_tenant_insert_policy(self):
        self.assertIn('supabase.table("service_tickets").insert({', APP)
        self.assertIn('"tenant_id": ticket_tenant', APP)
        self.assertIn('select("subject, message, status, created_at")', APP)

    def test_customer_operations_do_not_enable_upload_or_billing_writes(self):
        self.assertIn('supabase.table("upload_jobs")', APP)
        self.assertIn('supabase.table("billing_accounts")', APP)
        self.assertNotIn('supabase.table("upload_jobs").insert(', APP)
        self.assertNotIn('supabase.table("billing_accounts").insert(', APP)

    def test_metadata_mutations_are_admin_only_server_functions(self):
        self.assertIn("private.admin_save_content_metadata", WORKFLOW_MIGRATION)
        self.assertIn("private.is_platform_admin()", WORKFLOW_MIGRATION)
        self.assertIn("public.admin_save_content_metadata", WORKFLOW_MIGRATION)
        self.assertIn("content_metadata_prepared", WORKFLOW_MIGRATION)

    def test_customer_can_publish_own_video_without_admin_approval(self):
        self.assertIn("membership_role='owner'", SELF_SERVICE_MIGRATION)
        self.assertIn("workspace owner required", SELF_SERVICE_MIGRATION)
        self.assertIn("explicit_customer_action", SELF_SERVICE_MIGRATION)
        self.assertIn('publish_approved_video(', APP)
        self.assertNotIn('supabase.rpc("customer_approve_upload"', APP)

    def test_support_status_changes_are_admin_only_and_audited(self):
        self.assertIn("private.admin_update_service_ticket_status", WORKFLOW_MIGRATION)
        self.assertIn("support_ticket_status_changed", WORKFLOW_MIGRATION)
        self.assertIn('supabase.rpc("admin_update_service_ticket_status"', APP)

    def test_customer_video_intake_is_private_and_tenant_scoped(self):
        self.assertIn("values ('customer-video-intake','customer-video-intake',false", UPLOAD_MIGRATION)
        self.assertIn("private.create_customer_upload_job", UPLOAD_MIGRATION)
        self.assertIn("private.finalize_customer_video_upload", UPLOAD_MIGRATION)
        self.assertIn("customer video intake insert own tenant", UPLOAD_MIGRATION)
        self.assertIn("customer video intake read own tenant or admin", UPLOAD_MIGRATION)
        self.assertIn('supabase.storage.from_("customer-video-intake").upload(', APP)
        self.assertIn('supabase.rpc("finalize_customer_video_upload"', APP)
        self.assertIn('type=["mp4", "mov", "webm"]', APP)
        self.assertIn('create_signed_url(', APP)
        self.assertIn('Download customer video (1-hour link)', APP)

    def test_private_youtube_upload_is_customer_owner_scoped_and_private_first(self):
        self.assertIn("private.claim_youtube_upload_job", SELF_SERVICE_MIGRATION)
        self.assertIn("membership_role='owner'", SELF_SERVICE_MIGRATION)
        self.assertIn("granted_scopes @>", YOUTUBE_WORKER_MIGRATION)
        self.assertIn('privacyStatus: "private"', YOUTUBE_WORKER)
        self.assertIn('status: "uploaded_private"', YOUTUBE_WORKER)
        self.assertIn('youtube-upload-private', APP)
        self.assertIn('Upload to my YouTube channel (PRIVATE)', APP)
        self.assertIn("The channel owner can now publish or schedule it", YOUTUBE_WORKER)

    def test_customer_publish_is_explicit_and_tenant_scoped(self):
        self.assertIn("v_job.status not in ('uploaded_private','approved')", SELF_SERVICE_MIGRATION)
        self.assertIn("youtube.force-ssl", SELF_SERVICE_MIGRATION)
        self.assertIn('privacyStatus:"public"', PUBLISH_WORKER)
        self.assertIn('privacyStatus:"private",publishAt', PUBLISH_WORKER)
        self.assertIn("initiated_by_authenticated_owner_or_admin:true", PUBLISH_WORKER)
        self.assertIn("youtube.force-ssl", OAUTH_START)
        self.assertIn("Reconnect for publishing permissions", APP)

    def test_analytics_snapshots_are_tenant_scoped_and_admin_refreshed(self):
        self.assertIn("analytics_select_member_or_admin", ANALYTICS_MIGRATION)
        self.assertIn("private.claim_youtube_analytics", ANALYTICS_MIGRATION)
        self.assertIn("youtube.readonly", ANALYTICS_MIGRATION)
        self.assertIn("channel_analytics_snapshots", ANALYTICS_WORKER)
        self.assertIn('youtube-refresh-analytics', APP)
        self.assertIn("Channel analytics", APP)

    def test_customer_ai_seo_is_owner_scoped_and_saved_server_side(self):
        self.assertIn('customer-youtube-seo', APP)
        self.assertIn('✨ Generate YouTube SEO', APP)
        self.assertIn('Save my SEO edits', APP)
        self.assertIn('membership_role', CUSTOMER_SEO_FUNCTION)
        self.assertIn('GEMINI_API_KEY', CUSTOMER_SEO_FUNCTION)
        self.assertIn('customer_ai_seo_generated', CUSTOMER_SEO_FUNCTION)
        self.assertNotIn('GEMINI_API_KEY', APP)

    def test_customer_channel_dashboard_is_owner_scoped(self):
        dashboard = (ROOT / "supabase/functions/customer-channel-dashboard/index.ts").read_text(encoding="utf-8")
        self.assertIn("workspace_owner_required", dashboard)
        self.assertIn("youtube.readonly", dashboard)
        self.assertIn("playlistItems?part=snippet,contentDetails", dashboard)
        self.assertIn("videos?part=snippet,statistics,status", dashboard)
        self.assertIn("customer_channel_dashboard_request", APP)
        self.assertIn("Recent uploads — sorted by views", APP)

    def test_customer_content_studio_is_tenant_scoped_and_server_keyed(self):
        studio = (ROOT / "supabase/functions/customer-content-studio/index.ts").read_text(encoding="utf-8")
        self.assertIn("membership_role", studio)
        self.assertIn("GEMINI_API_KEY", studio)
        self.assertIn("customer_content_studio_request", APP)
        self.assertIn("✨ Gemini AI Content Studio", APP)
        self.assertIn("🩺 Your AI Growth Doctor", APP)

    def test_existing_manager_is_not_imported_or_called(self):
        self.assertNotIn("macherla-guru-ai-agent", APP)
        self.assertNotIn("youtube.com/@macherlaguru", APP)


if __name__ == "__main__":
    unittest.main()
