import streamlit as st
import json
import pandas as pd
from helpers import get_redis

st.set_page_config(page_title="Race Log", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("📖 Standard PB Race Log")
raw_results = r.lrange("race_results", 0, -1)

if raw_results:
    data_list = [json.loads(res) for res in raw_results]
    for i, d in enumerate(data_list): d['idx'] = i
    df = pd.DataFrame(data_list)
    
    st.dataframe(df[['race_date', 'name', 'distance', 'time_display', 'location']], use_container_width=True, hide_index=True)
    
    st.divider()
    to_del = st.selectbox("Select Record to Delete", data_list, format_func=lambda x: f"{x['race_date']} - {x['name']} ({x['time_display']})")
    if st.button("Delete Record"):
        r.lset("race_results", to_del['idx'], "TO_DELETE")
        r.lrem("race_results", 1, "TO_DELETE")
        st.success("Deleted."); st.rerun()
