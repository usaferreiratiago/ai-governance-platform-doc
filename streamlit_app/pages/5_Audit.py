import sys
from pathlib import Path

# Ensure project root is available when Streamlit runs pages/*
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from streamlit_app.components import render_header
from streamlit_app.services.audit_service import get_audit_logs

# Page configuration
st.set_page_config(
    page_title='Audit Log',
    page_icon='🛡️',
    layout='wide',
)

# Render Power BI logo + application header
render_header()

st.header('Audit Log')
st.caption('Review governance, security, and operational events captured by the platform.')

# Controls
col1, col2 = st.columns([1, 3])

with col1:
    limit = st.selectbox(
        'Records',
        options=[50, 100, 200, 500, 1000],
        index=2,
    )

with col2:
    st.markdown(
        '''
Audit records include user actions, prompt publications, benchmark executions,
authentication events, and governance changes.
'''
    )

st.divider()

# Load logs
logs = get_audit_logs(limit=limit)

if logs:
    df = pd.DataFrame(logs)

    # Standardize timestamp column if present
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df = df.sort_values('created_at', ascending=False)

    # KPI summary
    st.subheader('Audit Summary')

    total_events = len(df)
    unique_users = df['user'].nunique() if 'user' in df.columns else 0

    col_a, col_b = st.columns(2)

    with col_a:
        st.metric('Total Events', total_events)

    with col_b:
        st.metric('Unique Users', unique_users)

    st.divider()

    # Filters
    st.subheader('Filters')

    filtered_df = df.copy()

    if 'user' in df.columns:
        users = ['All'] + sorted(df['user'].dropna().unique().tolist())
        selected_user = st.selectbox('User', users)

        if selected_user != 'All':
            filtered_df = filtered_df[filtered_df['user'] == selected_user]

    st.divider()

    # Audit table
    st.subheader('Audit Events')

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # Export section
    st.subheader('Export Audit Logs')

    csv_bytes = filtered_df.to_csv(index=False).encode('utf-8')

    st.download_button(
        label='Download CSV',
        data=csv_bytes,
        file_name='audit_logs.csv',
        mime='text/csv',
        use_container_width=True,
    )

    st.divider()

    # Recent events
    st.subheader('Recent Events')

    preview_df = filtered_df.head(5)

    for _, row in preview_df.iterrows():
        timestamp = row.get('created_at', '')
        user = row.get('user', 'unknown')
        action = row.get('action', '')

        st.markdown(
            f'**{timestamp}** — `{user}` — {action}'
        )

else:
    st.info('No audit events found.')

    st.code(
        'Use the application to generate audit events.',
        language='text',
    )

st.divider()

st.subheader('Governance Notes')

st.markdown(
    '''
- Audit logs should be retained according to enterprise policy.
- Export logs regularly for compliance evidence.
- Investigate failed benchmark executions immediately.
- Review prompt publication history before promoting changes.
- Restrict audit-log access to authorized governance administrators.
'''
)