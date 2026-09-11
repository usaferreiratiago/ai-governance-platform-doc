from pathlib import Path
import streamlit as st

ASSETS_DIR = Path(__file__).parent / 'assets'

def render_header():
    logo_path = ASSETS_DIR / 'powerbi_logo.png'

    col1, col2 = st.columns([1, 5])

    with col1:
        st.image(str(logo_path), width=90)

    with col2:
        st.markdown(
            '<h1 style="margin-bottom:0;">AI Governance Dashboard</h1>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="color:#666;margin-top:0;">Power BI • BigQuery • MCP • LLM Governance</p>',
            unsafe_allow_html=True,
        )

    st.divider()