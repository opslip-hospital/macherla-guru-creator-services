"""Macherla Guru Creator Services — isolated customer/admin portal.

Authentication is handled by the dedicated Supabase project. Every Streamlit
session owns its own Supabase client; clients are never shared across users.
Roles and tenant membership are read from database tables protected by RLS.
This app intentionally performs no privileged writes.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import re
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


def start_private_youtube_upload(job_id: str, client: Client) -> dict[str, Any]:
    """Request an owner-checked server-side upload; Google tokens never reach Streamlit."""
    try:
        session = client.auth.get_session()
        access_token = getattr(session, "access_token", None) if session else None
        if not access_token:
            raise RuntimeError("missing_session")
        request = urllib.request.Request(
            f"{SUPABASE_FUNCTIONS_URL}/youtube-upload-private",
            data=json.dumps({"job_id": job_id}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("success") or payload.get("status") != "uploaded_private":
            raise RuntimeError("private_upload_failed")
        return payload
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, RuntimeError, AttributeError):
        raise RuntimeError("private_upload_failed") from None


def publish_approved_video(
    job_id: str, mode: str, publish_at: str | None, client: Client
) -> dict[str, Any]:
    """Execute public publishing or scheduling only through the trusted Edge Function."""
    try:
        session = client.auth.get_session()
        access_token = getattr(session, "access_token", None) if session else None
        if not access_token:
            raise RuntimeError("missing_session")
        request = urllib.request.Request(
            f"{SUPABASE_FUNCTIONS_URL}/youtube-publish-approved",
            data=json.dumps({
                "job_id": job_id,
                "mode": mode,
                "publish_at": publish_at,
            }).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("success"):
            raise RuntimeError("publish_failed")
        return payload
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, RuntimeError, AttributeError):
        raise RuntimeError("publish_failed") from None


def refresh_youtube_analytics(tenant_id: str, client: Client) -> dict[str, Any]:
    """Refresh channel statistics in the trusted backend without exposing Google tokens."""
    try:
        session = client.auth.get_session()
        access_token = getattr(session, "access_token", None) if session else None
        if not access_token:
            raise RuntimeError("missing_session")
        request = urllib.request.Request(
            f"{SUPABASE_FUNCTIONS_URL}/youtube-refresh-analytics",
            data=json.dumps({"tenant_id": tenant_id}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("success"):
            raise RuntimeError("analytics_refresh_failed")
        return payload
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, RuntimeError, AttributeError):
        raise RuntimeError("analytics_refresh_failed") from None


def customer_youtube_seo_request(
    action: str, job_id: str, client: Client, values: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Generate or save a customer's SEO metadata through an owner-checked Edge Function."""
    try:
        session = client.auth.get_session()
        access_token = getattr(session, "access_token", None) if session else None
        if not access_token:
            raise RuntimeError("missing_session")
        payload = {"action": action, "job_id": job_id, **(values or {})}
        request = urllib.request.Request(
            f"{SUPABASE_FUNCTIONS_URL}/customer-youtube-seo",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("success"):
            raise RuntimeError(str(result.get("error") or "seo_request_failed"))
        return result
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = str(body.get("error") or "seo_request_failed")
            stage = str(body.get("stage") or "")
            provider_status = str(body.get("provider_status") or "")
            provider_code = str(body.get("provider_code") or "")
            provider_message = str(body.get("provider_message") or "")
        except Exception:
            detail, stage, provider_status, provider_code, provider_message = "seo_request_failed", "", "", "", ""
        safe_detail = detail[:80]
        safe_stage = stage[:40]
        safe_provider = re.sub(r"[^A-Za-z0-9 _.,:()/-]", "", provider_message)[:180]
        parts = [safe_detail]
        if safe_stage:
            parts.append(safe_stage)
        if provider_status:
            parts.append(f"Gemini HTTP {provider_status}")
        if provider_code and provider_code != "not_provided":
            parts.append(provider_code[:80])
        if safe_provider:
            parts.append(safe_provider)
        raise RuntimeError(": ".join(parts)) from None
    except (urllib.error.URLError, TimeoutError, ValueError, AttributeError):
        raise RuntimeError("seo_request_failed") from None


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
        "Customer AI SEO generation and self-service YouTube upload/publish workflows are deployed in code. "
        "Live Gemini and YouTube actions still need a successful end-to-end test. Payment processing is not enabled."
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
                if tenant.get("status") == "active":
                    st.caption(
                        "YouTube needs permission to upload videos and update their visibility for publishing/scheduling. "
                        "Google will show the requested permissions before you grant access."
                    )
                    if st.button(
                        "Reconnect for publishing permissions",
                        key=f"reconnect_youtube_{tenant_id}",
                    ):
                        try:
                            google_url = start_youtube_oauth(tenant_id, supabase)
                        except RuntimeError:
                            st.error("Google connection could not be started. Please contact support.")
                        else:
                            st.link_button("Continue securely with Google", google_url)
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
            "Channel connection uses Google OAuth. The service never asks for your Google password. "
            "After connecting, you can generate SEO, upload privately, and choose Publish now or Schedule. "
            "Your publish/schedule button is your instruction; no separate video approval is needed."
        )

