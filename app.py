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

def get_category(dob_str, race_date_str):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        if age < 40: return "Senior"
        if age < 50: return "V40"
        if age < 60: return "V50"
        if age < 70: return "V60"
        return "V70"
    except: return "Unknown"

def time_to_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return None

def is_time_realistic(dist, secs):
    limits = {"5k": 720, "10k": 1560, "10 Mile": 2700, "HM": 3480, "Marathon": 7200}
    return secs >= limits.get(dist, 0)

# --- SIDEBAR ADMIN ---
with st.sidebar:
    st.title("🔐 Admin Login")
    current_pwd = get_admin_password()
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == current_pwd)
    
    if is_admin:
        st.success("Admin Access Granted")
        st.divider()
        new_pwd = st.text_input("Update Password", type="password")
        if st.button("Save New Password"):
            if new_pwd:
                r.set("admin_password", new_pwd)
                st.success("Password Updated!")
                st.rerun()
    else:
        st.warning("Enter password to manage data")

# --- MAIN UI ---
st.title("🏃‍♂️ Club Records")

tab1, tab2, tab3, tab4 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Admin"])

# --- TAB 1: LEADERBOARD ---
with tab1:
    current_year = datetime.now().year
    years = ["All-Time"] + [str(y) for y in range(2023, current_year + 1)]
    col_filter, _ = st.columns([1, 2])
    with col_filter:
        selected_year = st.selectbox("📅 Select Season:", years, index=0)
    
    raw_results = r.lrange("race_results", 0, -1)
    if raw_results:
        df = pd.DataFrame([json.loads(res) for res in raw_results])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        
        if selected_year != "All-Time":
            df = df[df['race_date_dt'].dt.year == int(selected_year)]
        
        if not df.empty:
            df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date']), axis=1)
            cat_order = ["Senior", "V40", "V50", "V60", "V70"]
            
            for d in ["5k", "10k", "10 Mile", "HM", "Marathon"]:
                st.markdown(f"### 🏁 {d} Records - {selected_year}")
                m_col, f_col = st.columns(2)
                for gen, col in [("Male", m_col), ("Female", f_col)]:
                    with col:
                        bg_color = "#2e5a88" if gen == "Male" else "#a64d79"
                        st.markdown(f'<div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; color: white; text-align: center; font-weight: bold; margin-bottom: 10px;">{gen.upper()}</div>', unsafe_allow_html=True)
                        
                        subset = df[(df['distance'] == d) & (df['gender'] == gen)]
                        if not subset.empty:
                            leaders = subset.sort_values('time_seconds').groupby('Category', observed=True).head(1)
                            leaders['Category'] = pd.Categorical(leaders['Category'], categories=cat_order, ordered=True)
                            for _, row in leaders.sort_values('Category').iterrows():
                                st.markdown(f"""
                                <div style="border: 1px solid #ddd; padding: 10px; border-radius: 8px; margin-bottom: 5px; background-color: #f9f9f9;">
                                    <span style="font-weight: bold; color: #555;">{row['Category']}:</span> 
                                    <span style="font-size: 1.1em;">{row['name']}</span>
                                    <div style="float: right; font-weight: bold; color: #d35400;">{row['time_display']}</div>
                                    <div style="font-size: 0.8em; color: #888;">{row['location']} | {row['race_date']}</div>
                                </div>""", unsafe_allow_html=True)
                        else: st.caption(f"No {gen} records recorded.")
        else: st.info(f"No results found for {selected_year}.")
    else: st.info("Database is empty.")

# --- TAB 2: ACTIVITY FEED ---
with tab2:
    st.header("Recent Race Activity")
    if raw_results:
        all_df = pd.DataFrame([json.loads(res) for res in raw_results])
        all_df = all_df.sort_values('race_date', ascending=False)
        st.dataframe(all_df[['race_date', 'name', 'distance', 'time_display', 'location']], use_container_width=True, hide_index=True)

