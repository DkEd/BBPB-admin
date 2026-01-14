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
    st.error("Redis Connection Failed. Check your REDIS_URL environment variable.")

# --- HELPER FUNCTIONS ---
def format_time_string(t_str):
    try:
        parts = str(t_str).strip().split(':')
        if len(parts) == 2: return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3: return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return t_str
    except: return t_str

def time_to_seconds(t_str):
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        return 999999
    except: return 999999

def get_club_logo():
    # Priority: Redis Saved URL -> Default Fallback
    stored = r.get("club_logo_url")
    if stored and stored.startswith("http"): return stored
    return "https://cdn-icons-png.flaticon.com/512/55/55281.png" # Professional Running Fallback

def get_category(dob_str, race_date_str, mode="10Y"):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        threshold = 35 if mode == "5Y" else 40
        step = 5 if mode == "5Y" else 10
        if age < threshold: return "Senior"
        return f"V{(age // step) * step}"
    except: return "Unknown"

def is_duplicate(name, race_date):
    current_results = r.lrange("race_results", 0, -1)
    for res_json in current_results:
        res = json.loads(res_json)
        if str(res.get('name', '')).strip() == str(name).strip() and str(res.get('race_date', '')).strip() == str(race_date).strip():
            return True
    return False

def run_database_deduplication():
    raw_res = r.lrange("race_results", 0, -1)
    if not raw_res: return 0, 0
    unique_entries = {}
    for res_json in raw_res:
        data = json.loads(res_json)
        key = (data['name'], data['race_date'])
        new_time = data.get('time_seconds') if data.get('time_seconds') is not None else 999999
        if key not in unique_entries:
            unique_entries[key] = res_json
        else:
            existing_data = json.loads(unique_entries[key])
            existing_time = existing_data.get('time_seconds') if existing_data.get('time_seconds') is not None else 999999
            if new_time < existing_time: unique_entries[key] = res_json
    r.delete("race_results")
    for final_json in unique_entries.values():
        r.rpush("race_results", final_json)
    return len(raw_res), len(unique_entries)

# --- SIDEBAR & AUTH ---
with st.sidebar:
    st.image(get_club_logo(), width=150)
    st.markdown("### 🔒 Admin Access")
    pwd_input = st.text_input("Password", type="password")
    admin_pwd = r.get("admin_password") or "admin123"
    is_admin = (pwd_input == admin_pwd)
    
    st.divider()
    # Health Audit - Constant Visibility
    raw_mem = r.lrange("members", 0, -1)
    members_data = [json.loads(m) for m in raw_mem]
    missing_dob = [m['name'] for m in members_data if not m.get('dob')]
    
    if missing_dob:
        st.error(f"⚠️ Health Alert: {len(missing_dob)} members missing DOB")
    else:
        st.success("✅ Data Health: Perfect")
    
    if st.button("🔄 Force Refresh All Data"): st.rerun()

