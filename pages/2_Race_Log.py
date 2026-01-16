import streamlit as st
import json
from helpers import get_redis, format_time_string, time_to_seconds

# Page Config
st.set_page_config(page_title="Race Log", layout="wide")

r = get_redis()

# --- PERSISTENT URL-BASED AUTHENTICATION ---
if st.query_params.get("access") == "granted":
    st.session_state['authenticated'] = True

if not st.session_state.get('authenticated'):
    st.warning("Please login on the Home page to access this section.")
    st.stop()

st.header("📋 Master Record Log")
results = r.lrange("race_results", 0, -1)
for idx, val in enumerate(results):
    item = json.loads(val)
    with st.container(border=True):
        c1, c2 = st.columns([4,1])
        c1.write(f"**{item['name']}** - {item['distance']} - {item['time_display']} ({item['race_date']})")
        if c2.button("🗑️ Delete", key=f"del_{idx}"):
            # Your specific WIPE and REMOVE logic preserved
            r.lset("race_results", idx, "WIPE")
            r.lrem("race_results", 1, "WIPE")
            st.rerun()
