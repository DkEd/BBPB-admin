import streamlit as st
import json
import pandas as pd
from helpers import get_redis

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()
if not st.session_state.get('authenticated'): 
    st.error("Please login on the Home page.")
    st.stop()

st.header("👥 Member Management")
tab_list, tab_add, tab_edit = st.tabs(["Member List", "Add New", "Edit/Delete"])

raw_mem = r.lrange("members", 0, -1)
members = [json.loads(m) for m in raw_mem]
df = pd.DataFrame(members)

with tab_list:
    if not df.empty:
        st.dataframe(df[['name', 'gender', 'dob', 'status']].sort_values('name'), use_container_width=True, hide_index=True)

with tab_add:
    with st.form("new_member"):
        n = st.text_input("Full Name")
        g = st.selectbox("Gender", ["Male", "Female", "Non-Binary"])
        d = st.date_input("DOB")
        if st.form_submit_button("Create Member"):
            r.rpush("members", json.dumps({"name":n, "gender":g, "dob":str(d), "status":"Active"}))
            st.success("Member Created"); st.rerun()

with tab_edit:
    if not df.empty:
        sel = st.selectbox("Select Member", sorted(df['name'].tolist()))
        idx = next(i for i, m in enumerate(members) if m['name'] == sel)
        m = members[idx]
        with st.form("edit_m"):
            un = st.text_input("Name", m['name'])
            ug = st.selectbox("Gender", ["Male", "Female", "Non-Binary"], index=["Male", "Female", "Non-Binary"].index(m['gender']))
            ud = st.text_input("DOB (YYYY-MM-DD)", m['dob'])
            us = st.selectbox("Status", ["Active", "Left"], index=0 if m.get('status')=="Active" else 1)
            if st.form_submit_button("Update"):
                r.lset("members", idx, json.dumps({"name":un, "gender":ug, "dob":ud, "status":us}))
                st.success("Saved"); st.rerun()
