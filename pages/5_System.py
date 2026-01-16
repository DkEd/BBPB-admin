import streamlit as st
import pandas as pd
import json
from helpers import get_redis

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("⚙️ System Tools")
# Age Mode
mode = r.get("age_mode") or "10Y"
new_mode = st.radio("Age Mode", ["10Y", "5Y"], index=0 if mode=="10Y" else 1)
if st.button("Save Age Mode"): r.set("age_mode", new_mode)

st.divider()
# Exports
if st.button("Generate PB Backup"):
    df = pd.DataFrame([json.loads(x) for x in r.lrange("race_results", 0, -1)])
    st.download_button("Download CSV", df.to_csv(index=False), "pb_backup.csv")

st.divider()
# Password
new_pwd = st.text_input("New Admin Password", type="password")
if st.button("Update Password"): r.set("admin_password", new_pwd); st.success("Updated")
