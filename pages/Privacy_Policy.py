from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Privacy Policy — Macherla Guru Creator Services", page_icon="🔒", layout="centered")
policy_path = Path(__file__).resolve().parents[1] / "PRIVACY_POLICY_DRAFT.md"
st.markdown(policy_path.read_text(encoding="utf-8"))