# --- MAIN TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboard", "📥 Submissions", "📋 Race Log", "👥 Members", "⚙️ System"])
all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: LEADERBOARD ---
with tab1:
    raw_res = r.lrange("race_results", 0, -1)
    active_members = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Results", len(raw_res))
    c2.metric("Active Runners", len(active_members))
    pending_count = r.llen("pending_results")
    c3.metric("Pending Approvals", pending_count, delta_color="inverse")

    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("Season Select:", years)
        
        display_df = df.copy()
        if sel_year != "All-Time":
            display_df = display_df[display_df['race_date_dt'].dt.year == int(sel_year)]
            
        stored_vis = r.get("visible_distances")
        active_dist = json.loads(stored_vis) if stored_vis else all_distances
        age_mode = r.get("age_mode") or "10Y"
        display_df['Category'] = display_df.apply(lambda x: get_category(x['dob'], x['race_date'], mode=age_mode), axis=1)

        for d in active_dist:
            st.markdown(f"### 🏁 {d}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg, tx = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                    st.markdown(f'<div style="background:{bg}; color:{tx}; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    sub = display_df[(display_df['distance'] == d) & (display_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, r_data in leaders.sort_values('Category').iterrows():
                            opacity = "1.0" if r_data['name'] in active_members else "0.5"
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">{r_data['Category']}</span><b>{r_data['name']}</b><br><small>{r_data['location']}</small></div>
                                <div style="font-weight:bold; color:#003366;">{r_data['time_display']}</div></div>''', unsafe_allow_html=True)
                    else: st.markdown('<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; font-size:0.8em; color:#ccc;">No data</div>', unsafe_allow_html=True)

# --- PROTECTED ADMIN TABS ---
if is_admin:
    with tab2: # SUBMISSIONS
        st.subheader("📥 Pending Submissions")
        pending_raw = r.lrange("pending_results", 0, -1)
        member_names = sorted([m['name'] for m in members_data])
        
        if not pending_raw: st.info("No submissions waiting for review.")
        for i, p_json in enumerate(pending_raw):
            p = json.loads(p_json)
            with st.expander(f"Review: {p['name']} ({p['distance']})"):
                matched = next((m for m in members_data if m['name'] == p['name']), None)
                if not matched:
                    st.error("Name Typo Found!")
                    correct_name = st.selectbox("Assign to Member:", ["-- Select --"] + member_names, key=f"match_{i}")
                    matched = next((m for m in members_data if m['name'] == correct_name), None)
                
                if matched:
                    if is_duplicate(matched['name'], p['race_date']): st.warning("⚠️ Warning: This runner already has a result for this date.")
                    if st.button("✅ Approve Entry", key=f"app_{i}"):
                        t_sec = time_to_seconds(p['time_display'])
                        entry = {"name": matched['name'], "gender": matched['gender'], "dob": matched['dob'], "distance": p['distance'], "time_seconds": t_sec, "time_display": format_time_string(p['time_display']), "location": p['location'], "race_date": p['race_date']}
                        r.rpush("race_results", json.dumps(entry))
                        r.lrem("pending_results", 1, p_json); st.rerun()
                if st.button("❌ Reject / Delete", key=f"rej_{i}"):
                    r.lrem("pending_results", 1, p_json); st.rerun()

    with tab3: # RACE LOG (EDIT/DELETE/EXPORT)
        st.subheader("📋 Searchable Race Log")
        search_q = st.text_input("🔍 Search by Runner Name:", "")
        
        if raw_res:
            res_df = pd.DataFrame([json.loads(res) for res in raw_res])
            if search_q:
                res_df = res_df[res_df['name'].str.contains(search_q, case=False)]
            
            st.download_button("📥 Export Log to Excel (CSV)", res_df.to_csv(index=False), "bbpb_history.csv", "text/csv")
            
            for i, row in res_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"**{row['name']}**")
                    c1.write(f"{row['distance']} | {row['time_display']} | {row['race_date']}")
                    
                    if c2.button("📝 Edit", key=f"edit_{i}"):
                        st.session_state[f"editing_{i}"] = True
                    
                    if c3.button("🗑️", key=f"del_{i}"):
                        r.lrem("race_results", 1, json.dumps(row.to_dict())); st.rerun()
                    
                    if st.session_state.get(f"editing_{i}"):
                        with st.form(f"form_{i}"):
                            new_dist = st.selectbox("Distance", all_distances, index=all_distances.index(row['distance']) if row['distance'] in all_distances else 0)
                            new_time = st.text_input("Time", row['time_display'])
                            new_loc = st.text_input("Location", row['location'])
                            new_date = st.text_input("Date (YYYY-MM-DD)", row['race_date'])
                            if st.form_submit_button("Save Changes"):
                                r.lrem("race_results", 1, json.dumps(row.to_dict()))
                                row['distance'], row['time_display'], row['location'], row['race_date'] = new_dist, new_time, new_loc, new_date
                                row['time_seconds'] = time_to_seconds(new_time)
                                r.rpush("race_results", json.dumps(row.to_dict()))
                                del st.session_state[f"editing_{i}"]; st.rerun()

    with tab4: # MEMBERS
        st.subheader("👥 Member Database")
        for i, m in enumerate(members_data):
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                status = m.get('status', 'Active')
                c1.write(f"**{m['name']}** ({m['gender']})")
                c1.write(f"DOB: {m.get('dob', 'MISSING')}")
                
                if c2.button("Toggle Status", key=f"m_stat_{i}"):
                    r.lrem("members", 1, json.dumps(m))
                    m['status'] = "Left" if status == "Active" else "Active"
                    r.rpush("members", json.dumps(m)); st.rerun()
                
                if c3.button("📝", key=f"m_edit_{i}"):
                    st.session_state[f"m_edit_{i}"] = True
                
                if st.session_state.get(f"m_edit_{i}"):
                    with st.form(f"m_form_{i}"):
                        new_n = st.text_input("Name", m['name'])
                        new_dob = st.text_input("DOB (YYYY-MM-DD)", m.get('dob', ''))
                        if st.form_submit_button("Update Member"):
                            r.lrem("members", 1, json.dumps(m))
                            m['name'], m['dob'] = new_n, new_dob
                            r.rpush("members", json.dumps(m))
                            del st.session_state[f"m_edit_{i}"]; st.rerun()

    with tab5: # SYSTEM
        st.subheader("⚙️ System Configuration")
        
        # LOGO CONTROLLER
        st.markdown("### 🖼️ Club Branding")
        current_logo = r.get("club_logo_url") or ""
        logo_url = st.text_input("Logo Image URL:", current_logo)
        if st.button("Save Logo"):
            r.set("club_logo_url", logo_url); st.success("Logo Updated!"); st.rerun()
            
        st.divider()
        st.markdown("### 🚀 Bulk Uploads")
        col_m, col_r = st.columns(2)
        with col_m:
            m_file = st.file_uploader("Bulk Members (CSV: name,gender,dob)", type="csv")
            if m_file and st.button("Process Members"):
                for _, row in pd.read_csv(m_file).iterrows():
                    r.rpush("members", json.dumps({"name": str(row['name']).strip(), "gender": str(row['gender']).strip(), "dob": str(row['dob']).strip(), "status": "Active"}))
                st.success("Members Loaded!"); st.rerun()
        with col_r:
            r_file = st.file_uploader("Bulk Results (CSV: name,distance,time_display,location,race_date)", type="csv")
            if r_file and st.button("Process Results"):
                m_lookup = {m['name']: m for m in members_data}
                added, skipped = 0, 0
                for _, row in pd.read_csv(r_file).iterrows():
                    n, d_str = str(row['name']).strip(), str(row['race_date']).strip()
                    dist = str(row['distance']).strip()
                    if dist.lower().replace(" ", "") == "10mile": dist = "10 Mile"
                    if n in m_lookup and not is_duplicate(n, d_str):
                        m = m_lookup[n]
                        entry = {"name": n, "gender": m['gender'], "dob": m['dob'], "distance": dist, "time_seconds": time_to_seconds(str(row['time_display'])), "time_display": format_time_string(str(row['time_display'])), "location": str(row['location']).strip(), "race_date": d_str}
                        r.rpush("race_results", json.dumps(entry)); added += 1
                    else: skipped += 1
                st.success(f"Added {added}, Skipped {skipped}"); st.rerun()

        st.divider()
        st.markdown("### 🛠️ Maintenance")
        if st.button("🧹 Run Deduplication (None-Safe)"):
            old, new = run_database_deduplication()
            st.success(f"Cleaned {old-new} records."); st.rerun()
            
        st.error("Danger Zone")
        if st.button("🗑️ Wipe All Race Results"):
            if st.checkbox("Confirm Wipe?"): r.delete("race_results"); st.rerun()

else:
    for t in [tab2, tab3, tab4, tab5]:
        with t: st.warning("🔒 Enter password in sidebar to manage club data.")
