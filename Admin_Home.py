import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_category, get_club_logo

st.set_page_config(page_title="AutoKudos Admin", layout="wide")
r = get_redis()

# --- 1. AUTHENTICATION ---
with st.sidebar:
    st.image(get_club_logo(r), width=150)
    admin_pwd = r.get("admin_password") or "admin123"
    pwd_input = st.text_input("Admin Password", type="password")
    is_auth = (pwd_input == admin_pwd)
    st.session_state['authenticated'] = is_auth

# --- 2. SIDEBAR LOCK ---
if not st.session_state['authenticated']:
    st.markdown("""
        <style>
        [data-testid="stSidebarNav"] ul li:nth-child(n+2) { display: none; }
        </style>
    """, unsafe_allow_html=True)
    st.title("🏆 Leaderboard View")
else:
    st.title("🛡️ AutoKudos Dashboard")
    st.success("Admin Access Granted")

# --- 3. LEADERBOARD (Always visible on Home) ---
raw_res = r.lrange("race_results", 0, -1)
if raw_res:
    df = pd.DataFrame([json.loads(res) for res in raw_res])
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    age_mode = r.get("age_mode") or "10Y"
    df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

    dist = st.selectbox("Select Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"])
    m_col, f_col = st.columns(2)
    for gen, col in [("Male", m_col), ("Female", f_col)]:
        with col:
            st.subheader(gen)
            sub = df[(df['distance'] == dist) & (df['gender'] == gen)]
            if not sub.empty:
                leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                st.table(leaders[['Category', 'name', 'time_display', 'race_date']])
else:
    st.info("No records found.")
