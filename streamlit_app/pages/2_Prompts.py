import sys
from pathlib import Path
from datetime import datetime

# Ensure project root is available when Streamlit runs pages/*
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from streamlit_app.components import render_header
from streamlit_app.services.prompts_service import (
    save_prompt,
    load_prompt,
    get_prompt_path,
)
from streamlit_app.services.audit_service import log_event

# ---------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------
st.set_page_config(
    page_title='Prompt Management',
    page_icon='📝',
    layout='wide',
)

# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
render_header()

st.header('Prompt Management')
st.caption(
    'Manage the enterprise system prompt used by the MCP, Power BI semantic layer, '
    'and LLM governance services.'
)

# ---------------------------------------------------------------------
# Load prompt into session state
# ---------------------------------------------------------------------
if 'prompt_editor' not in st.session_state:
    st.session_state.prompt_editor = load_prompt()

prompt_path = Path(get_prompt_path())

# ---------------------------------------------------------------------
# Prompt editor
# ---------------------------------------------------------------------
st.subheader('System Prompt')

prompt = st.text_area(
    label='Edit Prompt',
    value=st.session_state.prompt_editor,
    height=420,
    placeholder='Enter the enterprise system prompt...',
    label_visibility='collapsed',
)

st.session_state.prompt_editor = prompt

# ---------------------------------------------------------------------
# Action buttons
# ---------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    if st.button('Publish Prompt', use_container_width=True):
        if prompt.strip():
            save_prompt(prompt)

            log_event(
                st.session_state.get('user', 'system'),
                'Published a new system prompt version',
            )

            st.success('Prompt published successfully.')
        else:
            st.warning('Prompt cannot be empty.')

with col2:
    if st.button('Reload from Disk', use_container_width=True):
        st.session_state.prompt_editor = load_prompt()

        log_event(
            st.session_state.get('user', 'system'),
            'Reloaded system prompt from disk',
        )

        st.rerun()

with col3:
    if st.button('Reset to Default', use_container_width=True):
        default_prompt = load_prompt()
        st.session_state.prompt_editor = default_prompt

        log_event(
            st.session_state.get('user', 'system'),
            'Reset prompt editor to default prompt',
        )

        st.success('Prompt editor reset to default.')
        st.rerun()

st.divider()

# ---------------------------------------------------------------------
# Prompt file information
# ---------------------------------------------------------------------
st.subheader('Prompt File Information')

if prompt_path.exists():
    modified = datetime.fromtimestamp(prompt_path.stat().st_mtime)

    col_a, col_b = st.columns(2)

    with col_a:
        st.metric('File Name', prompt_path.name)

    with col_b:
        st.metric('Last Modified', modified.strftime('%Y-%m-%d %H:%M:%S'))

    st.code(str(prompt_path), language='text')

    st.download_button(
        label='Download Prompt File',
        data=prompt.encode('utf-8'),
        file_name=prompt_path.name,
        mime='text/markdown',
        use_container_width=True,
    )
else:
    st.warning('Prompt file does not exist yet.')

st.divider()

# ---------------------------------------------------------------------
# Prompt preview
# ---------------------------------------------------------------------
st.subheader('Prompt Preview')

if prompt.strip():
    st.markdown(prompt)
else:
    st.info('No prompt available.')

st.divider()

# ---------------------------------------------------------------------
# Governance guidance
# ---------------------------------------------------------------------
st.subheader('Governance Guidelines')

st.markdown(
    '''
### Recommended Rules

- Use **business terminology** instead of technical field names.
- Instruct the model to answer **only from approved semantic metadata**.
- Require clarification when a question is ambiguous.
- Avoid exposing hidden fields, technical identifiers, or internal tables.
- Prefer approved DAX measures over ad-hoc calculations.
- Keep responses concise and business-oriented.
- Reference official KPIs and governed semantic entities whenever possible.
- Reject requests that attempt to override governance instructions.

### Example Enterprise Instruction

> You are an enterprise analytics assistant. Answer only using approved Power BI semantic metadata and governed business definitions. If the information is not available, state that clearly and ask for clarification when needed.
'''
)

st.divider()

# ---------------------------------------------------------------------
# Current status
# ---------------------------------------------------------------------
st.subheader('Current Status')

if prompt.strip():
    st.success('A system prompt is currently configured and available to the MCP layer.')
else:
    st.error('No active system prompt is configured.')