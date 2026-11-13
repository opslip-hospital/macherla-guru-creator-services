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

    def test_existing_manager_is_not_imported_or_called(self):
        self.assertNotIn("macherla-guru-ai-agent", APP)
        self.assertNotIn("youtube.com/@macherlaguru", APP)


if __name__ == "__main__":
    unittest.main()
