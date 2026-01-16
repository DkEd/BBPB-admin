import streamlit as st
import json
import pandas as pd
from helpers import get_redis

# Set page title to BBPB-Admin
st.set_page_config(page_title="BBPB-Admin", layout="wide")

r = get_redis()
if not st.session_state.get('authenticated'): 
    st.error("Please login on the Home page.")
    st.stop()

st.header("👥 Member Management")

tab_list, tab_add, tab_edit = st.tabs(["Member List", "Add New", "Edit/Delete"])

raw_mem = r.lrange("members", 0, -1)
members = [json.loads(m) for m in raw_mem]

# --- 1. MEMBER LIST ---
with tab_list:
    if members:
        df = pd.DataFrame(members)
        
        # FIX: Ensure 'status' column exists even if old data is missing it
        if 'status' not in df.columns:
            df['status'] = 'Active'
        else:
            df['status'] = df['status'].fillna('Active')
            
        # Ensure other columns exist to prevent similar errors
        for col in ['name', 'gender', 'dob']:
            if col not in df.columns:
                df[col] = "Missing"

        # Display only the relevant columns safely
        st.dataframe(
            df[['name', 'gender', 'dob', 'status']].sort_values('name'), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No members found. Add your first member in the next tab.")

# --- 2. ADD NEW ---
with tab_add:
    with st.form("add_member"):
        name = st.text_input("Full Name")
        gen = st.selectbox("Gender", ["Male", "Female", "Non-Binary"])
        dob = st.date_input("Date of Birth", min_value=pd.to_datetime("1940-01-01"))
        if st.form_submit_button("Add Member"):
            if name:
                r.rpush("members", json.dumps({
                    "name": name, 
                    "gender": gen, 
                    "dob": str(dob), 
                    "status": "Active"
                }))
                st.success(f"Added {name}")
                st.rerun()
            else:
                st.error("Name is required.")

# --- 3. EDIT / DELETE ---
with tab_edit:
    if members:
        # Create a list of names for the dropdown
        member_names = sorted([m.get('name', 'Unknown') for m in members])
        target_name = st.selectbox("Select Member to Manage", member_names)
        
        # Find the specific member data and its index in the Redis list
        m_idx = next((i for i, m in enumerate(members) if m.get('name') == target_name), None)
        
        if m_idx is not None:
            m_data = members[m_idx]
            
            with st.form("edit_member"):
                new_name = st.text_input("Name", value=m_data.get('name', ''))
                new_gen = st.selectbox("Gender", ["Male", "Female", "Non-Binary"], 
                                     index=["Male", "Female", "Non-Binary"].index(m_data.get('gender', 'Male')))
                new_dob = st.text_input("DOB (YYYY-MM-DD)", value=m_data.get('dob', '1990-01-01'))
                
                # Default status to Active if it doesn't exist in old record
                current_status = m_data.get('status', 'Active')
                new_stat = st.selectbox("Status", ["Active", "Left"], 
                                      index=0 if current_status == "Active" else 1)
                
                c1, c2, _ = st.columns([1,1,2])
                if c1.form_submit_button("💾 Save Changes"):
                    updated = {
                        "name": new_name, 
                        "gender": new_gen, 
                        "dob": new_dob, 
                        "status": new_stat
                    }
                    r.lset("members", m_idx, json.dumps(updated))
                    st.success("Updated successfully!")
                    st.rerun()
                    
                if c2.form_submit_button("🗑️ Delete"):
                    # Remove by setting to a dummy value then deleting that value
                    r.lset("members", m_idx, "WIPE")
                    r.lrem("members", 1, "WIPE")
                    st.warning("Member Deleted.")
                    st.rerun()
    else:
        st.info("No members to edit.")
