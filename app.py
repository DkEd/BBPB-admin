import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- SECURE UPSTASH CONNECTION ---
redis_url = os.environ.get("REDIS_URL")

def check_redis():
    try:
        test_r = redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
        test_r.ping()
        test_r.set("connection_test", "ok", ex=5)
        return "✅ Connected (Read/Write)"
    except redis.exceptions.NoPermissionError:
        return "⚠️ Connected (READ ONLY - Check Upstash URL)"
    except Exception as e:
        return f"❌ Connection Failed: {str(e)}"

# Global Redis Instance
try:
    r = redis.from_url(redis_url, decode_responses=True)
except:
    pass

# --- UI SETUP ---
st.set_page_config(page_title="Club Leaderboard", layout="wide")

with st.sidebar:
    st.header("System Status")
    st.write(check_redis())
    st.divider()
    st.info("Logic: Age Category is calculated based on Age at the time of the Race Date.")

st.title("🏆 Club Leaderboard")

# --- CORE LOGIC ---
def get_category(dob_str, race_date_str):
    dob = datetime.strptime(dob_str, '%Y-%m-%d')
    race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
    age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
    if age < 40: return "Senior"
    if age < 50: return "V40"
    if age < 60: return "V50"
    if age < 70: return "V60"
    return "V70"

def time_to_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return None

tab1, tab2, tab3 = st.tabs(["Leaderboard", "Add Result", "Admin Tools"])

# --- TAB 1: LEADERBOARD ---
with tab1:
    view = st.radio("Display Filter", ["All-Time Records", "2026 Season"], horizontal=True)
    try:
        raw_results = r.lrange("race_results", 0, -1)
        if raw_results:
            df = pd.DataFrame([json.loads(res) for res in raw_results])
            if view == "2026 Season":
                df = df[pd.to_datetime(df['race_date']).dt.year == 2026]
            
            # Category is calculated dynamically from stored DOB and Race Date
            df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date']), axis=1)
            
            for d in ["Marathon", "HM", "10 Mile", "10k", "5k"]:
                st.header(f"🏁 {d}")
                m_col, f_col = st.columns(2)
                for gen, col in [("Male", m_col), ("Female", f_col)]:
                    with col:
                        st.subheader(gen)
                        subset = df[(df['distance'] == d) & (df['gender'] == gen)]
                        leaders = subset.sort_values('time_seconds').groupby('Category').head(1)
                        if not leaders.empty:
                            cat_order = ["Senior", "V40", "V50", "V60", "V70"]
                            leaders['Category'] = pd.Categorical(leaders['Category'], categories=cat_order, ordered=True)
                            res_table = leaders.sort_values('Category')[['Category', 'name', 'time_display', 'location', 'race_date']]
                            res_table.columns = ['Cat', 'Who', 'Time', 'Where', 'When']
                            st.table(res_table.set_index('Cat'))
                        else: st.write("_No records_")
        else: st.info("Database is empty. Add results to see the board.")
    except:
        st.error("Connection Error: Check your Redis URL.")

# --- TAB 2: ADD RESULT ---
with tab2:
    st.header("Log a Race Result")
    try:
        members = [json.loads(m) for m in r.lrange("members", 0, -1)]
        if members:
            with st.form("race_form", clear_on_submit=True):
                name_sel = st.selectbox("Select Runner", sorted([m['name'] for m in members]))
                m_info = next(i for i in members if i["name"] == name_sel)
                
                dist = st.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"])
                t_str = st.text_input("Time (HH:MM:SS)", "00:00:00")
                loc = st.text_input("Where (Location)")
                dt = st.date_input("When (Race Date)")
                
                if st.form_submit_button("Submit Result"):
                    secs = time_to_seconds(t_str)
                    if secs and loc:
                        # EVERYTHING needed for the leaderboard is saved here
                        entry = {
                            "name": name_sel, 
                            "gender": m_info['gender'], 
                            "dob": m_info['dob'], 
                            "distance": dist, 
                            "time_seconds": secs, 
                            "time_display": t_str, 
                            "location": loc, 
                            "race_date": dt.strftime('%Y-%m-%d')
                        }
                        r.rpush("race_results", json.dumps(entry))
                        st.success(f"Result for {name_sel} saved to Upstash!")
                        st.rerun()
        else:
            st.warning("No members found. Register runners in Admin Tools first.")
    except:
        st.error("Database connection issue.")

# --- TAB 3: ADMIN TOOLS ---
with tab3:
    st.header("Register Member")
    with st.form("mem_form", clear_on_submit=True):
        n = st.text_input("Full Name")
        g = st.selectbox("Gender", ["Male", "Female"])
        b = st.date_input("Date of Birth", 
                          value=date(1985, 1, 1), 
                          min_value=date(1920, 1, 1), 
                          max_value=date.today())
        
        if st.form_submit_button("Add Member"):
            if n and b:
                try:
                    # Saves the permanent member profile
                    r.rpush("members", json.dumps({"name":n, "gender":g, "dob":b.strftime('%Y-%m-%d')}))
                    st.success(f"{n} registered successfully!")
                    st.rerun()
                except redis.exceptions.NoPermissionError:
                    st.error("WRITE ERROR: Check your Upstash URL (likely Read-Only).")
            else:
                st.error("Name and Date of Birth are required.")

    st.divider()
    st.subheader("Data Management")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Delete Last Race Result"):
            r.rpop("race_results")
            st.rerun()
    with col2:
        if st.button("👤 Delete Last Member Added"):
            r.rpop("members")
            st.rerun()
