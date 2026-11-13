"""Macherla Guru Creator Services — isolated customer/admin portal.

Authentication is handled by the dedicated Supabase project. Every Streamlit
session owns its own Supabase client; clients are never shared across users.
Roles and tenant membership are read from database tables protected by RLS.
This app intentionally performs no privileged writes.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(Path(__file__).parent / ".env")

APP_NAME = os.getenv("APP_NAME", "Macherla Guru Creator Services")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🎬 Macherla Guru Creator Services")
st.caption("Managed YouTube services • Customer workspace • Master administration")
st.info(
    "This is a separate service project. The existing Macherla Guru YouTube AI "
    "Manager is not connected to or modified by this application."
)


def get_session_client() -> Client:
    """Create one Supabase client per Streamlit browser session."""
    client = st.session_state.get("_creator_supabase_client")
    if client is None:
        client = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
        st.session_state["_creator_supabase_client"] = client
    return client


def clear_session() -> None:
    """Clear this browser session's auth client and identity."""
    client = st.session_state.get("_creator_supabase_client")
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    st.session_state.pop("_creator_supabase_client", None)
    st.session_state.pop("_creator_user_id", None)


def safe_error_message(error: Exception) -> str:
    """Avoid displaying provider response bodies or tokens to end users."""
    message = str(error).lower()
    if "invalid login credentials" in message:
        return "Email or password is incorrect."
    if "email not confirmed" in message:
        return "Please confirm your email using the link sent to your inbox."
    if "user already registered" in message:
        return "An account already exists. Please sign in."
    return "We couldn't complete that request. Please check your details and try again."


if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
    st.warning(
        "Secure sign-in is locked until SUPABASE_URL and "
        "SUPABASE_PUBLISHABLE_KEY are configured in the deployment secrets."
    )
    st.stop()

try:
    supabase = get_session_client()
except Exception:
    st.error("Authentication service is temporarily unavailable. Please try again later.")
    st.stop()

# Existing customers and staff sign in. New customers may register, but account
# creation never grants admin rights or creates a tenant/membership.
if not st.session_state.get("_creator_user_id"):
    sign_in_tab, register_tab = st.tabs(["Sign in", "Create customer account"])

    with sign_in_tab:
        with st.form("creator_sign_in", clear_on_submit=False):
            email = st.text_input("Email address", key="signin_email").strip().lower()
            password = st.text_input("Password", type="password", key="signin_password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            if not email or not password:
                st.warning("Enter your email address and password.")
            else:
                try:
                    response = supabase.auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )
                    if not response.session or not response.user:
                        st.warning("Sign-in needs email verification. Check your inbox.")
                    else:
                        st.session_state["_creator_user_id"] = str(response.user.id)
                        st.rerun()
                except Exception as exc:
                    st.error(safe_error_message(exc))

    with register_tab:
        st.caption("Create a customer login. Service access is activated separately by our team.")
        with st.form("creator_register", clear_on_submit=True):
            display_name = st.text_input("Your name")
            new_email = st.text_input("Email address", key="register_email").strip().lower()
            new_password = st.text_input(
                "Create password (minimum 8 characters)",
                type="password",
                key="register_password",
            )
            confirm_password = st.text_input(
                "Confirm password", type="password", key="register_confirm_password"
            )
            register = st.form_submit_button(
                "Create account", type="primary", use_container_width=True
            )
        if register:
            if not new_email or not display_name.strip():
                st.warning("Enter your name and email address.")
            elif len(new_password) < 8:
                st.warning("Use a password with at least 8 characters.")
            elif new_password != confirm_password:
                st.warning("The passwords do not match.")
            else:
                try:
                    response = supabase.auth.sign_up(
                        {
                            "email": new_email,
                            "password": new_password,
                            "options": {"data": {"display_name": display_name.strip()}},
                        }
                    )
                    if response.session and response.user:
                        st.session_state["_creator_user_id"] = str(response.user.id)
                        st.success("Account created. Your service access will be activated separately.")
                        st.rerun()
                    else:
                        st.success(
                            "Account request received. Please confirm your email, then sign in. "
                            "Our team will activate your customer workspace separately."
                        )
                except Exception as exc:
                    st.error(safe_error_message(exc))
    st.stop()

# Re-validate the identity with Supabase Auth on every rerun. Never trust a
# browser-supplied user ID, role, tenant ID, or user_metadata for authorization.
try:
    verified = supabase.auth.get_user()
    user = getattr(verified, "user", None)
    if user is None or str(user.id) != st.session_state["_creator_user_id"]:
        clear_session()
        st.warning("Your session expired. Please sign in again.")
        st.rerun()
except Exception:
    clear_session()
    st.warning("Your session expired. Please sign in again.")
    st.rerun()

user_id = str(user.id)

try:
    profile_result = (
        supabase.table("profiles")
        .select("user_id, display_name, role")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    profile: dict[str, Any] | None = profile_result.data
except Exception:
    st.error("We couldn't verify your service profile. Please contact support.")
    st.stop()

if not profile or profile.get("role") not in {"customer", "admin"}:
    st.error("Your account doesn't have an active service profile. Contact support.")
    st.stop()

display_name = profile.get("display_name") or getattr(user, "email", None) or "Creator"
role = profile["role"]

st.divider()
left, right = st.columns([4, 1])
with left:
    st.subheader(f"Welcome, {display_name}")
    st.caption(f"Signed in as {getattr(user, 'email', 'verified account')}")
with right:
    if st.button("Sign out", use_container_width=True):
        clear_session()
        st.rerun()

if role == "admin":
    st.header("Master Admin Dashboard")
    st.caption("Platform overview — customer data is read through admin-only RLS policies.")
    try:
        tenants_result = (
            supabase.table("tenants")
            .select("id, business_name, status")
            .order("created_at", desc=True)
            .execute()
        )
        tenants = tenants_result.data or []
        st.metric("Customer workspaces", len(tenants))
        if tenants:
            st.dataframe(tenants, use_container_width=True, hide_index=True)
        else:
            st.info("No customer workspaces have been provisioned yet.")
    except Exception:
        st.error("Admin access could not be verified for the customer workspace list.")
    st.info(
        "Upload controls, YouTube OAuth, SEO operations, scheduling, billing, and "
        "support workflows will be added only after their server-side authorization "
        "and audit controls are implemented."
    )
else:
    st.header("Customer Dashboard")
    try:
        memberships_result = (
            supabase.table("tenant_memberships")
            .select("tenant_id")
            .eq("user_id", user_id)
            .execute()
        )
        memberships = memberships_result.data or []
    except Exception:
        st.error("We couldn't load your customer workspace. Please contact support.")
        st.stop()

    if not memberships:
        st.info(
            "Your login is ready. Your customer workspace is waiting for activation "
            "by the Macherla Guru Creator Services team."
        )
    else:
        tenant_ids = [row["tenant_id"] for row in memberships if row.get("tenant_id")]
        tenant_result = (
            supabase.table("tenants")
            .select("id, business_name, status")
            .in_("id", tenant_ids)
            .execute()
        )
        tenant_rows = tenant_result.data or []
        for tenant in tenant_rows:
            st.subheader(tenant.get("business_name") or "Your YouTube workspace")
            st.caption(f"Workspace status: {tenant.get('status', 'pending')}")
        st.info(
            "Your workspace is connected. Video upload, private-first approval, "
            "SEO delivery, scheduling, and reports will appear here as each workflow "
            "passes its security checks."
        )

st.caption(
    "Customer accounts cannot grant themselves admin access or assign tenant membership. "
    "YouTube publishing will require explicit customer approval."
)
