import streamlit as st
import pandas as pd
import json
from helpers import get_redis, time_to_seconds, format_time_string

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()
if not st.session_state.get('authenticated'): 
    st.error("Please login on the Home page.")
    st.stop()

st.header("⚙️ System Tools & Settings")

# --- PUBLIC VISIBILITY CONTROL ---
st.subheader("🌐 Public Site Controls")
current_viz = r.get("show_champ_tab") == "True"
if st.toggle("Show Championship Page on Public Site", value=current_viz):
    r.set("show_champ_tab", "True")
else:
    r.set("show_champ_tab", "False")

st.divider()

# --- BRANDING & LOGO ---
col_logo, col_age = st.columns(2)
with col_logo:
    new_logo = st.text_input("Club Logo URL", value=r.get("club_logo_url") or "")
    if st.button("Save Logo"):
        r.set("club_logo_url", new_logo); st.success("Logo Updated")
with col_age:
    mode = r.get("age_mode") or "10Y"
    new_mode = st.radio("Age Banding", ["10Y", "5Y"], index=0 if mode=="10Y" else 1)
    if st.button("Save Banding"):
        r.set("age_mode", new_mode); st.success("Banding Saved")

st.divider()

# --- BULK DATA TOOLS ---
st.subheader("📤 Bulk Uploads")
c1, c2 = st.columns(2)
with c1:
    m_file = st.file_uploader("Upload Members CSV", type="csv")
    if m_file and st.button("Import Members"):
        df_m = pd.read_csv(m_file)
        for _, row in df_m.iterrows():
            r.rpush("members", json.dumps({"name":row['name'], "gender":row['gender'], "dob":str(row['dob']), "status":"Active"}))
        st.success("Imported!")
with c2:
    r_file = st.file_uploader("Upload PBs CSV", type="csv")
    if r_file and st.button("Import PBs"):
        m_list = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
        df_r = pd.read_csv(r_file)
        for _, row in df_r.iterrows():
            if row['name'] in m_list:
                m = m_list[row['name']]
                entry = {"name":row['name'], "gender":m['gender'], "dob":m['dob'], "distance":row['distance'], "time_seconds":time_to_seconds(row['time']), "time_display":format_time_string(row['time']), "location":row['location'], "race_date":str(row['date'])}
                r.rpush("race_results", json.dumps(entry))
        st.success("PBs Imported!")
