import streamlit as st
from helpers import get_redis

st.set_page_config(page_title="System Settings", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("⚙️ System Settings")

# Password Update
with st.expander("🔐 Change Admin Password"):
    new_p = st.text_input("New Password", type="password")
    if st.button("Update Password"):
        r.set("admin_password", new_p)
        st.success("Password Updated.")

# PB Age Mode
curr_mode = r.get("age_mode") or "10Y"
new_mode = st.radio("Standard PB Age Banding", ["10Y", "5Y"], index=0 if curr_mode == "10Y" else 1)
if st.button("Save Banding"):
    r.set("age_mode", new_mode); st.success("Saved.")

# Logo
curr_logo = r.get("club_logo_url") or ""
new_logo = st.text_input("Logo URL", value=curr_logo)
if st.button("Save Logo"):
    r.set("club_logo_url", new_logo); st.success("Saved.")

# Champ Toggle
curr_v = r.get("show_champ_tab") == "True"
if st.toggle("Show Champ Tab Publicly", value=curr_v):
    r.set("show_champ_tab", "True")
else:
    r.set("show_champ_tab", "False")
