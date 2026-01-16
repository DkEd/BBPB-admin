import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings, get_category

# 1. Page Setup
st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

# 2. Sidebar Login
st.sidebar.image(settings['logo_url'], width=150)
st.sidebar.title("🛡️ Admin Access")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    stored_password = r.get("admin_password") or "admin123"
    pwd_input = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == stored_password:
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.sidebar.error("Incorrect Password")
else:
    st.sidebar.success("Logged In")
    if st.sidebar.button("Logout"):
        st.session_state['authenticated'] = False
        st.rerun()

# 3. Main Dashboard Header
st.title("🏃 Club PB Leaderboard (Admin View)")

# 4. Load Data for the Preview
raw_results = r.lrange("race_results", 0, -1)
raw_members = r.lrange("members", 0, -1)

if not raw_results:
    st.info("No records found in the database.")
else:
    df_results = pd.DataFrame([json.loads(res) for res in raw_results])
    df_members = pd.DataFrame([json.loads(m) for m in raw_members])

    # Category Logic (uses the toggle from System tab)
    age_mode = settings['age_mode']
    
    if not df_members.empty:
        df_merged = df_results.merge(df_members[['name', 'gender', 'dob']], on='name', how='left')
        df_merged = df_merged.dropna(subset=['dob'])
        df_merged['category'] = df_merged.apply(lambda x: get_category(x['dob'], x['race_date'], mode=age_mode), axis=1)
    else:
        df_merged = df_results
        df_merged['category'] = "Unk"

    # Filter for PBs
    df_merged = df_merged.sort_values(['name', 'distance', 'time_display'])
    pbs = df_merged.groupby(['name', 'distance']).head(1)

    # 5. Leaderboard Tabs (Just like the Public site, but for Admin use)
    tabs = st.tabs(["5k", "10k", "10 Mile", "HM", "Marathon", "🔍 Search & History"])
    distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

    for i, dist in enumerate(distances):
        with tabs[i]:
            dist_df = pbs[pbs['distance'] == dist].copy()
            if dist_df.empty:
                st.write("No records.")
            else:
                for gender in ["Female", "Male"]:
                    st.markdown(f"#### {gender}")
                    g_df = dist_df[dist_df['gender'] == gender].sort_values('time_display')
                    st.dataframe(
                        g_df[['name', 'category', 'time_display', 'location', 'race_date']].rename(columns={
                            'name': 'Runner', 'category': 'Cat', 'time_display': 'Time', 'location': 'Race'
                        }),
                        use_container_width=True, hide_index=True
                    )

    # 6. Search Tab
    with tabs[5]:
        st.subheader("Runner History")
        all_names = sorted(df_members['name'].unique()) if not df_members.empty else []
        search_name = st.selectbox("Search Member History", [""] + all_names)
        if search_name:
            history = df_merged[df_merged['name'] == search_name].sort_values('race_date', ascending=False)
            st.dataframe(
                history[['race_date', 'distance', 'time_display', 'location', 'category']],
                use_container_width=True, hide_index=True
            )

# Admin Metrics (Only visible if logged in)
if st.session_state['authenticated']:
    st.divider()
    st.subheader("📊 System Overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pending PBs", r.llen("pending_results"))
    c2.metric("Pending Champ", r.llen("champ_pending"))
    c3.metric("Members", r.llen("members"))
