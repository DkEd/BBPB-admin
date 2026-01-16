import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="AutoKudos Admin", layout="wide")

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    st.error("Redis Connection Failed. Check environment variables.")

# --- 2. HELPERS (The Full Logic) ---
def format_time_string(t_str):
    """Ensures time is HH:MM:SS even if user enters MM:SS."""
    try:
        parts = str(t_str).strip().split(':')
        if len(parts) == 2: 
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3: 
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return str(t_str)
    except:
        return str(t_str)

def time_to_seconds(t_str):
    """Converts time string to total seconds for math/sorting."""
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: 
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: 
            return parts[0] * 60 + parts[1]
        return 999999
    except:
        return 999999

def get_club_logo():
    stored = r.get("club_logo_url")
    if stored and stored.startswith("http"): 
        return stored
    return "https://cdn-icons-png.flaticon.com/512/55/55281.png"

def get_category(dob_str, race_date_str, mode="10Y"):
    """Calculates age category (Senior, V40, etc) based on race date."""
    try:
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        race_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        threshold = 35 if mode == "5Y" else 40
        step = 5 if mode == "5Y" else 10
        if age < threshold: return "Senior"
        return f"V{(age // step) * step}"
    except:
        return "Unknown"

def is_duplicate_pb(name, race_date):
    """Prevents the same race being added twice for one person."""
    current_results = r.lrange("race_results", 0, -1)
    for res_json in current_results:
        res = json.loads(res_json)
        if str(res.get('name', '')).strip() == str(name).strip() and str(res.get('race_date', '')).strip() == str(race_date).strip():
            return True
    return False

# --- 3. SIDEBAR & VISIBILITY ---
with st.sidebar:
    st.image(get_club_logo(), width=150)
    st.markdown("### 🔒 Admin Access")
    pwd_input = st.text_input("Password", type="password")
    admin_pwd = r.get("admin_password") or "admin123"
    is_admin = (pwd_input == admin_pwd)
    
    if is_admin:
        st.success("Admin Authenticated")
        st.divider()
        st.markdown("### 👁️ Public Visibility")
        current_vis = r.get("show_champ_tab") == "True"
        champ_toggle = st.toggle("Show Champ Tab on BBPB", value=current_vis)
        if st.button("Save Tab Visibility"):
            r.set("show_champ_tab", str(champ_toggle))
            st.rerun()
    
    st.divider()
    raw_mem = r.lrange("members", 0, -1)
    members_data = [json.loads(m) for m in raw_mem]
    if st.button("🔄 Force Refresh Data"): 
        st.rerun()

# --- 4. MAIN NAVIGATION ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏆 Leaderboard", "📥 Submissions", "📋 Race Log", "👥 Members", "🏅 Championship", "⚙️ System"
])

