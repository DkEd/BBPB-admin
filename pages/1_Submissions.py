import streamlit as st
import json
from helpers import get_redis, format_time_string, time_to_seconds

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("📥 Review & Approvals")

# Load members for the dropdown assignment
raw_mem = r.lrange("members", 0, -1)
members_data = [json.loads(m) for m in raw_mem]
member_names = sorted([m['name'] for m in members_data])

# --- PENDING PB SECTION ---
st.subheader("Pending Public Submissions")
pending = r.lrange("pending_results", 0, -1)

if not pending:
    st.info("No pending submissions to review.")

for i, p_json in enumerate(pending):
    p = json.loads(p_json)
    
    # Check if name exists in our database
    match = next((m for m in members_data if m['name'].lower() == p['name'].lower()), None)
    
    with st.container(border=True):
        st.markdown(f"#### Submission from: `{p['name']}`")
        if not match:
            st.warning("⚠️ Name not found in Member List. Please assign to a correct member below.")
        
        col1, col2, col3 = st.columns(3)
        
        # 1. Edit/Assign Member
        # We default to the submitted name if it matches, otherwise you pick from list
        default_idx = member_names.index(match['name']) if match else 0
        assigned_name = col1.selectbox("Assign to Member", member_names, index=default_idx, key=f"name_{i}")
        
        # 2. Edit Distance & Time
        dist = col2.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"], 
                              index=["5k", "10k", "10 Mile", "HM", "Marathon"].index(p['distance']), 
                              key=f"dist_{i}")
        
        time_val = col3.text_input("Time (HH:MM:SS)", value=p['time_display'], key=f"time_{i}")
        
        # 3. Edit Metadata
        col4, col5 = st.columns(2)
        loc_val = col4.text_input("Race Location", value=p['location'], key=f"loc_{i}")
        date_val = col5.text_input("Date (YYYY-MM-DD)", value=p['race_date'], key=f"date_{i}")
        
        # Action Buttons
        btn_col1, btn_col2, _ = st.columns([1, 1, 3])
        
        if btn_col1.button("✅ Approve & Save", key=f"app_{i}"):
            # Re-fetch the correct member data for the assigned name
            final_m = next(m for m in members_data if m['name'] == assigned_name)
            
            entry = {
                "name": assigned_name,
                "gender": final_m['gender'],
                "dob": final_m['dob'],
                "distance": dist,
                "time_seconds": time_to_seconds(time_val),
                "time_display": format_time_string(time_val),
                "location": loc_val,
                "race_date": date_val
            }
            # Add to master, remove from pending
            r.rpush("race_results", json.dumps(entry))
            r.lrem("pending_results", 1, p_json)
            st.success(f"Saved for {assigned_name}!")
            st.rerun()

        if btn_col2.button("🗑️ Reject/Delete", key=f"rej_{i}"):
            r.lrem("pending_results", 1, p_json)
            st.rerun()

st.divider()

# --- MANUAL ADD SECTION (Optional backup) ---
with st.expander("➕ Create Manual PB Entry from Scratch"):
    with st.form("manual_entry"):
        m_name = st.selectbox("Member", member_names)
        m_dist = st.selectbox("Dist", ["5k", "10k", "10 Mile", "HM", "Marathon"])
        m_time = st.text_input("Time (HH:MM:SS)")
        m_loc = st.text_input("Race Name")
        m_date = st.date_input("Date")
        if st.form_submit_button("Add to Leaderboard"):
            m_info = next(m for m in members_data if m['name'] == m_name)
            new_entry = {
                "name": m_name, "gender": m_info['gender'], "dob": m_info['dob'],
                "distance": m_dist, "time_seconds": time_to_seconds(m_time),
                "time_display": format_time_string(m_time),
                "location": m_loc, "race_date": str(m_date)
            }
            r.rpush("race_results", json.dumps(new_entry))
            st.success("Added!")
            st.rerun()
