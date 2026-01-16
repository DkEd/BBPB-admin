import streamlit as st
import json
import pandas as pd
from helpers import get_redis, get_club_settings

st.set_page_config(page_title="System Settings", layout="wide")
r = get_redis()
settings = get_club_settings()

if not st.session_state.get('authenticated'):
    st.warning("Please login on the Home page.")
    st.stop()

st.header("⚙️ System Management")

tabs = st.tabs(["🔧 General Settings", "📥 Bulk Upload", "💾 Backup & Export"])

# --- TAB 1: GENERAL SETTINGS ---
with tabs[0]:
    st.subheader("Club Configuration")
    with st.form("settings_form"):
        col1, col2 = st.columns(2)
        
        new_age_mode = col1.selectbox(
            "Age Category Mode", 
            ["5 Year", "10 Year"], 
            index=0 if settings['age_mode'] == "5 Year" else 1,
            help="Determines if categories are V40, V45... or V40, V50..."
        )
        
        new_logo = col2.text_input("Logo URL", settings['logo_url'])
        new_pass = st.text_input("Change Admin Password", type="password", placeholder="Leave blank to keep current")
        
        if st.form_submit_button("Save System Settings"):
            updated = {
                "age_mode": new_age_mode,
                "logo_url": new_logo,
                "admin_password": new_pass if new_pass else settings['admin_password']
            }
            r.set("club_settings", json.dumps(updated))
            st.success("Settings updated successfully!")
            st.rerun()

# --- TAB 2: BULK UPLOAD ---
with tabs[1]:
    st.subheader("Bulk Data Import")
    st.caption("Upload CSV files to populate your database. Ensure headers match exactly.")
    
    # Member Upload
    with st.expander("👥 Bulk Upload Members"):
        m_file = st.file_uploader("Upload Members CSV (name, dob, gender, status)", type="csv", key="m_up")
        if m_file:
            m_df = pd.read_csv(m_file)
            if st.button("Process Members"):
                for _, row in m_df.iterrows():
                    m_data = {"name": row['name'], "dob": str(row['dob']), "gender": row['gender'], "status": row.get('status', 'Active')}
                    r.rpush("members", json.dumps(m_data))
                st.success(f"Imported {len(m_df)} members!")

    # Race Upload
    with st.expander("🏃 Bulk Upload Race Results (PBs)"):
        r_file = st.file_uploader("Upload Races CSV (name, distance, location, race_date, time_display, time_seconds, gender, dob)", type="csv", key="r_up")
        if r_file:
            r_df = pd.read_csv(r_file)
            if st.button("Process Races"):
                for _, row in r_df.iterrows():
                    r_data = row.to_dict()
                    r.rpush("race_results", json.dumps(r_data))
                st.success(f"Imported {len(r_df)} race records!")

    # Championship Upload
    with st.expander("🏅 Bulk Upload Championship Results"):
        c_file = st.file_uploader("Upload Champ CSV (name, race_name, date, time_display, points, category)", type="csv", key="c_up")
        if c_file:
            c_df = pd.read_csv(c_file)
            if st.button("Process Champ Results"):
                for _, row in c_df.iterrows():
                    c_data = row.to_dict()
                    r.rpush("champ_results_final", json.dumps(c_data))
                st.success(f"Imported {len(c_df)} championship scores!")

# --- TAB 3: BACKUP & EXPORT ---
with tabs[2]:
    st.subheader("Export Data (CSV)")
    st.info("Download your data regularly to keep a local backup.")
    
    col1, col2, col3 = st.columns(3)
    
    # Export Members
    raw_m = r.lrange("members", 0, -1)
    if raw_m:
        df_m = pd.DataFrame([json.loads(m) for m in raw_m])
        col1.download_button("📥 Download Members", df_m.to_csv(index=False), "bbpb_members.csv", "text/csv")
    
    # Export Races
    raw_r = r.lrange("race_results", 0, -1)
    if raw_r:
        df_r = pd.DataFrame([json.loads(x) for x in raw_r])
        col2.download_button("📥 Download All Races", df_r.to_csv(index=False), "bbpb_races.csv", "text/csv")

    # Export Championship
    raw_c = r.lrange("champ_results_final", 0, -1)
    if raw_c:
        df_c = pd.DataFrame([json.loads(x) for x in raw_c])
        col3.download_button("📥 Download Champ Log", df_c.to_csv(index=False), "bbpb_championship.csv", "text/csv")

    st.divider()
    if st.button("🔴 Clear All Cache", help="This does not delete data, just clears Streamlit's UI cache"):
        st.cache_data.clear()
        st.success("Cache cleared!")
