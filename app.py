import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- CONFIG & CONNECTION ---
st.set_page_config(page_title="AutoKudos Admin", layout="wide")

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    st.error(f"Redis Connection Failed: {e}")

# --- HELPER FUNCTIONS ---
def format_time_string(t_str):
    """Ensures time is always HH:MM:SS for the leaderboard cards."""
    try:
        parts = str(t_str).strip().split(':')
        if len(parts) == 2: # MM:SS
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3: # HH:MM:SS
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return t_str
    except:
        return t_str

def get_admin_password():
    stored_pwd = r.get("admin_password")
    return stored_pwd if stored_pwd else "admin123"

def get_club_logo():
    stored_logo = r.get("club_logo_url")
    default_logo = "https://scontent-lhr6-2.xx.fbcdn.net/v/t39.30808-6/613136946_122094772515215234_2783950400659519915_n.jpg?_nc_cat=105&ccb=1-7&oh=00_AfquWT54_DxkPrvTyRnSk2y3a3tBuCxJBvkLCS8rd7ANlg&oe=696A8E3D"
    return stored_logo if stored_logo else default_logo

def get_category(dob_str, race_date_str, mode="10Y"):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        threshold = 35 if mode == "5Y" else 40
        step = 5 if mode == "5Y" else 10
        if age < threshold:
            return "Senior"
        return f"V{(age // step) * step}"
    except:
        return "Unknown"

def time_to_seconds(t_str):
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return None

# --- UI HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(get_club_logo(), width=120)
with col_title:
    st.markdown('<h1 style="color: #003366; margin-top: 10px;">AutoKudos Admin Portal</h1>', unsafe_allow_html=True)

# --- SIDEBAR (LOGIN & REFRESH) ---
with st.sidebar:
    st.markdown('<h2 style="color: #003366;">🔐 Admin Login</h2>', unsafe_allow_html=True)
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == get_admin_password())
    st.divider()
    if st.button("🔄 Refresh All Data", use_container_width=True):
        st.rerun()

