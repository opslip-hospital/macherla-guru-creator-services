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
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", os.getenv("SUPABASE_ANON_KEY", "")).strip()
SUPABASE_FUNCTIONS_URL = f"{SUPABASE_URL.rstrip('/')}/functions/v1" if SUPABASE_URL else ""

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Clear every prior customer's widget value on the next run, before widgets are
# instantiated. This prevents auto-generated Streamlit widget keys from leaking
# drafts or form values between sign-ins in the same browser session.
if st.session_state.pop("_creator_clear_all_state", False):
    for _session_key in list(st.session_state.keys()):
        st.session_state.pop(_session_key, None)

st.title("🎬 Macherla Guru Creator Services")
st.caption("One video • Gemini SEO • Private YouTube upload • IST scheduling")
st.markdown(
    "Upload one video first. Gemini prepares your SEO title, description, tags, five hashtags and captions. "
    "You can do this before connecting a YouTube channel; connect later for private upload and IST scheduling. "
    "Review and save every AI suggestion before continuing."
)
st.page_link("pages/Privacy_Policy.py", label="Privacy Policy")
st.page_link("pages/Terms_of_Service.py", label="Terms of Service")


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
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
        except (ValueError, AttributeError):
            error_payload = {}
        if error_payload.get("error") in ("youtube_upload_status_sync_failed", "youtube_upload_status_unknown"):
            video_id = str(error_payload.get("youtube_video_id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
                video_id = ""
            error_code = str(error_payload.get("error"))
            raise RuntimeError(f"{error_code}:{video_id}") from None
        raise RuntimeError("private_upload_failed") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("youtube_upload_status_unknown") from None
    except (ValueError, RuntimeError, AttributeError):
        raise RuntimeError("private_upload_failed") from None


def publish_approved_video(
    job_id: str, mode: str, publish_at: str | None, client: Client
) -> dict[str, Any]:
    """Schedule an already-private video only through the trusted Edge Function."""
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
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
        except (ValueError, AttributeError):
            error_payload = {}
        if error_payload.get("error") == "publish_status_sync_failed":
            video_id = str(error_payload.get("youtube_video_id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
                video_id = ""
            raise RuntimeError(f"publish_status_sync_failed:{video_id}") from None
        if error_payload.get("error") == "publish_status_unknown":
            raise RuntimeError("publish_status_unknown") from None
        raise RuntimeError("publish_failed") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("publish_status_unknown") from None
    except (ValueError, RuntimeError, AttributeError):
        raise RuntimeError("publish_failed") from None


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
            retry_after = int(body.get("retry_after_seconds") or 0)
            provider_code = str(body.get("provider_code") or "")
            provider_message = str(body.get("provider_message") or "")
        except Exception:
            detail, stage, provider_status, retry_after, provider_code, provider_message = "seo_request_failed", "", "", 0, "", ""
        if detail == "youtube_upload_connection_required":
            raise RuntimeError("SEO drafts can be prepared with your workspace brand. Connect YouTube later for private upload and scheduling.") from None
        if detail == "ai_rate_limit_exceeded":
            raise RuntimeError(f"AI generation limit reached. Try again in {max(1, (retry_after + 59) // 60)} minutes.") from None
        if detail == "ai_rate_limit_check_failed":
            raise RuntimeError("AI usage limit check is temporarily unavailable. Please try again shortly.") from None
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
    # Clear all widget values on the next run, before any widgets are recreated.
    st.session_state["_creator_clear_all_state"] = True


def format_scheduled_time(value: str | None) -> str:
    """Render stored UTC/ISO schedule timestamps in the customer's 12-hour IST format."""
    if not value:
        return "time unavailable"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
    except (TypeError, ValueError):
        return str(value)


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
        "SUPABASE_PUBLISHABLE_KEY (or legacy SUPABASE_ANON_KEY) is configured in deployment secrets."
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
            for tenant_row in tenants:
                with st.container(border=True):
                    st.write(f"**{tenant_row.get('business_name') or 'Customer workspace'}**")
                    st.caption(f"Workspace ID: {tenant_row['id']} • Created: {tenant_row.get('created_at')}")
                    status_values = ["pending", "active", "suspended", "closed"]
                    current_status = tenant_row.get("status") if tenant_row.get("status") in status_values else "pending"
                    with st.form(f"workspace_status_{tenant_row['id']}"):
                        next_status = st.selectbox("Workspace access", status_values, index=status_values.index(current_status))
                        update_workspace = st.form_submit_button("Save workspace status")
                    if update_workspace and next_status != current_status:
                        try:
                            supabase.rpc("admin_update_tenant_status", {
                                "p_tenant": tenant_row["id"], "p_status": next_status
                            }).execute()
                        except Exception:
                            st.error("Workspace status could not be updated.")
                        else:
                            st.success(f"Workspace status changed to {next_status}.")
                            st.rerun()
                    st.caption("Active = customer can use the service • Suspended = access paused • Closed = workspace closed")
        else:
            st.info("No customer workspaces have been provisioned yet.")
    except Exception:
        st.error("Admin access could not be verified for the workspace list.")
    st.info(
        "Customer AI SEO generation and self-service YouTube upload/publish workflows are deployed in code. "
        "Live Gemini and YouTube actions still need a successful end-to-end test. Payment processing is not enabled."
    )
else:
    # One-column customer journey: upload -> Gemini SEO -> thumbnail -> disclosure -> private upload/schedule.
    try:
        memberships = (
            supabase.table("tenant_memberships")
            .select("tenant_id")
            .eq("user_id", user_id)
            .execute().data or []
        )
        own_tenant_ids = [row["tenant_id"] for row in memberships if row.get("tenant_id")]
        own_tenant_rows = (
            supabase.table("tenants")
            .select("id, status, business_name")
            .in_("id", own_tenant_ids)
            .execute().data or []
        ) if own_tenant_ids else []
        active_tenant_rows = [row for row in own_tenant_rows if row.get("status") == "active"]
        active_tenant_ids = [row["id"] for row in active_tenant_rows if row.get("id")]
        selected_active_tenant_id = active_tenant_ids[0] if active_tenant_ids else None
    except Exception:
        own_tenant_ids, own_tenant_rows, active_tenant_rows, active_tenant_ids = [], [], [], []
        selected_active_tenant_id = None
        st.error("Your customer workspace could not be loaded. Please retry.")

    st.header("🎬 ఒక్క వీడియో ఇవ్వు — మిగతావన్నీ Gemini సిద్ధం చేస్తుంది")
    if not own_tenant_ids:
        st.info("Your customer workspace is waiting for activation by the service team.")
    elif not active_tenant_ids:
        st.info("Your workspace is not active yet. Upload and scheduling will be available after activation.")
    else:
        try:
            channel_connections = supabase.rpc(
                "list_tenant_youtube_connections",
                {"target_tenant": selected_active_tenant_id},
            ).execute().data or []
        except Exception:
            channel_connections = []
        upload_scope = "https://www.googleapis.com/auth/youtube.upload"
        upload_connection = next(
            (row for row in channel_connections if upload_scope in (row.get("granted_scopes") or [])),
            None,
        )
        has_upload_permission = upload_connection is not None

        try:
            own_jobs = (
                supabase.table("upload_jobs")
                .select("id, tenant_id, video_title, status, youtube_video_id, scheduled_for, original_filename, file_size_bytes, created_at")
                .in_("tenant_id", own_tenant_ids)
                .order("created_at", desc=True)
                .limit(1)
                .execute().data or []
            )
        except Exception:
            own_jobs = []
            st.warning("Your latest video is temporarily unavailable.")
        selected_job = own_jobs[0] if own_jobs else None
        saved_meta: dict[str, Any] = {}
        if selected_job:
            st.session_state["creator_selected_job_id"] = str(selected_job["id"])
            try:
                saved_rows = (
                    supabase.table("content_metadata")
                    .select("title, description, tags, hashtags, caption, metadata_details")
                    .eq("upload_job_id", selected_job["id"])
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute().data or []
                )
                saved_meta = saved_rows[0] if saved_rows else {}
            except Exception:
                saved_meta = {}

        pending_seo_job_id = st.session_state.get("creator_pending_seo_job_id")
        if (
            selected_job
            and selected_job.get("status") == "received"
            and not saved_meta
            and not pending_seo_job_id
        ):
            pending_seo_job_id = str(selected_job["id"])
            st.session_state["creator_pending_seo_job_id"] = pending_seo_job_id

        # 1. Video upload
        st.subheader("1. Video upload")
        video_file = st.file_uploader(
            "నీ వీడియో ఎంచుకోండి",
            type=["mp4", "mov", "avi", "webm"],
            max_upload_size=50,
            key="customer_video_file_50mb",
            help="MP4, MOV, AVI లేదా WEBM • గరిష్ఠంగా 50 MB",
        )

        # 2. Gemini generation. The consent and per-workspace rate limit remain in force.
        st.subheader("2. Gemini — Title, SEO, Tags & Captions")
        gemini_video_consent = st.checkbox(
            "I consent to send this video to Google Gemini to create captions, SEO, tags and hashtags. The current Gemini API Free Tier may use submitted content to improve Google products. I confirm I have the rights to share this video.",
            value=False,
            key="gemini_video_consent_single_flow",
        )
        st.caption("Gemini SEO limit: up to 5 video generations per workspace per hour.")
        create_seo_clicked = st.button(
            "✨ ఈ వీడియో చూసి Title, SEO, Tags, Captions తయారు చేయి",
            type="primary",
            use_container_width=True,
            disabled=video_file is None and not pending_seo_job_id,
            key="create_video_seo_single_action",
        )
        if create_seo_clicked:
            if not gemini_video_consent:
                st.warning("Please confirm Gemini consent before sending the video.")
            else:
                try:
                    if pending_seo_job_id:
                        job_id = str(pending_seo_job_id)
                        upload_title = str((selected_job or {}).get("video_title") or "New video")[:100]
                    elif video_file is None:
                        st.warning("Choose a video file first.")
                        job_id = ""
                    else:
                        safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(video_file.name).name)[:255]
                        file_bytes = video_file.getvalue()
                        extension = Path(safe_filename).suffix.lower()
                        mime_by_extension = {
                            ".mp4": "video/mp4", ".mov": "video/quicktime",
                            ".avi": "video/x-msvideo", ".webm": "video/webm",
                        }
                        mime_type = mime_by_extension.get(extension, "")
                        if len(file_bytes) > 52428800:
                            raise RuntimeError("This video exceeds the 50 MB limit.")
                        if not mime_type:
                            raise RuntimeError("Use an MP4, MOV, AVI or WEBM video file.")
                        upload_title = Path(safe_filename).stem[:100] or "New video"
                        created = supabase.rpc("create_customer_upload_job", {
                            "p_tenant": selected_active_tenant_id,
                            "p_title": upload_title,
                            "p_filename": safe_filename,
                            "p_mime": mime_type,
                            "p_size": len(file_bytes),
                        }).execute()
                        job_id = str(created.data)
                        object_path = f"{selected_active_tenant_id}/{job_id}/{safe_filename}"
                        supabase.storage.from_("customer-video-intake").upload(
                            object_path, file_bytes,
                            file_options={"content-type": mime_type, "upsert": "false"},
                        )
                        supabase.rpc("finalize_customer_video_upload", {
                            "p_job": job_id, "p_object_path": object_path,
                        }).execute()
                        st.session_state["creator_pending_seo_job_id"] = job_id
                    if job_id:
                        st.session_state["creator_selected_job_id"] = job_id
                        with st.spinner("Gemini is watching your video and preparing Title, SEO, Tags and Captions..."):
                            customer_youtube_seo_request(
                                "generate", job_id, supabase,
                                {"title": upload_title, "language": "Telugu", "ai_consent": True},
                            )
                        st.session_state.pop("creator_pending_seo_job_id", None)
                        st.success("Gemini prepared your metadata. Review and edit it in Step 5.")
                        st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc)[:220])
                except Exception:
                    st.error("Video upload or Gemini generation failed. Your workspace data remains protected. Retry the same step; do not upload again if the video is already saved.")

        # 3–5 appear once Gemini has generated metadata for the current video.
        if selected_job and saved_meta and selected_job.get("status") == "received":
            st.subheader("3. Thumbnail upload (optional)")
            st.caption("JPG/PNG • maximum 2 MB. YouTube may ignore files over 2 MB.")
            with st.form(f"customer_final_private_upload_{selected_job['id']}"):
                details = saved_meta.get("metadata_details") or {}
                st.subheader("Review your Gemini details")
                edit_title = st.text_input(
                    "Title", value=saved_meta.get("title") or selected_job.get("video_title") or "",
                    max_chars=100,
                )
                edit_hashtags = st.text_input(
                    "5 Hashtags",
                    value=", ".join("#" + str(x).lstrip("#") for x in (saved_meta.get("hashtags") or [])),
                )
                edit_description = st.text_area(
                    "Description", value=saved_meta.get("description") or "", max_chars=5000,
                )
                edit_tags = st.text_area(
                    "Tags", value=", ".join(saved_meta.get("tags") or []),
                )
                edit_caption = st.text_area(
                    "Captions", value=details.get("youtube_caption") or saved_meta.get("caption") or "",
                    max_chars=2200,
                )
                st.subheader("3. Thumbnail upload (optional)")
                st.caption("JPG/PNG • maximum 2 MB. YouTube may ignore files over 2 MB.")
                thumbnail_file = st.file_uploader(
                    "Thumbnail image (ఐచ్ఛికం)",
                    type=["jpg", "jpeg", "png"],
                    max_upload_size=2,
                    key=f"customer_thumbnail_{selected_job['id']}",
                )
                st.subheader("4. YouTube disclosure")
                contains_synthetic_media = st.checkbox(
                    "AI-generated / altered realistic content (YouTube disclosure)",
                    value=True,
                    key=f"contains_synthetic_media_{selected_job['id']}",
                )
                st.subheader("5. Private YouTube upload")
                if not has_upload_permission:
                    st.info("Connect your YouTube channel to enable the private upload. Your Gemini draft is already saved.")
                    if st.form_submit_button("Connect / reconnect YouTube channel", use_container_width=True):
                        try:
                            google_url = start_youtube_oauth(selected_active_tenant_id, supabase)
                        except RuntimeError:
                            st.error("Google connection could not be started. Please contact the service administrator.")
                        else:
                            st.link_button("Continue securely with Google", google_url, type="primary")
                final_upload_clicked = st.form_submit_button(
                    "🔒 Review చేసిన వివరాలతో Privateగా Upload చేయి",
                    type="primary",
                    use_container_width=True,
                    disabled=not has_upload_permission,
                )
            if final_upload_clicked and has_upload_permission:
                try:
                    if len(edit_title.strip()) > 100 or not edit_title.strip():
                        raise RuntimeError("Title is required and must be 100 characters or fewer.")
                    thumbnail_bytes = thumbnail_file.getvalue() if thumbnail_file is not None else None
                    if thumbnail_bytes is not None and len(thumbnail_bytes) > 2097152:
                        raise RuntimeError("Thumbnail must be 2 MB or smaller.")
                    details = saved_meta.get("metadata_details") or {}
                    customer_youtube_seo_request(
                        "save", str(selected_job["id"]), supabase,
                        {
                            "title": edit_title.strip(),
                            "description": edit_description,
                            "tags": [x.strip() for x in edit_tags.split(",") if x.strip()],
                            "hashtags": [x.strip().lstrip("#") for x in edit_hashtags.split(",") if x.strip()],
                            "caption": edit_caption,
                            "metadata_details": {
                                **details,
                                "title_options": details.get("title_options") or [edit_title.strip()],
                                "youtube_caption": edit_caption,
                            },
                        },
                    )
                    thumbnail_path = None
                    if thumbnail_bytes is not None:
                        thumbnail_ext = Path(thumbnail_file.name).suffix.lower()
                        thumbnail_name = "thumbnail.png" if thumbnail_ext == ".png" else "thumbnail.jpg"
                        thumbnail_path = f"{selected_active_tenant_id}/{selected_job['id']}/{thumbnail_name}"
                        thumbnail_mime = "image/png" if thumbnail_name.endswith(".png") else "image/jpeg"
                        supabase.storage.from_("customer-video-intake").upload(
                            thumbnail_path, thumbnail_bytes,
                            file_options={"content-type": thumbnail_mime, "upsert": "true"},
                        )
                    supabase.rpc("set_customer_upload_assets", {
                        "p_job": str(selected_job["id"]),
                        "p_thumbnail_path": thumbnail_path,
                        "p_contains_synthetic_media": bool(contains_synthetic_media),
                    }).execute()
                    with st.spinner("Uploading your reviewed video to YouTube as PRIVATE..."):
                        upload_result = start_private_youtube_upload(str(selected_job["id"]), supabase)
                    st.session_state["creator_private_upload_success_job_id"] = str(selected_job["id"])
                    st.success("Your video was uploaded to YouTube as PRIVATE.")
                    if upload_result.get("thumbnail_requested") and upload_result.get("thumbnail_applied"):
                        st.success("Your custom thumbnail was applied.")
                    elif upload_result.get("thumbnail_requested"):
                        st.warning("The video is private; YouTube did not confirm the thumbnail. You can set it in YouTube Studio.")
                    if upload_result.get("youtube_url"):
                        st.link_button("Open private YouTube video", upload_result["youtube_url"])
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc)[:220])
                except Exception:
                    st.error("Private upload failed. The video remains in your secure workspace; check YouTube status before retrying.")

        elif selected_job and not saved_meta and selected_job.get("status") == "received":
            st.info("Your video is saved securely. Complete Step 2 to let Gemini create its metadata.")
        elif not selected_job:
            st.info("Choose your video in Step 1. The Gemini button becomes available after you select it.")

        # Schedule remains attached to the same private-uploaded video.
        if selected_job and selected_job.get("status") in {"uploaded_private", "approved"}:
            st.success("Your video is PRIVATE on YouTube. Choose its schedule time below.")
            with st.form(f"customer_publish_action_{selected_job['id']}"):
                customer_schedule_date = st.date_input(
                    "Schedule date (IST)",
                    value=datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=1),
                    min_value=datetime.now(ZoneInfo("Asia/Kolkata")).date(),
                    key=f"customer_schedule_date_{selected_job['id']}",
                )
                hour_12 = st.selectbox(
                    "Hour", list(range(1, 13)), index=8,
                    key=f"schedule_hour_{selected_job['id']}",
                )
                minute = st.selectbox(
                    "Minutes", [f"{m:02d}" for m in range(60)], index=0,
                    key=f"schedule_minute_{selected_job['id']}",
                )
                am_pm = st.selectbox(
                    "AM / PM", ["AM", "PM"], index=0,
                    key=f"schedule_ampm_{selected_job['id']}",
                )
                customer_publish_submit = st.form_submit_button("📅 Confirm Schedule", type="primary")
            if customer_publish_submit and customer_schedule_date:
                hour_24 = (int(hour_12) % 12) + (12 if am_pm == "PM" else 0)
                selected_time = time(hour_24, int(minute))
                scheduled_local = datetime.combine(
                    customer_schedule_date, selected_time,
                    tzinfo=ZoneInfo("Asia/Kolkata"),
                )
                if scheduled_local < datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(minutes=15):
                    st.error("Choose a schedule time at least 15 minutes in the future (IST).")
                else:
                    try:
                        result = publish_approved_video(
                            str(selected_job["id"]), "schedule", scheduled_local.isoformat(), supabase,
                        )
                    except RuntimeError as exc:
                        if str(exc).startswith("publish_status_sync_failed"):
                            st.warning("YouTube accepted the schedule action, but the dashboard could not confirm it. Check YouTube Studio before retrying.")
                            video_id = str(exc).partition(":")[2]
                            if video_id:
                                st.link_button("Open YouTube video", f"https://www.youtube.com/watch?v={video_id}")
                        elif str(exc) == "publish_status_unknown":
                            st.warning("The scheduling response was interrupted. YouTube may already have accepted it. Check YouTube Studio before retrying; do not repeat the action.")
                            existing_video_id = str(selected_job.get("youtube_video_id") or "")
                            if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", existing_video_id):
                                st.link_button("Open YouTube video to check status", f"https://www.youtube.com/watch?v={existing_video_id}")
                        else:
                            st.error("YouTube could not schedule this video. It remains private; check scheduling permissions and selected time.")
                    else:
                        st.success(result.get("message", "Your video has been scheduled."))
                        if result.get("youtube_url"):
                            st.link_button("Open scheduled YouTube video", result["youtube_url"])
                        st.rerun()
        elif selected_job and selected_job.get("status") == "scheduled":
            st.success(f"Scheduled: {format_scheduled_time(selected_job.get('scheduled_for'))}")
        elif selected_job and selected_job.get("status") == "published":
            st.success("Published on YouTube.")
        elif selected_job and selected_job.get("status") == "upload_unknown":
            st.error("YouTube may have accepted the upload. Check YouTube Studio before retrying; this job is locked to prevent duplicate uploads.")
        elif selected_job and selected_job.get("status") == "publishing":
            st.warning("The schedule request may still be processing. Check YouTube Studio before retrying.")
