import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- CONFIG & CONNECTION ---
st.set_page_config(page_title="Club Leaderboard", layout="wide")

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    st.error(f"Redis Connection Failed: {e}")

# --- HELPER FUNCTIONS ---
def get_admin_password():
    stored_pwd = r.get("admin_password")
    return stored_pwd if stored_pwd else "admin123"

def get_club_logo():
    stored_logo = r.get("club_logo_url")
    default_logo = "https://scontent-lhr6-2.xx.fbcdn.net/v/t39.30808-6/613136946_122094772515215234_2783950400659519915_n.jpg?_nc_cat=105&ccb=1-7&_nc_sid=cc71e4&_nc_ohc=kvHoy9QIOF4Q7kNvwGRAj6K&_nc_oc=Adm0NLaoEHZoixq2SnIjN_KH-Zfwbqu11R1pz8aAV3sMB2Ru2wRsi3H4j7cerOPAUmGOmUh3Q6dC7TWGA82mWYDi&_nc_zt=23&_nc_ht=scontent-lhr6-2.xx&_nc_gid=5GS-5P76DuiR2umpX-xI5w&oh=00_AfquWT54_DxkPrvTyRnSk2y3a3tBuCxJBvkLCS8rd7ANlg&oe=696A8E3D"
    return stored_logo if stored_logo else default_logo

def get_category(dob_str, race_date_str, mode="10Y"):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        if mode == "5Y":
            if age < 35: return "Senior"
            return f"V{(age // 5) * 5}"
        else:
            if age < 40: return "Senior"
            return f"V{(age // 10) * 10}"
    except: return "Unknown"

def time_to_seconds(t_str):
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return None

# --- HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(get_club_logo(), width=120)
with col_title:
    st.markdown('<h1 style="color: #003366; margin-top: 10px;">Club Leaderboard</h1>', unsafe_allow_html=True)

# --- ADMIN LOGIN ---
with st.sidebar:
    st.markdown('<h2 style="color: #003366;">🔐 Admin Login</h2>', unsafe_allow_html=True)
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == get_admin_password())

# --- TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Admin", "👁️ View Controller"])

all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 4: ADMIN (WIPE & UPLOAD) ---
with tab4:
    if is_admin:
        st.header("🛠️ Admin & Data Control")
        
        # --- BULK UPLOAD ---
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            st.subheader("1. Members CSV")
            m_file = st.file_uploader("Upload Members", type="csv")
            if m_file and st.button("🚀 Import Members"):
                m_df = pd.read_csv(m_file)
                m_df.columns = [c.lower().strip() for c in m_df.columns]
                for _, row in m_df.iterrows():
                    r.rpush("members", json.dumps({"name": str(row['name']).strip(), "gender": str(row['gender']).strip(), "dob": str(row['dob']).strip()}))
                st.success("Members Imported! Reloading...")
                st.rerun()

        with col_up2:
            st.subheader("2. Results CSV")
            r_file = st.file_uploader("Upload Results", type="csv")
            if r_file and st.button("💾 Import Results"):
                r_df = pd.read_csv(r_file)
                r_df.columns = [c.lower().strip() for c in r_df.columns]
                m_lookup = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
                for _, row in r_df.iterrows():
                    name = str(row['name']).strip()
                    if name in m_lookup:
                        m = m_lookup[name]
                        entry = {"name": name, "gender": m['gender'], "dob": m['dob'], "distance": str(row['distance']).strip(), 
                                 "time_seconds": time_to_seconds(row['time_display']), "time_display": str(row['time_display']).strip(), 
                                 "location": str(row['location']).strip(), "race_date": str(row['race_date']).strip()}
                        r.rpush("race_results", json.dumps(entry))
                st.success("Results Imported! Reloading...")
                st.rerun()

        st.divider()

        # --- WIPE TOOLS ---
        st.subheader("⚠️ Danger Zone (Testing Tools)")
        st.write("Use these to clear data during testing.")
        cw1, cw2, cw3 = st.columns(3)
        with cw1:
            if st.button("🗑️ Wipe ALL Results"):
                r.delete("race_results")
                st.warning("All race results deleted.")
                st.rerun()
        with cw2:
            if st.button("👥 Wipe ALL Members"):
                r.delete("members")
                st.warning("All members deleted.")
                st.rerun()
        with cw3:
            if st.button("🔥 Factory Reset (Both)"):
                r.delete("race_results")
                r.delete("members")
                st.error("Database completely cleared.")
                st.rerun()
                
    else:
        st.error("Admin Login Required")

# --- TAB 1: LEADERBOARD ---
with tab1:
    current_year = datetime.now().year
    years = ["All-Time"] + [str(y) for y in range(2023, current_year + 1)]
    selected_year = st.selectbox("📅 Season:", years)
    
    vis_data = r.get("visible_distances")
    active_dist = json.loads(vis_data) if vis_data else all_distances
    mode = r.get("age_mode") or "10Y"

    results = r.lrange("race_results", 0, -1)
    if results:
        df = pd.DataFrame([json.loads(res) for res in results])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        if selected_year != "All-Time":
            df = df[df['race_date_dt'].dt.year == int(selected_year)]
        
        if not df.empty:
            df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date'], mode=mode), axis=1)
            for d in active_dist:
                st.markdown(f"### 🏁 {d} Records")
                m_col, f_col = st.columns(2)
                for gen, col in [("Male", m_col), ("Female", f_col)]:
                    with col:
                        bg, tx = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                        st.markdown(f'<div style="background-color:{bg}; color:{tx}; padding:10px; border-radius:8px 8px 0 0; text-align:center; font-weight:800; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                        sub = df[(df['distance'] == d) & (df['gender'] == gen)]
                        if not sub.empty:
                            leaders = sub.sort_values('time_seconds').groupby('Category').head(1).sort_values('Category')
                            for _, row in leaders.iterrows():
                                st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:12px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center;">
                                    <div><span style="background:#FFD700; color:#003366; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em; margin-right:8px;">{row['Category']}</span><b>{row['name']}</b><br><small>{row['location']} | {row['race_date']}</small></div>
                                    <div style="font-weight:800; color:#003366; font-size:1.1em;">{row['time_display']}</div></div>''', unsafe_allow_html=True)
                        else: st.markdown('<div style="border:1px solid #ddd; padding:10px; text-align:center; font-size:0.8em; color:#999;">No data</div>', unsafe_allow_html=True)
    else: st.info("Database empty.")

# --- TAB 5: VIEW CONTROLLER ---
with tab5:
    if is_admin:
        st.subheader("Leaderboard Settings")
        stored_mode = r.get("age_mode") or "10Y"
        age_toggle = st.radio("Age Grouping:", ["10 Year Steps", "5 Year Steps"], index=0 if stored_mode == "10Y" else 1)
        if st.button("Save Settings"):
            r.set("age_mode", "10Y" if "10" in age_toggle else "5Y")
            st.success("Updated!")
            st.rerun()
    else: st.warning("Login as Admin to change views.")

# (Tab 2 and Tab 3 logic follows standard dataframe display from Redis)
with tab2:
    if results:
        st.dataframe(pd.DataFrame([json.loads(res) for res in results]).sort_values('race_date', ascending=False), use_container_width=True)
with tab3:
    m_raw = r.lrange("members", 0, -1)
    if m_raw:
        st.dataframe(pd.DataFrame([json.loads(m) for m in m_raw]).sort_values('name'), use_container_width=True)
