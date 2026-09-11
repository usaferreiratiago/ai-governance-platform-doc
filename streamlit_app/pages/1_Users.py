import sys
from pathlib import Path

# Ensure project root is available when Streamlit runs pages/*
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from streamlit_app.components import render_header
from streamlit_app.services.audit_service import log_event
from streamlit_app.services.user_service import (
    create_user, 
    get_all_users, 
    toggle_user_active,
    delete_user,
    get_user_statistics
)

# Page configuration
st.set_page_config(
    page_title='User Management',
    page_icon='👥',
    layout='wide',
)

# Render header
render_header()

st.header('👥 User Management')

# ---------------------------------------------------------------------
# Load users from database
# ---------------------------------------------------------------------
def load_users():
    """Load users from database into session state."""
    users = get_all_users()
    st.session_state.users = users
    return users

# Initialize session state
if 'users' not in st.session_state:
    load_users()

# ---------------------------------------------------------------------
# Create User Form
# ---------------------------------------------------------------------
with st.form('create_user', clear_on_submit=True):
    st.subheader('➕ Create New User')

    col1, col2 = st.columns(2)
    
    with col1:
        username = st.text_input('Username *', placeholder='Enter username')
        password = st.text_input('Password *', type='password', placeholder='Enter password')
    
    with col2:
        email = st.text_input('Email', placeholder='user@company.com')
        full_name = st.text_input('Full Name', placeholder='Full name')
        role = st.selectbox('Role', ['VIEWER', 'ANALYST', 'ADMIN'])
    
    submitted = st.form_submit_button('Create User', use_container_width=True)

    if submitted:
        if not username.strip():
            st.warning('Username is required.')
        elif not password.strip():
            st.warning('Password is required.')
        else:
            # Create user in database
            user = create_user(
                username=username.strip(),
                password=password.strip(),
                email=email.strip(),
                full_name=full_name.strip(),
                role=role
            )
            
            if user:
                log_event(
                    st.session_state.get('user', 'system'),
                    f'Created user {username.strip()}',
                    'User',
                    user.get('id', '')
                )
                st.success(f"✅ User '{username}' created successfully!")
                # Reload users
                load_users()
                st.rerun()
            else:
                st.error(f"❌ User '{username}' already exists or invalid data.")

st.divider()

# ---------------------------------------------------------------------
# Existing Users Table
# ---------------------------------------------------------------------
st.subheader('📋 Existing Users')

if not st.session_state.users:
    st.info('No users found. Create one using the form above.')
else:
    for idx, user in enumerate(st.session_state.users):
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 1.5, 1.5, 1.5])

        with col1:
            st.write(f"**{user['username']}**")
        
        with col2:
            st.write(user.get('full_name', user['username']))
        
        with col3:
            st.write(user['role'])
        
        with col4:
            if user['is_active']:
                st.success('✅ Active')
            else:
                st.error('❌ Inactive')
        
        with col5:
            label = 'Deactivate' if user['is_active'] else 'Activate'
            if st.button(label, key=f"toggle_{user['username']}_{idx}"):
                if toggle_user_active(user['username']):
                    log_event(
                        st.session_state.get('user', 'system'),
                        f"Toggled user {user['username']} to {'active' if not user['is_active'] else 'inactive'}",
                        'User',
                        user.get('id', '')
                    )
                    load_users()
                    st.rerun()
                else:
                    st.error("Failed to toggle user status.")
        
        with col6:
            # Don't allow deleting the last admin
            admin_count = sum(1 for u in st.session_state.users if u['role'] == 'ADMIN')
            if user['role'] == 'ADMIN' and admin_count == 1:
                st.button('🗑️ Delete', key=f"delete_{user['username']}_{idx}", disabled=True, 
                          help="Cannot delete the last ADMIN user")
            else:
                if st.button('🗑️ Delete', key=f"delete_{user['username']}_{idx}"):
                    if delete_user(user['username']):
                        log_event(
                            st.session_state.get('user', 'system'),
                            f'Deleted user {user["username"]}',
                            'User',
                            user.get('id', '')
                        )
                        load_users()
                        st.success(f"✅ User '{user['username']}' deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete user.")

        st.divider()

# ---------------------------------------------------------------------
# User Statistics
# ---------------------------------------------------------------------
st.divider()
st.subheader('📊 User Statistics')

stats = get_user_statistics()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric('Total Users', stats.get('total', 0))

with col2:
    st.metric('Active Users', stats.get('active', 0))

with col3:
    st.metric('Inactive Users', stats.get('inactive', 0))

with col4:
    st.metric('Admin Users', stats.get('admin', 0))

# ---------------------------------------------------------------------
# Export Users Data
# ---------------------------------------------------------------------
st.divider()
if st.button('📊 Export Users Data'):
    import pandas as pd
    df = pd.DataFrame(st.session_state.users)
    # Remove sensitive data
    if 'password_hash' in df.columns:
        df = df.drop(columns=['password_hash'])
    csv = df.to_csv(index=False)
    st.download_button(
        label='📥 Download CSV',
        data=csv,
        file_name=f'users_export.csv',
        mime='text/csv'
    )
    