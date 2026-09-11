import sys
from pathlib import Path

# ---------------------------------------------------------------------
# Load environment variables from .env file (before any other imports)
# ---------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    # .env is in the project root (one level up from this file)
    ROOT_DIR = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=ROOT_DIR / '.env')
except ImportError:
    # dotenv not installed – fallback to system env vars (no warning)
    pass

# ---------------------------------------------------------------------
# Ensure project root is available when Streamlit runs the app
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# ---------------------------------------------------------------------
# Streamlit must be imported before any Streamlit command is executed
# ---------------------------------------------------------------------
import streamlit as st


# ---------------------------------------------------------------------
# Streamlit page configuration (must be the first Streamlit command)
# ---------------------------------------------------------------------
st.set_page_config(
    page_title='AI Governance',
    page_icon='📊',
    layout='wide',
)


# ---------------------------------------------------------------------
# Application imports
# ---------------------------------------------------------------------
from streamlit_app.auth import login
from streamlit_app.components import render_header
from mcp.query_service import ask_semantic_model
from guardrails.db_guardrails import get_all_measures_with_filters, get_mandatory_filters


# ---------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------
login()


# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
render_header()

st.success('Application healthy')


# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'selected_organization' not in st.session_state:
    st.session_state.selected_organization = 'Retail'

if 'selected_date_filter' not in st.session_state:
    st.session_state.selected_date_filter = 'Q2 2026'

if 'available_measures' not in st.session_state:
    st.session_state.available_measures = get_all_measures_with_filters()


# ---------------------------------------------------------------------
# Sidebar - Filters and Configuration
# ---------------------------------------------------------------------
with st.sidebar:
    st.header('🔧 Filters & Configuration')
    
    # Organization selector
    organization = st.selectbox(
        '🏢 Organization',
        ['Retail', 'E-commerce', 'Wholesale', 'All'],
        index=['Retail', 'E-commerce', 'Wholesale', 'All'].index(st.session_state.selected_organization) 
        if st.session_state.selected_organization in ['Retail', 'E-commerce', 'Wholesale', 'All'] 
        else 0,
        help='Select the organization to filter data'
    )
    st.session_state.selected_organization = organization
    
    # Date filter
    date_options = ['Q1 2026', 'Q2 2026', 'Q3 2026', 'Q4 2026', '2026', '2025', 'All']
    date_filter = st.selectbox(
        '📅 Date Filter',
        date_options,
        index=date_options.index(st.session_state.selected_date_filter) 
        if st.session_state.selected_date_filter in date_options 
        else 0,
        help='Select the time period for analysis'
    )
    st.session_state.selected_date_filter = date_filter
    
    st.divider()
    
    # Available measures
    st.header('📊 Available Measures')
    measures = get_all_measures_with_filters()
    for measure, filters in measures.items():
        with st.expander(f"📌 {measure}"):
            st.write(f"**Mandatory Filters:** {', '.join(filters)}")
    
    st.divider()
    
    # Session controls
    st.header('💬 Session')
    st.write(f'Messages: **{len(st.session_state.chat_history)}**')
    
    if st.button('🗑️ Clear conversation', use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    st.divider()
    
    # Environment info
    st.header('⚙️ Environment')
    import os
    mock_mode = os.getenv('MCP_MOCK_MODE', 'true')
    st.write(f'**Mock mode:** `{mock_mode}`')
    
    st.divider()
    
    st.header('🛡️ Governance')
    st.markdown('''
    - ✅ Prompt Injection Protection
    - ✅ Semantic Allowlist
    - ✅ Mandatory Filters
    - ✅ Response Validation
    - ✅ Audit Logging
    ''')


# ---------------------------------------------------------------------
# Introduction
# ---------------------------------------------------------------------
st.markdown('''
## 💬 Ask Questions About Your Semantic Model

Ask questions about the governed Power BI semantic model. The system will:
1. **Validate** your question against guardrails
2. **Check** mandatory filters (Date, Organization, etc.)
3. **Route** to the appropriate semantic domain
4. **Generate** an answer from the approved model

### 📝 Examples:
- **"What was net revenue in Q2 2026?"**
- **"Show gross margin by month"**
- **"What is average unit price?"**
- **"Show the information about the tables"**
''')


# ---------------------------------------------------------------------
# Render chat history
# ---------------------------------------------------------------------
for message in st.session_state.chat_history:
    with st.chat_message(message['role']):
        st.markdown(message['content'])
        if message.get('source'):
            st.caption(f"Source: {message['source']}")


# ---------------------------------------------------------------------
# Chat input with filters
# ---------------------------------------------------------------------
question = st.chat_input('Ask a business question...')


# ---------------------------------------------------------------------
# Process question
# ---------------------------------------------------------------------
if question:
    # Store user message
    st.session_state.chat_history.append({
        'role': 'user',
        'content': question,
    })
    
    # Render user message
    with st.chat_message('user'):
        st.markdown(question)
    
    # Build filters from sidebar selections
    provided_filters = {}
    
    if st.session_state.selected_organization and st.session_state.selected_organization != 'All':
        provided_filters['Organization'] = st.session_state.selected_organization
    
    if st.session_state.selected_date_filter and st.session_state.selected_date_filter != 'All':
        provided_filters['Date'] = st.session_state.selected_date_filter
    
    # Call semantic model with filters
    with st.spinner('🔍 Analyzing the semantic model...'):
        result = ask_semantic_model(
            question=question,
            provided_filters=provided_filters
        )
    
    # Extract answer
    answer = 'No answer available.'
    source = None
    missing_filters = []
    
    if isinstance(result, dict):
        answer = result.get('answer', answer)
        source = result.get('source')
        missing_filters = result.get('missing_filters', [])
    
    elif isinstance(result, str):
        answer = result
    
    # Display warning if filters are missing
    if missing_filters:
        st.warning(f"⚠️ Missing mandatory filters: {', '.join(missing_filters)}")
    
    # Store assistant message
    st.session_state.chat_history.append({
        'role': 'assistant',
        'content': answer,
        'source': source,
    })
    
    # Render assistant message
    with st.chat_message('assistant'):
        st.markdown(answer)
        if source:
            st.caption(f"Source: {source}")


# ---------------------------------------------------------------------
# Footer with filter information
# ---------------------------------------------------------------------
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption(f"🏢 Organization: {st.session_state.selected_organization}")

with col2:
    st.caption(f"📅 Date: {st.session_state.selected_date_filter}")

with col3:
    st.caption(f"💬 Messages: {len(st.session_state.chat_history)}")