# --- TAB 3: MEMBER MANAGEMENT ---
with tab3:
    if is_admin:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Register Member")
            with st.form("mem_form", clear_on_submit=True):
                n = st.text_input("Full Name")
                g = st.selectbox("Gender", ["Male", "Female"])
                b = st.date_input("DOB", value=date(1990, 1, 1), min_value=date(1920, 1, 1))
                if st.form_submit_button("Save"):
                    if n:
                        r.rpush("members", json.dumps({"name":n, "gender":g, "dob":str(b)}))
                        st.success(f"{n} added.")
                        st.rerun()
        with col2:
            st.subheader("Member List")
            m_raw = r.lrange("members", 0, -1)
            if m_raw:
                m_list = [json.loads(m) for m in m_raw]
                m_df = pd.DataFrame(m_list).sort_values('name')
                st.dataframe(m_df, use_container_width=True, hide_index=True)
                m_del = st.selectbox("Remove Member", m_df['name'])
                if st.button("Delete Member"):
                    updated = [json.dumps(m) for m in m_list if m['name'] != m_del]
                    r.delete("members")
                    if updated: r.rpush("members", *updated)
                    st.rerun()
    else: st.error("Admin login required.")

# --- TAB 4: ADMIN TOOLS ---
with tab4:
    if is_admin:
        st.header("Bulk Import & Export")
        col_m, col_r = st.columns(2)
        with col_m:
            st.subheader("Import Members (CSV)")
            m_file = st.file_uploader("Upload Members", type="csv")
            if m_file and st.button("Confirm Member Import"):
                m_df = pd.read_csv(m_file)
                for _, row in m_df.iterrows():
                    r.rpush("members", json.dumps({"name": str(row['name']), "gender": str(row['gender']), "dob": str(row['dob'])}))
                st.success("Imported!")
                st.rerun()
        with col_r:
            st.subheader("Backup Data")
            if raw_results:
                csv = pd.DataFrame([json.loads(res) for res in raw_results]).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Results CSV", data=csv, file_name=f"records_backup_{date.today()}.csv", mime='text/csv')

        st.divider()
        st.header("Log Result")
        m_raw = r.lrange("members", 0, -1)
        if m_raw:
            m_list = [json.loads(m) for m in m_raw]
            with st.form("race_form", clear_on_submit=True):
                n_sel = st.selectbox("Runner", sorted([m['name'] for m in m_list]))
                m_info = next(i for i in m_list if i["name"] == n_sel)
                dist = st.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"])
                t_str = st.text_input("Time (HH:MM:SS)")
                loc = st.text_input("Location")
                dt = st.date_input("Race Date")
                if st.form_submit_button("Submit"):
                    secs = time_to_seconds(t_str)
                    if secs:
                        if not is_time_realistic(dist, secs):
                            st.error("⚠️ Time too fast. Check format (HH:MM:SS).")
                        elif dt < datetime.strptime(m_info['dob'], '%Y-%m-%d').date():
                            st.error("⚠️ Race date cannot be before DOB.")
                        else:
                            entry = {"name": n_sel, "gender": m_info['gender'], "dob": m_info['dob'], "distance": dist, "time_seconds": secs, "time_display": t_str, "location": loc, "race_date": str(dt)}
                            r.rpush("race_results", json.dumps(entry))
                            st.success("Saved!")
                            st.rerun()

        st.divider()
        st.subheader("Cleanup Results")
        if raw_results:
            res_list = [json.loads(res) for res in raw_results]
            res_labels = [f"{res['race_date']} - {res['name']} ({res['distance']})" for res in res_list]
            to_del = st.selectbox("Select Result to Delete", res_labels)
            if st.button("Confirm Delete Result"):
                idx = res_labels.index(to_del)
                res_list.pop(idx)
                r.delete("race_results")
                if res_list: r.rpush("race_results", *[json.dumps(res) for res in res_list])
                st.rerun()
    else: st.error("Admin login required.")
