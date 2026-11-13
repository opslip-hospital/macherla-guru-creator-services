from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Terms of Service — Macherla Guru Creator Services", page_icon="📄", layout="centered")
terms_path = Path(__file__).resolve().parents[1] / "TERMS_OF_SERVICE_DRAFT.md"
st.markdown(terms_path.read_text(encoding="utf-8"))