dist_list = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: PUBLIC LEADERBOARD VIEW ---
with tab1:
    raw_res = r.lrange("race_results", 0, -1)
    active_names = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']
    
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        
        # Season Selector
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("Select Season:", years)
        
        disp_df = df.copy()
        if sel_year != "All-Time":
            disp_df = disp_df[disp_df['race_date_dt'].dt.year == int(sel_year)]
            
        age_mode = r.get("age_mode") or "10Y"
        disp_df['Category'] = disp_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

        for d in dist_list:
            st.markdown(f"### 🏁 {d}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg = "#003366" if gen == "Male" else "#FFD700"
                    tc = "white" if gen == "Male" else "#003366"
                    st.markdown(f'<div style="background:{bg}; color:{tc}; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    
                    sub = disp_df[(disp_df['distance'] == d) & (disp_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, row in leaders.sort_values('Category').iterrows():
                            # Restored Ghosting Logic for members who left
                            opacity = "1.0" if row['name'] in active_names else "0.5"
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">{row['Category']}</span><b>{row['name']}</b><br><small>{row['location']}</small></div>
                                <div style="font-weight:bold; color:#003366;">{row['time_display']}</div></div>''', unsafe_allow_html=True)

# --- PROTECTED ADMIN TABS ---
if is_admin:
    with tab2: # SUBMISSIONS & MANUAL ADD
        st.subheader("📥 Process Submissions")
        
        # Manual Form (Restored)
        with st.form("manual_add_form"):
            st.markdown("**Manual Result Entry**")
            c1, c2, c3 = st.columns(3)
            n = c1.selectbox("Select Member", sorted([m['name'] for m in members_data]))
            d = c2.selectbox("Distance", dist_list)
            t = c3.text_input("Time (HH:MM:SS)")
            loc = st.text_input("Race Name")
            rd = st.date_input("Race Date")
            if st.form_submit_button("Save Record"):
                matched = next(m for m in members_data if m['name'] == n)
                if not is_duplicate_pb(n, str(rd)):
                    entry = {"name": n, "gender": matched['gender'], "dob": matched['dob'], "distance": d, "time_seconds": time_to_seconds(t), "time_display": format_time_string(t), "location": loc, "race_date": str(rd)}
                    r.rpush("race_results", json.dumps(entry))
                    st.success(f"Saved {n}'s result")
                    st.rerun()

        st.divider()
        # Pending Queue
        pending = r.lrange("pending_results", 0, -1)
        for i, p_json in enumerate(pending):
            p = json.loads(p_json)
            with st.expander(f"Review: {p['name']} ({p['distance']})"):
                matched = next((m for m in members_data if m['name'] == p['name']), None)
                if matched:
                    if st.button("✅ Approve", key=f"p_app_{i}"):
                        entry = {"name": p['name'], "gender": matched['gender'], "dob": matched['dob'], "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']), "time_display": format_time_string(p['time_display']), "location": p['location'], "race_date": str(p['race_date'])}
                        r.rpush("race_results", json.dumps(entry))
                        r.lrem("pending_results", 1, p_json)
                        st.rerun()
                if st.button("❌ Reject", key=f"p_rej_{i}"):
                    r.lrem("pending_results", 1, p_json)
                    st.rerun()

    with tab3: # RACE LOG (Restored Index-Based Precision Deletion)
        st.subheader("📋 Master Record Log")
        all_results = r.lrange("race_results", 0, -1)
        if all_results:
            for idx, val in enumerate(all_results):
                item = json.loads(val)
                st_key = f"edit_state_{idx}"
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3,1,1])
                    c1.write(f"**{item['name']}** - {item['distance']} - {item['time_display']} ({item['race_date']})")
                    
                    if c2.button("📝 Edit", key=f"ebtn_{idx}"):
                        st.session_state[st_key] = True
                    
                    if c3.button("🗑️", key=f"dbtn_{idx}"):
                        # Targeting specific index to avoid data corruption
                        r.lset("race_results", idx, "DELETE_TAG")
                        r.lrem("race_results", 1, "DELETE_TAG")
                        st.rerun()
                    
                    if st.session_state.get(st_key):
                        with st.form(f"edit_form_{idx}"):
                            new_t = st.text_input("New Time", item['time_display'])
                            new_d = st.text_input("New Date (YYYY-MM-DD)", item['race_date'])
                            new_loc = st.text_input("New Location", item['location'])
                            if st.form_submit_button("Confirm Changes"):
                                item['time_display'] = format_time_string(new_t)
                                item['time_seconds'] = time_to_seconds(new_t)
                                item['race_date'] = new_d
                                item['location'] = new_loc
                                r.lset("race_results", idx, json.dumps(item))
                                st.session_state[st_key] = False
                                st.rerun()

    with tab4: # MEMBERS (Restored Edit & Toggle)
        st.subheader("👥 Member Management")
        for i, m_json in enumerate(r.lrange("members", 0, -1)):
            m = json.loads(m_json)
            m_key = f"m_state_{i}"
            with st.container(border=True):
                c1, c2, c3 = st.columns([3,1,1])
                status_label = m.get('status', 'Active')
                c1.write(f"**{m['name']}** - Status: {status_label}")
                
                if c2.button("Toggle Active/Left", key=f"mtog_{i}"):
                    m['status'] = "Left" if status_label == "Active" else "Active"
                    r.lset("members", i, json.dumps(m))
                    st.rerun()
                
                if c3.button("Edit Member", key=f"medit_{i}"):
                    st.session_state[m_key] = True
                
                if st.session_state.get(m_key):
                    with st.form(f"mform_{i}"):
                        un = st.text_input("Name", m['name'])
                        udob = st.text_input("DOB (YYYY-MM-DD)", m.get('dob', ''))
                        ugen = st.selectbox("Gender", ["Male", "Female"], index=0 if m['gender']=="Male" else 1)
                        if st.form_submit_button("Update Member"):
                            m.update({"name": un, "dob": udob, "gender": ugen})
                            r.lset("members", i, json.dumps(m))
                            st.session_state[m_key] = False
                            st.rerun()

    with tab5: # CHAMPIONSHIP (Restored 15-Race Setup)
        st.subheader("🏅 2026 Club Championship")
        ced, capp, cstand = st.tabs(["Calendar Editor", "Approvals", "Points Standings"])
        
        with ced:
            cal_raw = r.get("champ_calendar_2026")
            if not cal_raw:
                init = [{"date": "TBC", "name": f"Race {i+1}", "distance": "TBC", "terrain": "Road"} for i in range(15)]
                r.set("champ_calendar_2026", json.dumps(init))
                cal_raw = json.dumps(init)
            
            cal = json.loads(cal_raw)
            up_cal = []
            for i, ra in enumerate(cal):
                with st.expander(f"Race {i+1}: {ra['name']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    rd = c1.text_input("Date", ra['date'], key=f"chd_{i}")
                    rn = c2.text_input("Event Name", ra['name'], key=f"chn_{i}")
                    rdi = c3.text_input("Distance", ra['distance'], key=f"chdi_{i}")
                    rte = c4.selectbox("Terrain", ["Road", "Trail", "Fell", "XC"], key=f"chte_{i}")
                    up_cal.append({"date": rd, "name": rn, "distance": rdi, "terrain": rte})
            if st.button("Save Championship Calendar"):
                r.set("champ_calendar_2026", json.dumps(up_cal))
                st.success("Calendar Saved")
                st.rerun()

        with capp:
            c_pend = r.lrange("champ_pending", 0, -1)
            for i, cj in enumerate(c_pend):
                cp = json.loads(cj)
                st.write(f"**{cp['name']}** at {cp['race_name']} ({cp['time_display']})")
                win_t = st.text_input("Category Winner Time (HH:MM:SS)", key=f"win_{i}")
                if st.button("Approve & Calc Points", key=f"c_app_btn_{i}"):
                    pts = round((time_to_seconds(win_t) / time_to_seconds(cp['time_display'])) * 100, 1)
                    res = {"name": cp['name'], "race": cp['race_name'], "points": pts, "date": cp['date']}
                    r.rpush("champ_results_final", json.dumps(res))
                    r.lrem("champ_pending", 1, cj)
                    st.rerun()
                if st.button("Reject Entry", key=f"c_rej_btn_{i}"):
                    r.lrem("champ_pending", 1, cj)
                    st.rerun()

        with cstand:
            final_raw = r.lrange("champ_results_final", 0, -1)
            if final_raw:
                st.dataframe(pd.DataFrame([json.loads(x) for x in final_raw]))
                if st.button("Clear Standings"):
                    if st.checkbox("Confirm Clear All Points"):
                        r.delete("champ_results_final")
                        st.rerun()

    with tab6: # SYSTEM (Restored Bulk CSV logic)
        st.subheader("⚙️ System Configuration")
        lurl = st.text_input("Club Logo URL", r.get("club_logo_url") or "")
        if st.button("Update Branding"): r.set("club_logo_url", lurl); st.rerun()
        
        col_m, col_p = st.columns(2)
        with col_m:
            st.markdown("**Bulk Member Upload**")
            mf = st.file_uploader("Upload CSV (name,gender,dob)", type="csv", key="m_up")
            if mf and st.button("Process Members"):
                for _, row in pd.read_csv(mf).iterrows():
                    r.rpush("members", json.dumps({"name": str(row['name']).strip(), "gender": str(row['gender']).strip(), "dob": str(row['dob']).strip(), "status": "Active"}))
                st.success("Members Imported")
        with col_p:
            st.markdown("**Bulk PB Upload**")
            pf = st.file_uploader("Upload CSV (name,distance,time_display,location,race_date)", type="csv", key="p_up")
            if pf and st.button("Process PBs"):
                m_lookup = {m['name']: m for m in members_data}
                for _, row in pd.read_csv(pf).iterrows():
                    nm = str(row['name']).strip()
                    if nm in m_lookup:
                        m = m_lookup[nm]
                        e = {"name": nm, "gender": m['gender'], "dob": m['dob'], "distance": str(row['distance']), "time_seconds": time_to_seconds(str(row['time_display'])), "time_display": format_time_string(str(row['time_display'])), "location": str(row['location']), "race_date": str(row['race_date'])}
                        r.rpush("race_results", json.dumps(e))
                st.success("PBs Imported")
        
        st.divider()
        if st.button("🗑️ Wipe All PB Results"):
            if st.checkbox("Confirm database wipe"):
                r.delete("race_results")
                st.rerun()
