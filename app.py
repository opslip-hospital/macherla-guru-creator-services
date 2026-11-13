"""Macherla Guru Creator Services — secure foundation UI.

This intentionally does not expose customer or admin data until verified
server-side authentication and tenant-scoped persistence are configured.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

APP_NAME = os.getenv("APP_NAME", "Macherla Guru Creator Services")
REQUIRED_AUTH = ("AUTH_ISSUER_URL", "AUTH_AUDIENCE", "AUTH_JWKS_URL")
auth_ready = all(os.getenv(key, "").strip() for key in REQUIRED_AUTH)

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

if not auth_ready:
    st.warning("Secure sign-in is not configured yet. Customer and admin workspaces are locked.")
    st.markdown(
        """
        **Foundation setup checklist**
        - Configure a trusted authentication provider and verify JWT signatures server-side.
        - Add a managed PostgreSQL database with tenant-level row security.
        - Configure Google OAuth for YouTube using the minimum required scopes.
        - Add audit logging and test customer-to-customer isolation.
        """
    )
    st.stop()

# Fail closed until a verified authentication integration is implemented.
# Never trust a role, customer ID, or email supplied by a browser form/session state.
st.error(
    "Authentication settings are present, but the verified sign-in integration "
    "has not been implemented. Access remains locked by design."
)
st.stop()