st.caption(
    "Customer accounts cannot grant themselves admin access or assign tenant membership. "
    "Each customer can only manage videos and publish actions for their own connected workspace."
)


# Operational views let the platform admin monitor tenant-scoped customer work.
# Customer video upload, SEO generation, and publish/schedule actions run through
# authenticated server-side functions; billing changes remain disabled.
if role == "admin":
    st.divider()
    st.header("Service operations")
    op_uploads, op_support, op_billing, op_analytics = st.tabs(
        ["Upload queue", "Support inbox", "Billing overview", "Channel analytics"]
    )
    with op_uploads:
        try:
            rows = (
                supabase.table("upload_jobs")
                .select("id, tenant_id, video_title, status, youtube_video_id, scheduled_for, storage_object_path, original_filename, file_size_bytes, created_at")
                .order("created_at", desc=True)
                .limit(100)
                .execute().data or []
            )
            st.caption("Monitor customer uploads, metadata, private uploads and publishing activity. Customers can publish or schedule their own videos; live Google OAuth testing is still pending.")
            if rows:
                for job in rows:
                    with st.container(border=True):
                        st.write(f"**{job.get('video_title') or 'Untitled video'}**")
                        st.caption(f"Job: {job['id']} • Status: {job.get('status', 'draft')} • Workspace: {job.get('tenant_id', '')}")
                        if job.get("status") == "received":
                            if st.button("Upload privately to connected YouTube channel", key=f"private_youtube_upload_{job['id']}", type="primary"):
                                try:
                                    upload_result = start_private_youtube_upload(job["id"], supabase)
                                except RuntimeError:
                                    st.error("Private YouTube upload failed. Check the customer's Google channel connection and OAuth permissions before retrying.")
                                else:
                                    st.success("YouTube accepted the video as PRIVATE. The customer can publish or schedule it from their dashboard.")
                                    if upload_result.get("youtube_url"):
                                        st.link_button("Open private YouTube video", upload_result["youtube_url"])
                        if job.get("status") in {"uploaded_private", "approved"}:
                            with st.form(f"publish_action_{job['id']}"):
                                publish_mode = st.radio(
                                    "Publishing action",
                                    ["Publish now", "Schedule"],
                                    horizontal=True,
                                    key=f"publish_mode_{job['id']}",
                                )
                                if publish_mode == "Schedule":
                                    schedule_date = st.date_input(
                                        "Schedule date (IST)",
                                        value=date.today() + timedelta(days=1),
                                        min_value=date.today(),
                                        key=f"schedule_date_{job['id']}",
                                    )
                                    schedule_time = st.time_input(
                                        "Schedule time (IST)",
                                        value=time(9, 0),
                                        key=f"schedule_time_{job['id']}",
                                    )
                                else:
                                    schedule_date = None
                                    schedule_time = None
                                execute_publish = st.form_submit_button(
                                    "Confirm publish action", type="primary"
                                )
                            if execute_publish:
                                publish_at = None
                                if publish_mode == "Schedule" and schedule_date and schedule_time:
                                    publish_at = datetime.combine(
                                        schedule_date, schedule_time,
                                        tzinfo=ZoneInfo("Asia/Kolkata"),
                                    ).isoformat()
                                try:
                                    publish_result = publish_approved_video(
                                        job["id"],
                                        "schedule" if publish_mode == "Schedule" else "now",
                                        publish_at,
                                        supabase,
                                    )
                                except RuntimeError:
                                    st.error("Publish action failed. The video remains private; verify the customer's new YouTube publishing permission.")
                                else:
                                    st.success(publish_result.get("message", "Publish action completed."))
                                    if publish_result.get("youtube_url"):
                                        st.link_button("Open YouTube video", publish_result["youtube_url"])
                        if job.get("status") == "publishing":
                            st.info("Publishing request is processing.")
                        elif job.get("status") == "scheduled":
                            st.info(f"Scheduled for: {job.get('scheduled_for')}")
                        elif job.get("status") == "published":
                            st.success("Public on YouTube.")
                        if job.get("storage_object_path"):
                            try:
                                signed = supabase.storage.from_("customer-video-intake").create_signed_url(
                                    job["storage_object_path"], 3600
                                )
                                signed_url = signed.get("signedURL") or signed.get("signedUrl")
                                if signed_url:
                                    st.link_button("Download customer video (1-hour link)", signed_url)
                            except Exception:
                                st.caption("Private video download link is temporarily unavailable.")
                        elif job.get("original_filename"):
                            st.caption(f"Customer file: {job.get('original_filename')} — upload intake not finalized.")
                        try:
                            existing_meta = (
                                supabase.table("content_metadata")
                                .select("title, description, tags, hashtags, caption, metadata_details")
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
    with op_analytics:
        try:
            analytics_tenants = (
                supabase.table("tenants")
                .select("id, business_name")
                .order("created_at", desc=True)
                .limit(100)
                .execute().data or []
            )
        except Exception:
            analytics_tenants = []
        if not analytics_tenants:
            st.info("No customer workspaces are available.")
        else:
            tenant_labels = {
                row["id"]: row.get("business_name") or row["id"]
                for row in analytics_tenants
            }
            with st.form("refresh_customer_channel_analytics"):
                analytics_tenant = st.selectbox(
                    "Customer workspace",
                    list(tenant_labels),
                    format_func=lambda value: tenant_labels.get(value, value),
                )
                refresh_analytics = st.form_submit_button("Refresh YouTube analytics", type="primary")
            if refresh_analytics:
                try:
                    refreshed = refresh_youtube_analytics(analytics_tenant, supabase)
                except RuntimeError:
                    st.error("Analytics refresh failed. Confirm that this customer has connected YouTube with read-only access.")
                else:
                    st.success(f"Analytics refreshed for {refreshed.get('channel_title', 'YouTube channel')}.")
                    metric_a, metric_b, metric_c = st.columns(3)
                    metric_a.metric("Subscribers", refreshed.get("subscriber_count") if refreshed.get("subscriber_count") is not None else "Hidden")
                    metric_b.metric("Channel views", refreshed.get("view_count") if refreshed.get("view_count") is not None else "Unavailable")
                    metric_c.metric("Videos", refreshed.get("video_count") if refreshed.get("video_count") is not None else "Unavailable")
            try:
                snapshot_rows = (
                    supabase.table("channel_analytics_snapshots")
                    .select("tenant_id, channel_title, subscriber_count, view_count, video_count, captured_at")
                    .order("captured_at", desc=True)
                    .limit(100)
                    .execute().data or []
                )
                if snapshot_rows:
                    st.dataframe(snapshot_rows, use_container_width=True, hide_index=True)
                else:
                    st.caption("No analytics snapshots have been collected yet.")
            except Exception:
                st.warning("Analytics history is temporarily unavailable.")

else:
    st.divider()
    st.header("Your service")
    customer_uploads, customer_tickets, customer_billing, customer_analytics = st.tabs(["My videos & AI SEO", "Support", "Plan & billing", "Channel analytics"])
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
            # Compact upload history at the top; only one selected video gets the full editor below.
            try:
                own_jobs = (
                    supabase.table("upload_jobs")
                    .select("id, tenant_id, video_title, status, youtube_video_id, scheduled_for, original_filename, file_size_bytes, created_at")
                    .in_("tenant_id", own_tenant_ids)
                    .order("created_at", desc=True)
                    .limit(50)
                    .execute().data or []
                )
            except Exception:
                own_jobs = []
                st.warning("Your upload history is temporarily unavailable.")

            st.subheader("📁 Uploads")
            if own_jobs:
                selected_job_id = st.session_state.get("creator_selected_job_id")
                valid_ids = {str(row["id"]) for row in own_jobs}
                if selected_job_id not in valid_ids:
                    selected_job_id = str(own_jobs[0]["id"])
                    st.session_state["creator_selected_job_id"] = selected_job_id

                for offset in range(0, len(own_jobs), 4):
                    strip_cols = st.columns(4)
                    for col, job in zip(strip_cols, own_jobs[offset:offset + 4]):
                        job_id_text = str(job["id"])
                        label = (job.get("video_title") or "Video")[:22]
                        status_label = (job.get("status") or "new").replace("_", " ").title()
                        with col:
                            if st.button(
                                f"🎬 {label}\n{status_label}",
                                key=f"upload_strip_{job_id_text}",
                                type="primary" if job_id_text == selected_job_id else "secondary",
                                use_container_width=True,
                            ):
                                st.session_state["creator_selected_job_id"] = job_id_text
                                st.rerun()
                selected_job = next((row for row in own_jobs if str(row["id"]) == selected_job_id), own_jobs[0])
            else:
                selected_job = None
                st.caption("No uploads yet. Choose a video below to start.")

            st.divider()
            st.subheader("🎥 Upload one video")
            st.caption("Choose one MP4, MOV or WebM file. Gemini watches the video and prepares its SEO automatically.")
            with st.form("customer_video_intake", clear_on_submit=True):
                upload_tenant = st.selectbox("Workspace", own_tenant_ids)
                video_file = st.file_uploader("Choose video file", type=["mp4", "mov", "webm"], max_upload_size=100)
                submit_video = st.form_submit_button("⬆️ Upload video & generate AI SEO", type="primary", use_container_width=True)
            if submit_video:
                if video_file is None:
                    st.warning("Choose a video file.")
                else:
                    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(video_file.name).name)[:255]
                    file_bytes = video_file.getvalue()
                    mime_type = video_file.type or ""
                    if len(file_bytes) > 104857600:
                        st.error("This file is larger than 100 MB.")
                    elif mime_type not in {"video/mp4", "video/quicktime", "video/webm"}:
                        st.error("Use an MP4, MOV or WebM video file.")
                    else:
                        try:
                            upload_title = Path(safe_filename).stem[:100] or "New video"
                            created = supabase.rpc("create_customer_upload_job", {
                                "p_tenant": upload_tenant,
                                "p_title": upload_title,
                                "p_filename": safe_filename,
                                "p_mime": mime_type,
                                "p_size": len(file_bytes),
                            }).execute()
                            job_id = str(created.data)
                            object_path = f"{upload_tenant}/{job_id}/{safe_filename}"
                            supabase.storage.from_("customer-video-intake").upload(
                                object_path, file_bytes,
                                file_options={"content-type": mime_type, "upsert": "false"},
                            )
                            supabase.rpc("finalize_customer_video_upload", {
                                "p_job": job_id, "p_object_path": object_path,
                            }).execute()
                        except Exception:
                            st.error("Secure upload did not complete. Please retry; no YouTube publishing was started.")
                        else:
                            st.session_state["creator_selected_job_id"] = job_id
                            st.success("Video received. Gemini is analyzing the video and preparing SEO now.")
                            try:
                                customer_youtube_seo_request(
                                    "generate", job_id, supabase,
                                    {"title": upload_title, "language": "Telugu"},
                                )
                            except RuntimeError as exc:
                                st.warning(f"Video is safe. AI SEO needs a retry: {str(exc)[:130]}.")
                            else:
                                st.success("Gemini finished the video SEO. Review it below.")
                            st.rerun()

            st.divider()
            st.subheader("🤖 Selected video — AI SEO & YouTube publishing")
            if selected_job:
                job = selected_job
                st.markdown(f"**{job.get('video_title') or 'Your video'}**")
                st.caption(f"Status: {(job.get('status') or 'draft').replace('_', ' ').title()}")
                try:
                    saved_rows = (
                        supabase.table("content_metadata")
                        .select("title, description, tags, hashtags, caption, metadata_details")
                        .eq("upload_job_id", job["id"])
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute().data or []
                    )
                    saved_meta = saved_rows[0] if saved_rows else {}
                except Exception:
                    saved_meta = {}

                if not saved_meta and job.get("status") == "received":
                    st.info("Video upload complete. Gemini is ready to analyze its scenes and audio.")
                if st.button(
                    "✨ Generate YouTube SEO",
                    key=f"generate_seo_{job['id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    with st.spinner("Gemini is watching your video and preparing SEO..."):
                        try:
                            customer_youtube_seo_request(
                                "generate", job["id"], supabase,
                                {"title": job.get("video_title") or "", "language": "Telugu"},
                            )
                        except RuntimeError as exc:
                            st.error(f"AI SEO error: {str(exc)[:130]}")
                        else:
                            st.success("Gemini created your SEO. Review and save it below.")
                            st.rerun()

                if saved_meta:
                    details = saved_meta.get("metadata_details") or {}
                    title_options = details.get("title_options") or [saved_meta.get("title") or ""]
                    if len(title_options) > 1:
                        st.markdown("**AI title options**")
                        selected_title = st.radio(
                            "Choose YouTube title", title_options,
                            index=next((i for i, value in enumerate(title_options) if value == saved_meta.get("title")), 0),
                            key=f"title_options_{job['id']}",
                        )
                    else:
                        selected_title = saved_meta.get("title") or ""
                    if details.get("category"):
                        st.caption(f"YouTube category: {details.get('category')}")
                    with st.form(f"customer_seo_edit_{job['id']}"):
                        edit_title = st.text_input("YouTube title", value=selected_title, max_chars=100)
                        edit_description = st.text_area("SEO Description", value=saved_meta.get("description") or "", max_chars=5000)
                        edit_tags = st.text_area("YouTube SEO tags", value=", ".join(saved_meta.get("tags") or []))
                        edit_hashtags = st.text_input("5 Hashtags", value=", ".join("#" + x.lstrip("#") for x in (saved_meta.get("hashtags") or [])))
                        edit_caption = st.text_area("YouTube caption", value=details.get("youtube_caption") or saved_meta.get("caption") or "", max_chars=2200)
                        edit_instagram_caption = st.text_area("Instagram caption", value=details.get("instagram_caption") or "", max_chars=2200)
                        edit_keywords = st.text_area("Extra SEO keywords", value=", ".join(details.get("keywords") or []))
                        save_customer_seo = st.form_submit_button("Save my SEO edits", type="primary")
                    if save_customer_seo:
                        try:
                            customer_youtube_seo_request(
                                "save", job["id"], supabase,
                                {
                                    "title": edit_title,
                                    "description": edit_description,
                                    "tags": [x.strip() for x in edit_tags.split(",") if x.strip()],
                                    "hashtags": [x.strip().lstrip("#") for x in edit_hashtags.split(",") if x.strip()],
                                    "caption": edit_caption,
                                    "metadata_details": {
                                        **details,
                                        "title_options": title_options,
                                        "youtube_caption": edit_caption,
                                        "instagram_caption": edit_instagram_caption,
                                        "keywords": [x.strip() for x in edit_keywords.split(",") if x.strip()],
                                    },
                                },
                            )
                        except RuntimeError:
                            st.error("Your SEO edits could not be saved. Check the title and tag limits.")
                        else:
                            st.success("SEO saved.")
                            st.rerun()

                if job.get("status") == "received":
                    if saved_meta:
                        if st.button(
                            "⬆️ Upload to my YouTube channel (PRIVATE)",
                            key=f"customer_upload_youtube_{job['id']}",
                            type="primary", use_container_width=True,
                        ):
                            try:
                                upload_result = start_private_youtube_upload(job["id"], supabase)
                            except RuntimeError:
                                st.error("YouTube upload failed. Connect your channel with upload permission and retry.")
                            else:
                                st.success("Your video is uploaded as PRIVATE.")
                                if upload_result.get("youtube_url"):
                                    st.link_button("Open private YouTube video", upload_result["youtube_url"])
                                st.rerun()
                    else:
                        st.info("Generate and save SEO first. The private YouTube upload button appears after that.")
                if job.get("status") in {"uploaded_private", "approved"}:
                    st.success("Video is PRIVATE on YouTube. Choose when to publish.")
                    with st.form(f"customer_publish_action_{job['id']}"):
                        customer_publish_mode = st.radio(
                            "Publishing option", ["Publish now", "Schedule"],
                            horizontal=True, key=f"customer_publish_mode_{job['id']}",
                        )
                        if customer_publish_mode == "Schedule":
                            customer_schedule_date = st.date_input(
                                "Schedule date (IST)", value=date.today() + timedelta(days=1),
                                min_value=date.today(), key=f"customer_schedule_date_{job['id']}",
                            )
                            hour_12 = st.selectbox("Hour", list(range(1, 13)), index=8, key=f"schedule_hour_{job['id']}")
                            minute = st.selectbox("Minutes", [f"{m:02d}" for m in range(60)], index=0, key=f"schedule_minute_{job['id']}")
                            am_pm = st.selectbox("AM / PM", ["AM", "PM"], index=0, key=f"schedule_ampm_{job['id']}")
                        else:
                            customer_schedule_date = None
                            hour_12, minute, am_pm = 9, "00", "AM"
                        customer_publish_submit = st.form_submit_button("Confirm publish / schedule", type="primary")
                    if customer_publish_submit:
                        customer_publish_at = None
                        if customer_publish_mode == "Schedule" and customer_schedule_date:
                            hour_24 = (int(hour_12) % 12) + (12 if am_pm == "PM" else 0)
                            selected_time = time(hour_24, int(minute))
                            scheduled_local = datetime.combine(
                                customer_schedule_date, selected_time,
                                tzinfo=ZoneInfo("Asia/Kolkata"),
                            )
                            if scheduled_local <= datetime.now(ZoneInfo("Asia/Kolkata")):
                                st.error("Choose a future date and time in IST.")
                            else:
                                customer_publish_at = scheduled_local.isoformat()
                        if customer_publish_mode == "Publish now" or customer_publish_at:
                            try:
                                result = publish_approved_video(
                                    job["id"],
                                    "schedule" if customer_publish_mode == "Schedule" else "now",
                                    customer_publish_at, supabase,
                                )
                            except RuntimeError:
                                st.error("YouTube could not complete this action. Your video remains private; check publishing permissions and schedule time.")
                            else:
                                st.success(result.get("message", "YouTube action completed."))
                                if result.get("youtube_url"):
                                    st.link_button("Open YouTube video", result["youtube_url"])
                                st.rerun()
                elif job.get("status") == "scheduled":
                    scheduled_text = job.get("scheduled_for") or "time unavailable"
                    st.success(f"Scheduled: {scheduled_text}")
                elif job.get("status") == "published":
                    st.success("Published on YouTube.")
                elif job.get("status") == "failed":
                    st.error("This video needs attention. Please contact support.")
            else:
                st.info("Upload a video above, then select it from the small Uploads list to manage its SEO and publishing.")
    with customer_analytics:
        if not own_tenant_ids:
            st.info("Channel analytics will appear after your workspace is activated.")
        else:
            try:
                latest_analytics = (
                    supabase.table("channel_analytics_snapshots")
                    .select("channel_title, subscriber_count, view_count, video_count, captured_at")
                    .in_("tenant_id", own_tenant_ids)
                    .order("captured_at", desc=True)
                    .limit(1)
                    .execute().data or []
                )
                if latest_analytics:
                    snapshot = latest_analytics[0]
                    st.subheader(snapshot.get("channel_title") or "YouTube channel")
                    st.caption(f"Last refreshed: {snapshot.get('captured_at')}")
                    metric_a, metric_b, metric_c = st.columns(3)
                    metric_a.metric("Subscribers", snapshot.get("subscriber_count") if snapshot.get("subscriber_count") is not None else "Hidden")
                    metric_b.metric("Channel views", snapshot.get("view_count") if snapshot.get("view_count") is not None else "Unavailable")
                    metric_c.metric("Videos", snapshot.get("video_count") if snapshot.get("video_count") is not None else "Unavailable")
                else:
                    st.info("Your service team has not refreshed channel analytics yet.")
            except Exception:
                st.warning("Channel analytics are temporarily unavailable.")

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
