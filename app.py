"""Macherla Guru Creator Services — isolated customer/admin portal.

Authentication is handled by the dedicated Supabase project. Every Streamlit
session owns its own Supabase client; clients are never shared across users.
Roles and tenant membership are read from database tables protected by RLS.
This app intentionally performs no privileged writes.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(Path(__file__).parent / ".env")

APP_NAME = os.getenv("APP_NAME", "Macherla Guru Creator Services")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
SUPABASE_FUNCTIONS_URL = f"{SUPABASE_URL.rstrip('/')}/functions/v1" if SUPABASE_URL else ""

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


def start_youtube_oauth(tenant_id: str, client: Client) -> str:
    """Ask the authenticated Edge Function for a one-time Google authorization URL."""
    try:
        session = client.auth.get_session()
        access_token = getattr(session, "access_token", None) if session else None
        if not access_token:
            raise RuntimeError("missing_session")
        request = urllib.request.Request(
            f"{SUPABASE_FUNCTIONS_URL}/youtube-oauth-start",
            data=json.dumps({"tenant_id": tenant_id}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        authorization_url = payload.get("authorization_url", "")
        if not authorization_url.startswith("https://accounts.google.com/"):
            raise RuntimeError("invalid_authorization_url")
        return authorization_url
    except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError, AttributeError):
        raise RuntimeError("youtube_oauth_start_failed") from None


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
        return "Your account is not ready to sign in. Please contact the service administrator."
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
        with st.form("creator_sign_in", clear_on_submit=True):
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
                except Exception as exc:
                    st.error(safe_error_message(exc))
                else:
                    if not response.session or not response.user:
                        st.warning("Sign-in is not ready yet. Please contact the service administrator.")
                    else:
                        st.session_state["_creator_user_id"] = str(response.user.id)
                        st.rerun()

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
                            "options": {"data": {"name": display_name.strip()}},
                        }
                    )
                except Exception as exc:
                    st.error(safe_error_message(exc))
                else:
                    if response.session and response.user:
                        st.session_state["_creator_user_id"] = str(response.user.id)
                        st.success("Account created. Your service access will be activated separately.")
                        st.rerun()
                    else:
                        st.success(
                            "Account created. Check your email for the confirmation link. "
                            "After confirming, sign in; our team will activate your workspace separately."
                        )
    st.stop()

# Re-validate the identity with Supabase Auth on every rerun. Never trust a
# browser-supplied user ID, role, tenant ID, or user_metadata for authorization.
user = None
try:
    verified = supabase.auth.get_user()
    user = getattr(verified, "user", None)
except Exception:
    user = None

if user is None or str(user.id) != st.session_state["_creator_user_id"]:
    clear_session()
    st.warning("Your session expired. Please sign in again.")
    st.stop()

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
    st.caption("Approve customer access and provision isolated workspaces.")
    st.subheader("Pending customer requests")
    try:
        requests_result = (
            supabase.table("customer_requests")
            .select("user_id, email, display_name, status, created_at")
            .eq("status", "pending")
            .order("created_at", desc=False)
            .execute()
        )
        pending_requests = requests_result.data or []
    except Exception:
        pending_requests = []
        st.error("Customer requests could not be loaded. Check the admin RLS policy.")

    st.metric("Pending approvals", len(pending_requests))
    if not pending_requests:
        st.info("There are no pending customer requests.")
    else:
        for request in pending_requests:
            request_id = request["user_id"]
            customer_name = request.get("display_name") or "Creator"
            with st.container(border=True):
                st.write(f"**{customer_name}**")
                st.caption(request.get("email", "Email unavailable"))
                workspace_name = st.text_input(
                    "Workspace / business name",
                    value=f"{customer_name} YouTube Workspace",
                    key=f"workspace_{request_id}",
                )
                approve_col, reject_col = st.columns(2)
                with approve_col:
                    if st.button("Approve & create workspace", key=f"approve_{request_id}",
                                 type="primary", use_container_width=True):
                        if len(workspace_name.strip()) < 2:
                            st.warning("Enter a workspace name with at least 2 characters.")
                        else:
                            try:
                                supabase.rpc("admin_approve_customer", {
                                    "target_user": request_id,
                                    "workspace_name": workspace_name.strip(),
                                }).execute()
                            except Exception:
                                st.error("Approval failed. No access was granted; check the request and try again.")
                            else:
                                st.success("Customer approved and workspace created.")
                                st.rerun()
                with reject_col:
                    if st.button("Reject request", key=f"reject_{request_id}",
                                 use_container_width=True):
                        try:
                            supabase.rpc("admin_reject_customer", {
                                "target_user": request_id,
                            }).execute()
                        except Exception:
                            st.error("The request could not be rejected. Please try again.")
                        else:
                            st.success("Customer request rejected.")
                            st.rerun()

    st.divider()
    st.subheader("Active customer workspaces")
    try:
        tenants_result = (
            supabase.table("tenants")
            .select("id, business_name, status, created_at")
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
        st.error("Admin access could not be verified for the workspace list.")
    st.info(
        "Customer approval is active. Google OAuth connection endpoints are deployed; "
        "uploads, SEO operations, scheduling, and billing remain disabled until their "
        "separate workflows are implemented and tested."
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
            tenant_id = tenant["id"]
            st.subheader(tenant.get("business_name") or "Your YouTube workspace")
            st.caption(f"Workspace status: {tenant.get('status', 'pending')}")
            try:
                connections = (
                    supabase.rpc(
                        "list_tenant_youtube_connections",
                        {"target_tenant": tenant_id},
                    ).execute().data or []
                )
            except Exception:
                connections = []
                st.warning("YouTube connection status is temporarily unavailable.")

            if connections:
                for connection in connections:
                    st.success(
                        f"Connected channel: {connection.get('channel_title') or 'YouTube channel'}"
                    )
                    st.caption(f"Channel ID: {connection.get('channel_id', 'Unavailable')}")
            else:
                st.caption("No YouTube channel is connected yet.")
                if tenant.get("status") == "active":
                    if st.button(
                        "Connect YouTube channel",
                        key=f"connect_youtube_{tenant_id}",
                        type="primary",
                    ):
                        try:
                            google_url = start_youtube_oauth(tenant_id, supabase)
                        except RuntimeError:
                            st.error(
                                "Google connection is not configured yet. "
                                "Please contact the service administrator."
                            )
                        else:
                            st.link_button(
                                "Continue securely with Google",
                                google_url,
                                type="primary",
                            )
                else:
                    st.info("Your workspace must be active before connecting YouTube.")
        callback_status = st.query_params.get("youtube_oauth")
        if callback_status:
            if callback_status == "connected":
                st.success("Google returned to the app. The channel connection is saved if it appears above.")
            else:
                st.warning(
                    "Google connection did not complete. Check the Google consent setup "
                    "or ask the service administrator for help."
                )
        st.info(
            "Channel connection uses Google OAuth. The service never asks for your "
            "Google password. Video uploads and public/scheduled publishing are not "
            "enabled yet; customer approval will be required before publishing."
        )

st.caption(
    "Customer accounts cannot grant themselves admin access or assign tenant membership. "
    "YouTube publishing will require explicit customer approval."
)


# Operational views are read-only except for customer-created support tickets.
# Upload execution, SEO editing, publishing approval and billing changes remain
# disabled until their trusted server-side workflows are implemented and tested.
if role == "admin":
    st.divider()
    st.header("Service operations")
    op_uploads, op_support, op_billing = st.tabs(
        ["Upload queue", "Support inbox", "Billing overview"]
    )
    with op_uploads:
        try:
            rows = (
                supabase.table("upload_jobs")
                .select("id, tenant_id, video_title, status, youtube_video_id, scheduled_for, created_at")
                .order("created_at", desc=True)
                .limit(100)
                .execute().data or []
            )
            st.caption("Prepare SEO metadata for customer video jobs. Actual YouTube upload and publish execution remain gated on the live OAuth test.")
            if rows:
                for job in rows:
                    with st.container(border=True):
                        st.write(f"**{job.get('video_title') or 'Untitled video'}**")
                        st.caption(f"Job: {job['id']} • Status: {job.get('status', 'draft')} • Workspace: {job.get('tenant_id', '')}")
                        try:
                            existing_meta = (
                                supabase.table("content_metadata")
                                .select("title, description, tags, hashtags, caption")
                                .eq("upload_job_id", job["id"])
                                .order("created_at", desc=True)
                                .limit(1)
                                .execute().data or []
                            )
                            meta = existing_meta[0] if existing_meta else {}
                        except Exception:
                            meta = {}
                        with st.form(f"seo_metadata_{job['id']}"):
                            seo_title = st.text_input("SEO title", value=meta.get("title") or job.get("video_title") or "", max_chars=100)
                            seo_description = st.text_area("Description", value=meta.get("description") or "", max_chars=5000)
                            seo_tags = st.text_input("Tags (comma separated)", value=", ".join(meta.get("tags") or []))
                            seo_hashtags = st.text_input("Hashtags (comma separated)", value=" ".join(meta.get("hashtags") or []))
                            seo_caption = st.text_area("Caption", value=meta.get("caption") or "", max_chars=2200)
                            save_seo = st.form_submit_button("Save SEO metadata")
                        if save_seo:
                            try:
                                supabase.rpc("admin_save_content_metadata", {
                                    "p_upload_job": job["id"],
                                    "p_title": seo_title.strip(),
                                    "p_description": seo_description,
                                    "p_tags": [x.strip() for x in seo_tags.split(",") if x.strip()],
                                    "p_hashtags": [x.strip().lstrip("#") for x in seo_hashtags.split() if x.strip()],
                                    "p_caption": seo_caption,
                                }).execute()
                            except Exception:
                                st.error("SEO metadata could not be saved. Check the title and try again.")
                            else:
                                st.success("SEO metadata saved.")
                                st.rerun()
            else:
                st.info("No upload jobs have been submitted yet.")
        except Exception:
            st.error("Upload queue could not be loaded.")
    with op_support:
        try:
            tickets = (
                supabase.table("service_tickets")
                .select("id, tenant_id, subject, message, status, created_at")
                .order("created_at", desc=True)
                .limit(100)
                .execute().data or []
            )
            if tickets:
                for ticket in tickets:
                    with st.container(border=True):
                        st.write(f"**{ticket.get('subject') or 'Support request'}**")
                        st.caption(f"Ticket: {ticket['id']} • Workspace: {ticket.get('tenant_id')} • Status: {ticket.get('status')}")
                        st.write(ticket.get("message") or "")
                        status_options = ["open", "in_progress", "waiting_customer", "resolved", "closed"]
                        current_status = ticket.get("status") if ticket.get("status") in status_options else "open"
                        with st.form(f"ticket_status_{ticket['id']}"):
                            new_status = st.selectbox("Update status", status_options, index=status_options.index(current_status))
                            save_status = st.form_submit_button("Update ticket")
                        if save_status and new_status != current_status:
                            try:
                                supabase.rpc("admin_update_service_ticket_status", {
                                    "p_ticket": ticket["id"], "p_status": new_status
                                }).execute()
                            except Exception:
                                st.error("Ticket status could not be updated.")
                            else:
                                st.success("Ticket status updated.")
                                st.rerun()
            else:
                st.info("No customer support requests yet.")
        except Exception:
            st.error("Support inbox could not be loaded.")
    with op_billing:
        try:
            billing = (
                supabase.table("billing_accounts")
                .select("tenant_id, plan_code, subscription_status, updated_at")
                .order("updated_at", desc=True)
                .execute().data or []
            )
            if billing:
                st.dataframe(billing, use_container_width=True, hide_index=True)
            else:
                st.info("No billing accounts have been provisioned. Billing is not active.")
            st.caption("This is a status view only. No payments are collected or subscriptions changed here.")
        except Exception:
            st.error("Billing overview could not be loaded.")
else:
    st.divider()
    st.header("Your service")
    customer_uploads, customer_tickets, customer_billing = st.tabs(["Videos & approvals", "Support", "Plan & billing"])
    try:
        own_memberships = (
            supabase.table("tenant_memberships")
            .select("tenant_id")
            .eq("user_id", user_id)
            .execute().data or []
        )
        own_tenant_ids = [r["tenant_id"] for r in own_memberships if r.get("tenant_id")]
    except Exception:
        own_tenant_ids = []

    with customer_uploads:
        if not own_tenant_ids:
            st.info("Your video jobs will appear here after your workspace is activated.")
        else:
            try:
                own_jobs = (
                    supabase.table("upload_jobs")
                    .select("id, tenant_id, video_title, status, youtube_video_id, scheduled_for, created_at")
                    .in_("tenant_id", own_tenant_ids)
                    .order("created_at", desc=True)
                    .limit(50)
                    .execute().data or []
                )
                if not own_jobs:
                    st.info("No video jobs yet. The video file upload workflow is still being built.")
                for job in own_jobs:
                    with st.container(border=True):
                        st.write(f"**{job.get('video_title') or 'Your video'}**")
                        st.caption(f"Status: {job.get('status', 'draft')}")
                        if job.get("status") in {"uploaded_private", "awaiting_approval"}:
                            st.warning("This video is private. Review it before approving public publishing.")
                            if st.button("Approve public publishing", key=f"approve_video_{job['id']}", type="primary"):
                                try:
                                    supabase.rpc("customer_approve_upload", {"p_upload_job": job["id"]}).execute()
                                except Exception:
                                    st.error("Approval could not be recorded. Please contact support.")
                                else:
                                    st.success("Your approval has been recorded.")
                                    st.rerun()
                        elif job.get("status") == "approved":
                            st.info("Your approval is recorded. Publishing execution is not enabled yet.")
                        elif job.get("status") == "scheduled":
                            st.info("This video is marked as scheduled. Live scheduling execution is not enabled yet.")
                        elif job.get("status") == "published":
                            st.success("Published video.")
                        elif job.get("status") == "failed":
                            st.error("This job needs service-team attention.")
            except Exception:
                st.warning("Your video list is temporarily unavailable.")

    with customer_tickets:
        if not own_tenant_ids:
            st.info("Support is available after your workspace is activated.")
        else:
            with st.form("customer_support_request", clear_on_submit=True):
                ticket_tenant = st.selectbox("Workspace", own_tenant_ids)
                ticket_subject = st.text_input("Subject", max_chars=120)
                ticket_message = st.text_area("How can we help?", max_chars=4000)
                send_ticket = st.form_submit_button("Send support request", type="primary")
            if send_ticket:
                if len(ticket_subject.strip()) < 3 or len(ticket_message.strip()) < 10:
                    st.warning("Enter a subject and at least 10 characters describing the issue.")
                else:
                    try:
                        supabase.table("service_tickets").insert({
                            "tenant_id": ticket_tenant,
                            "subject": ticket_subject.strip(),
                            "message": ticket_message.strip(),
                        }).execute()
                    except Exception:
                        st.error("Your support request could not be sent. Please try again.")
                    else:
                        st.success("Support request submitted.")
                        st.rerun()
            try:
                own_ticket_rows = (
                    supabase.table("service_tickets")
                    .select("subject, message, status, created_at")
                    .in_("tenant_id", own_tenant_ids)
                    .order("created_at", desc=True)
                    .limit(50)
                    .execute().data or []
                )
                if own_ticket_rows:
                    st.dataframe(own_ticket_rows, use_container_width=True, hide_index=True)
                else:
                    st.caption("You have not submitted a support request yet.")
            except Exception:
                st.warning("Your support history is temporarily unavailable.")
    with customer_billing:
        if not own_tenant_ids:
            st.info("Plan information will appear after workspace activation.")
        else:
            try:
                own_billing = (
                    supabase.table("billing_accounts")
                    .select("plan_code, subscription_status, updated_at")
                    .in_("tenant_id", own_tenant_ids)
                    .execute().data or []
                )
                if own_billing:
                    st.dataframe(own_billing, use_container_width=True, hide_index=True)
                else:
                    st.info("No plan has been assigned yet. Billing is not active.")
                st.caption("No payment is due through this dashboard until an official payment flow is enabled.")
            except Exception:
                st.warning("Plan information is temporarily unavailable.")
