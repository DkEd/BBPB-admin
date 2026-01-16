import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings, get_category

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

# --- SIDEBAR LOGIN ---
st.sidebar.image(settings['logo_url'], width=150)
st.sidebar.title("🛡️ Admin Access")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

stored_password = r.get("admin_password") or "admin123"
pwd_input = st.sidebar.text_input("Password", type="password")
if st.sidebar.button("Login"):
    if pwd_input == stored_password:
        st.session_state['authenticated'] = True
        st.rerun()
    else:
        st.sidebar.error("Incorrect Password")

if st.session_state['authenticated']:
    if st.sidebar.button("Logout"):
        st.session_state['authenticated'] = False
        st.rerun()

# --- MAIN LEADERBOARD ---
st.title("🏃 Club PB Leaderboard (Admin View)")

raw_results = r.lrange("race_results", 0, -1)
raw_members = r.lrange("members", 0, -1)

if not raw_results:
    st.info("No records found in the database.")
else:
    df_results = pd.DataFrame([json.loads(res) for res in raw_results])
    df_members = pd.DataFrame([json.loads(m) for m in raw_members])
    age_mode = settings['age_mode']

    if not df_members.empty:
        df_merged = df_results.merge(df_members[['name', 'gender', 'dob']], on='name', how='left')
        df_merged = df_merged.dropna(subset=['dob'])
        df_merged['category'] = df_merged.apply(lambda x: get_category(x['dob'], x['race_date'], mode=age_mode), axis=1)
    else:
        df_merged = df_results
        df_merged['category'] = "Unk"

    df_merged = df_merged.sort_values(['name', 'distance', 'time_display'])
    pbs = df_merged.groupby(['name', 'distance']).head(1)

    tabs = st.tabs(["5k", "10k", "10 Mile", "HM", "Marathon", "🔍 Runner Search"])
    distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

    for i, dist in enumerate(distances):
        with tabs[i]:
            dist_df = pbs[pbs['distance'] == dist].copy()
            if not dist_df.empty:
                for gender in ["Female", "Male"]:
                    st.markdown(f"#### {gender}")
                    g_df = dist_df[dist_df['gender'] == gender].sort_values('time_display')
                    st.dataframe(
                        g_df[['name', 'category', 'time_display', 'location', 'race_date']].rename(columns={
                            'name': 'Runner', 'category': 'Cat', 'time_display': 'Time', 'location': 'Race'
                        }),
                        use_container_width=True, hide_index=True
                    )

    with tabs[5]:
        st.subheader("Search Member History")
        all_names = sorted(df_members['name'].unique().tolist()) if not df_members.empty else []
        search_name = st.selectbox("Select Runner", [""] + all_names)
        if search_name:
            history = df_merged[df_merged['name'] == search_name].sort_values('race_date', ascending=False)
            st.dataframe(
                history[['race_date', 'distance', 'time_display', 'location', 'category']],
                use_container_width=True, hide_index=True
            )
