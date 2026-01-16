import streamlit as st
import json
from helpers import get_redis, format_time_string, time_to_seconds

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()
if not st.session_state.get('authenticated'): 
    st.error("Please login on the Home page.")
    st.stop()

st.header("📥 PB Review & Approvals")

raw_mem = r.lrange("members", 0, -1)
members_data = [json.loads(m) for m in raw_mem]
member_names = sorted([m['name'] for m in members_data])

pending = r.lrange("pending_results", 0, -1)
if not pending:
    st.info("No pending PB submissions.")

for i, p_json in enumerate(pending):
    p = json.loads(p_json)
    match = next((m for m in members_data if m['name'].lower() == p['name'].lower()), None)
    
    with st.container(border=True):
        st.markdown(f"#### Submission from: `{p['name']}`")
        if not match: st.warning("⚠️ Name not found in Member List.")
        
        c1, c2, c3 = st.columns(3)
        def_idx = member_names.index(match['name']) if match else 0
        final_name = c1.selectbox("Assign to Member", member_names, index=def_idx, key=f"p_n_{i}")
        final_dist = c2.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"], index=["5k", "10k", "10 Mile", "HM", "Marathon"].index(p['distance']), key=f"p_d_{i}")
        final_time = c3.text_input("Time (HH:MM:SS)", value=p['time_display'], key=f"p_t_{i}")
        
        c4, c5 = st.columns(2)
        final_loc = c4.text_input("Race Name", value=p['location'], key=f"p_l_{i}")
        final_date = c5.text_input("Race Date (YYYY-MM-DD)", value=p['race_date'], key=f"p_da_{i}")
        
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("✅ Approve PB", key=f"p_ok_{i}"):
            m_info = next(m for m in members_data if m['name'] == final_name)
            entry = {
                "name": final_name, "gender": m_info['gender'], "dob": m_info['dob'],
                "distance": final_dist, "time_seconds": time_to_seconds(final_time),
                "time_display": format_time_string(final_time), "location": final_loc, "race_date": final_date
            }
            r.rpush("race_results", json.dumps(entry))
            r.lrem("pending_results", 1, p_json)
            st.rerun()
        if b2.button("🗑️ Reject", key=f"p_rej_{i}"):
            r.lrem("pending_results", 1, p_json); st.rerun()
