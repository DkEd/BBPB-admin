import streamlit as st
import pandas as pd
import json
from helpers import get_redis, format_time_string, time_to_seconds

st.set_page_config(layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page.")
    st.stop()

st.header("⚙️ System Tools")

# Age Mode
curr_mode = r.get("age_mode") or "10Y"
new_mode = st.radio("Age Category Mode", ["10Y", "5Y"], index=0 if curr_mode=="10Y" else 1)
if st.button("Save Age Mode"):
    r.set("age_mode", new_mode)
    st.success("Mode updated.")

st.divider()

# Downloads
st.subheader("💾 Backups")
if st.button("Generate Download Links"):
    res_df = pd.DataFrame([json.loads(x) for x in r.lrange("race_results", 0, -1)])
    st.download_button("📥 Download All PBs (CSV)", res_df.to_csv(index=False), "all_pbs.csv")

st.divider()

# Password Reset
st.subheader("🔑 Security")
new_pwd = st.text_input("New Admin Password", type="password")
if st.button("Change Password"):
    r.set("admin_password", new_pwd)
    st.success("Password changed.")