# --- TABS DEFINITION ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Approvals & Bulk", "👁️ View Controller"])
all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: LEADERBOARDS (VIEWABLE BY ALL) ---
with tab1:
    stored_vis = r.get("visible_distances")
    active_dist = json.loads(stored_vis) if stored_vis else all_distances
    age_mode = r.get("age_mode") or "10Y"
    raw_res = r.lrange("race_results", 0, -1)
    
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        # Apply the format standardization
        df['time_display'] = df['time_display'].apply(format_time_string)
        
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("📅 Season Select:", years)
        
        display_df = df.copy()
        if sel_year != "All-Time":
            display_df = display_df[display_df['race_date_dt'].dt.year == int(sel_year)]
            
        display_df['Category'] = display_df.apply(lambda x: get_category(x['dob'], x['race_date'], mode=age_mode), axis=1)

        for d in active_dist:
            st.markdown(f"### 🏁 {d} Records")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg, tx = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                    st.markdown(f'<div style="background-color:{bg}; color:{tx}; padding:10px; border-radius:8px 8px 0 0; text-align:center; font-weight:800; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    
                    sub = display_df[(display_df['distance'] == d) & (display_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, r_data in leaders.sort_values('Category').iterrows():
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:12px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center;">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em; margin-right:8px;">{r_data['Category']}</span><b>{r_data['name']}</b><br><small>{r_data['location']} | {r_data['race_date']}</small></div>
                                <div style="font-weight:800; color:#003366; font-size:1.1em;">{r_data['time_display']}</div></div>''', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; color:#999; font-size:0.8em;">No records</div>', unsafe_allow_html=True)
    else:
        st.info("No results in the database yet.")

# --- PROTECTED CONTENT (TABS 2-5) ---
if is_admin:
    with tab2:
        st.subheader("⏱️ All Recorded Results")
        if raw_res:
            res_df = pd.DataFrame([json.loads(res) for res in raw_res])
            st.dataframe(res_df.sort_values('race_date', ascending=False), use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("👤 Club Member List")
        raw_mem = r.lrange("members", 0, -1)
        if raw_mem:
            mem_df = pd.DataFrame([json.loads(m) for m in raw_mem])
            st.dataframe(mem_df.sort_values('name'), use_container_width=True, hide_index=True)

    with tab4:
        st.header("🛠️ Approvals & Bulk Tools")
        
        # 1. PENDING APPROVALS
        st.subheader("📋 Pending BBPB Submissions")
        pending_raw = r.lrange("pending_results", 0, -1)
        if pending_raw:
            m_lookup = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
            for i, p_json in enumerate(pending_raw):
                p = json.loads(p_json)
                with st.expander(f"Review: {p['name']} - {p['distance']} ({format_time_string(p['time_display'])})"):
                    st.write(f"**Location:** {p['location']} | **Date:** {p['race_date']}")
                    if p['name'] not in m_lookup:
                        st.error("Runner not found in Members list! Add them to 'Members' first.")
                    else:
                        m = m_lookup[p['name']]
                        st.success(f"Match Found: {m['gender']} | DOB: {m['dob']}")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Approve", key=f"app_{i}"):
                            entry = {
                                "name": p['name'], "gender": m['gender'], "dob": m['dob'],
                                "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']),
                                "time_display": format_time_string(p['time_display']),
                                "location": p['location'], "race_date": p['race_date']
                            }
                            r.rpush("race_results", json.dumps(entry))
                            r.lrem("pending_results", 1, p_json)
                            st.rerun()
                        if c2.button("❌ Reject", key=f"rej_{i}"):
                            r.lrem("pending_results", 1, p_json)
                            st.rerun()
        else:
            st.info("No submissions waiting for approval.")

        st.divider()
        # 2. TEMPLATE DOWNLOADS
        st.subheader("📥 Download CSV Templates")
        t1, t2 = st.columns(2)
        t1.download_button("Download Members Template", "name,gender,dob\nJohn Smith,Male,1985-05-15", "members_template.csv")
        t2.download_button("Download Results Template", "name,distance,time_display,location,race_date\nJohn Smith,5k,00:19:45,Leeds,2025-01-01", "results_template.csv")

        st.divider()
        # 3. BULK IMPORTS
        st.subheader("🚀 Bulk Upload")
        col_m, col_r = st.columns(2)
        with col_m:
            m_file = st.file_uploader("Upload Members CSV", type="csv")
            if m_file and st.button("Process Members"):
                m_df = pd.read_csv(m_file)
                for _, row in m_df.iterrows():
                    r.rpush("members", json.dumps({"name": str(row['name']).strip(), "gender": str(row['gender']).strip(), "dob": str(row['dob']).strip()}))
                st.success("Members imported successfully!"); st.rerun()
        with col_r:
            r_file = st.file_uploader("Upload Results CSV", type="csv")
            if r_file and st.button("Process Results"):
                m_lookup = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
                r_df = pd.read_csv(r_file)
                added = 0
                for _, row in r_df.iterrows():
                    n = str(row['name']).strip()
                    if n in m_lookup:
                        m = m_lookup[n]
                        entry = {
                            "name": n, "gender": m['gender'], "dob": m['dob'],
                            "distance": str(row['distance']).strip(),
                            "time_seconds": time_to_seconds(str(row['time_display'])),
                            "time_display": format_time_string(str(row['time_display'])),
                            "location": str(row['location']).strip(),
                            "race_date": str(row['race_date']).strip()
                        }
                        r.rpush("race_results", json.dumps(entry))
                        added += 1
                st.success(f"Imported {added} results!"); st.rerun()

        st.divider()
        if st.button("🗑️ Wipe All Results Data"):
            if st.checkbox("Confirm Wipe?"):
                r.delete("race_results")
                st.rerun()

    with tab5:
        st.header("👁️ View Controller")
        stored_vis = r.get("visible_distances")
        default_vis = all_distances if not stored_vis else json.loads(stored_vis)
        
        st.write("Toggle which distances appear on the public leaderboard:")
        visible_list = []
        for d in all_distances:
            if st.checkbox(d, value=(d in default_vis), key=f"vctrl_{d}"):
                visible_list.append(d)
        
        st.divider()
        stored_mode = r.get("age_mode") or "10Y"
        age_choice = st.radio("Age Grouping Style:", ["10 Year Brackets (V40, V50)", "5 Year Brackets (V35, V40, V45)"], 
                              index=0 if stored_mode == "10Y" else 1)
        
        if st.button("Save Global View Settings"):
            r.set("visible_distances", json.dumps(visible_list))
            r.set("age_mode", "10Y" if "10" in age_choice else "5Y")
            st.success("Leaderboard updated for everyone!"); st.rerun()

else:
    # If not logged in, show warnings on protected tabs
    for t in [tab2, tab3, tab4, tab5]:
        with t:
            st.warning("🔒 This section is restricted. Please enter the Admin Password in the sidebar.")
