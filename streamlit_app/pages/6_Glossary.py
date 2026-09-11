import sys
from pathlib import Path

# Ensure project root is available when Streamlit runs pages/*
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import json
from datetime import datetime

from streamlit_app.components import render_header
from streamlit_app.services.audit_service import log_event

# Import glossary module
try:
    from metadata.glossary import (
        load_glossary_json,
        get_glossary_context,
        find_terms_in_text,
        get_all_terms,
        Glossary,
        GlossaryTerm
    )
    GLOSSARY_AVAILABLE = True
except ImportError as e:
    st.error(f"⚠️ Glossary module not available: {e}")
    GLOSSARY_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title='Glossary Management',
    page_icon='📚',
    layout='wide',
)

# Render header
render_header()

st.header('📚 Business Glossary Management')

# ---------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------
if 'glossary_terms' not in st.session_state:
    st.session_state.glossary_terms = []
    
if 'glossary_search' not in st.session_state:
    st.session_state.glossary_search = ''

if 'glossary_edit_mode' not in st.session_state:
    st.session_state.glossary_edit_mode = False

if 'glossary_selected_term' not in st.session_state:
    st.session_state.glossary_selected_term = None

# ---------------------------------------------------------------------
# Load Glossary Data
# ---------------------------------------------------------------------
def load_glossary():
    """Load glossary from the JSON file."""
    if not GLOSSARY_AVAILABLE:
        return []
    
    try:
        glossary = load_glossary_json()
        if glossary:
            terms = []
            for term in glossary.terms.values():
                terms.append({
                    'business_term': term.business_term,
                    'synonyms': ', '.join(term.synonyms) if term.synonyms else '',
                    'related_measures': ', '.join(term.related_measures) if term.related_measures else '',
                    'category': term.category or '',
                    'table': term.table or '',
                    'field': term.field or '',
                    'description': term.description or ''
                })
            return terms
        return []
    except Exception as e:
        st.error(f"Error loading glossary: {e}")
        return []

def save_glossary(terms_data):
    """Save glossary terms to the JSON file."""
    if not GLOSSARY_AVAILABLE:
        return False
    
    try:
        # Convert to GlossaryTerm objects
        terms = {}
        for term_data in terms_data:
            term = GlossaryTerm(
                business_term=term_data.get('business_term', ''),
                synonyms=term_data.get('synonyms', '').split(', ') if term_data.get('synonyms') else [],
                related_measures=term_data.get('related_measures', '').split(', ') if term_data.get('related_measures') else [],
                description=term_data.get('description', None),
                category=term_data.get('category', None),
                table=term_data.get('table', None),
                field=term_data.get('field', None)
            )
            terms[term.business_term] = term
        
        # Create glossary and save
        glossary = Glossary(terms=terms)
        
        # Save to file
        import json
        from pathlib import Path
        
        GLOSSARY_DIR = ROOT_DIR / 'metadata' / 'gloassary'
        GLOSSARY_FILE = GLOSSARY_DIR / 'business_glossary.json'
        
        with open(GLOSSARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(glossary.to_dict(), f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Error saving glossary: {e}")
        return False

# ---------------------------------------------------------------------
# Load glossary into session state
# ---------------------------------------------------------------------
if not st.session_state.glossary_terms:
    st.session_state.glossary_terms = load_glossary()

# ---------------------------------------------------------------------
# Sidebar - Actions
# ---------------------------------------------------------------------
with st.sidebar:
    st.subheader('🔧 Actions')
    
    # Add new term
    if st.button('➕ Add New Term', use_container_width=True):
        st.session_state.glossary_edit_mode = True
        st.session_state.glossary_selected_term = None
        st.rerun()
    
    # Refresh glossary
    if st.button('🔄 Refresh Glossary', use_container_width=True):
        st.session_state.glossary_terms = load_glossary()
        st.success('Glossary refreshed!')
        st.rerun()
    
    # Export glossary
    if st.button('📥 Export Glossary', use_container_width=True):
        if st.session_state.glossary_terms:
            df = pd.DataFrame(st.session_state.glossary_terms)
            csv = df.to_csv(index=False)
            st.download_button(
                label='Download CSV',
                data=csv,
                file_name=f'glossary_export_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
                key='export_glossary_download'
            )
        else:
            st.warning('No terms to export')
    
    # Import glossary
    uploaded_file = st.file_uploader("📤 Import Glossary (CSV)", type=['csv'])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            # Convert to terms format
            import_terms = df.to_dict('records')
            if st.button('Confirm Import'):
                if save_glossary(import_terms):
                    st.session_state.glossary_terms = import_terms
                    st.success('Glossary imported successfully!')
                    st.rerun()
                else:
                    st.error('Failed to import glossary')
        except Exception as e:
            st.error(f'Error reading CSV: {e}')

st.divider()

# ---------------------------------------------------------------------
# Search and Filter
# ---------------------------------------------------------------------
col_search, col_filter = st.columns([3, 1])

with col_search:
    search_term = st.text_input(
        '🔍 Search Terms',
        placeholder='Search by business term, synonym, or related measure...',
        value=st.session_state.glossary_search,
        key='glossary_search_input'
    )
    st.session_state.glossary_search = search_term

with col_filter:
    categories = list(set([t.get('category', 'Uncategorized') for t in st.session_state.glossary_terms]))
    if categories:
        selected_category = st.selectbox(
            '📂 Filter by Category',
            ['All Categories'] + sorted(categories),
            key='glossary_category_filter'
        )
    else:
        selected_category = 'All Categories'

st.divider()

# ---------------------------------------------------------------------
# Display Glossary Terms
# ---------------------------------------------------------------------

# Apply search and filter
filtered_terms = st.session_state.glossary_terms

if st.session_state.glossary_search:
    search_lower = st.session_state.glossary_search.lower()
    filtered_terms = [
        t for t in filtered_terms
        if search_lower in t.get('business_term', '').lower()
        or search_lower in t.get('synonyms', '').lower()
        or search_lower in t.get('related_measures', '').lower()
        or search_lower in t.get('description', '').lower()
    ]

if selected_category != 'All Categories':
    filtered_terms = [
        t for t in filtered_terms
        if t.get('category', 'Uncategorized') == selected_category
    ]

# Stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric('Total Terms', len(st.session_state.glossary_terms))
with col2:
    st.metric('Filtered Terms', len(filtered_terms))
with col3:
    unique_categories = len(set([t.get('category', 'Uncategorized') for t in st.session_state.glossary_terms]))
    st.metric('Categories', unique_categories)

st.divider()

# ---------------------------------------------------------------------
# Edit/Create Term Form
# ---------------------------------------------------------------------
if st.session_state.glossary_edit_mode:
    st.subheader('✏️ ' + ('Edit Term' if st.session_state.glossary_selected_term else 'Add New Term'))
    
    with st.form('glossary_term_form', clear_on_submit=False):
        # Determine if editing or creating
        is_edit = st.session_state.glossary_selected_term is not None
        selected = st.session_state.glossary_selected_term
        
        # Form fields
        business_term = st.text_input(
            'Business Term *',
            value=selected.get('business_term', '') if is_edit else '',
            placeholder='e.g., Net Revenue'
        )
        
        synonyms = st.text_input(
            'Synonyms (comma-separated)',
            value=selected.get('synonyms', '') if is_edit else '',
            placeholder='e.g., revenue, sales, turnover'
        )
        
        related_measures = st.text_input(
            'Related Measures (comma-separated)',
            value=selected.get('related_measures', '') if is_edit else '',
            placeholder='e.g., Net Revenue, Gross Margin'
        )
        
        category = st.text_input(
            'Category',
            value=selected.get('category', '') if is_edit else '',
            placeholder='e.g., Financial, Sales, Operations'
        )
        
        table = st.text_input(
            'Table Name',
            value=selected.get('table', '') if is_edit else '',
            placeholder='e.g., financials, sales, orders'
        )
        
        field = st.text_input(
            'Field Name',
            value=selected.get('field', '') if is_edit else '',
            placeholder='e.g., net_revenue, gross_margin'
        )
        
        description = st.text_area(
            'Description',
            value=selected.get('description', '') if is_edit else '',
            placeholder='Enter a description of the business term...',
            height=100
        )
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            submitted = st.form_submit_button('💾 Save Term', use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button('❌ Cancel', use_container_width=True):
                st.session_state.glossary_edit_mode = False
                st.session_state.glossary_selected_term = None
                st.rerun()
        
        if submitted:
            if not business_term.strip():
                st.error('Business Term is required.')
            else:
                # Check for duplicate term name (when creating new)
                if not is_edit:
                    duplicates = [t for t in st.session_state.glossary_terms 
                                 if t.get('business_term', '').lower() == business_term.strip().lower()]
                    if duplicates:
                        st.error(f"Term '{business_term}' already exists!")
                    else:
                        # Create new term
                        new_term = {
                            'business_term': business_term.strip(),
                            'synonyms': synonyms.strip(),
                            'related_measures': related_measures.strip(),
                            'category': category.strip(),
                            'table': table.strip(),
                            'field': field.strip(),
                            'description': description.strip()
                        }
                        st.session_state.glossary_terms.append(new_term)
                        
                        if save_glossary(st.session_state.glossary_terms):
                            log_event(
                                st.session_state.get('user', 'system'),
                                f'Added new glossary term: {business_term}'
                            )
                            st.success(f"✅ Term '{business_term}' added successfully!")
                            st.session_state.glossary_edit_mode = False
                            st.rerun()
                        else:
                            st.error('Failed to save glossary')
                else:
                    # Update existing term
                    for idx, term in enumerate(st.session_state.glossary_terms):
                        if term.get('business_term') == selected.get('business_term'):
                            st.session_state.glossary_terms[idx] = {
                                'business_term': business_term.strip(),
                                'synonyms': synonyms.strip(),
                                'related_measures': related_measures.strip(),
                                'category': category.strip(),
                                'table': table.strip(),
                                'field': field.strip(),
                                'description': description.strip()
                            }
                            break
                    
                    if save_glossary(st.session_state.glossary_terms):
                        log_event(
                            st.session_state.get('user', 'system'),
                            f'Updated glossary term: {business_term}'
                        )
                        st.success(f"✅ Term '{business_term}' updated successfully!")
                        st.session_state.glossary_edit_mode = False
                        st.session_state.glossary_selected_term = None
                        st.rerun()
                    else:
                        st.error('Failed to save glossary')
    
    st.divider()

# ---------------------------------------------------------------------
# Display Terms Table
# ---------------------------------------------------------------------
if not filtered_terms:
    st.info('No terms found matching your criteria.')
else:
    # Create a nice display with expandable rows
    for idx, term in enumerate(filtered_terms):
        with st.expander(f"📌 **{term.get('business_term', 'Unknown')}**", expanded=False):
            col_info, col_actions = st.columns([3, 1])
            
            with col_info:
                st.markdown(f"**Description:** {term.get('description', 'No description')}")
                if term.get('synonyms'):
                    st.markdown(f"**Synonyms:** {term.get('synonyms')}")
                if term.get('related_measures'):
                    st.markdown(f"**Related Measures:** {term.get('related_measures')}")
                if term.get('category'):
                    st.markdown(f"**Category:** {term.get('category')}")
                if term.get('table'):
                    st.markdown(f"**Table:** `{term.get('table')}`")
                if term.get('field'):
                    st.markdown(f"**Field:** `{term.get('field')}`")
            
            with col_actions:
                # Edit button
                if st.button('✏️ Edit', key=f"edit_term_{idx}"):
                    st.session_state.glossary_edit_mode = True
                    st.session_state.glossary_selected_term = term
                    st.rerun()
                
                # Delete button with confirmation
                if st.button('🗑️ Delete', key=f"delete_term_{idx}"):
                    # Delete term
                    term_name = term.get('business_term')
                    st.session_state.glossary_terms = [
                        t for t in st.session_state.glossary_terms
                        if t.get('business_term') != term_name
                    ]
                    
                    if save_glossary(st.session_state.glossary_terms):
                        log_event(
                            st.session_state.get('user', 'system'),
                            f'Deleted glossary term: {term_name}'
                        )
                        st.success(f"✅ Term '{term_name}' deleted successfully!")
                        st.rerun()
                    else:
                        st.error('Failed to delete term')

# ---------------------------------------------------------------------
# Glossary Context Preview
# ---------------------------------------------------------------------
st.divider()
with st.expander("📝 View Glossary Context (for prompts)", expanded=False):
    if GLOSSARY_AVAILABLE:
        try:
            context = get_glossary_context()
            st.text_area(
                "Glossary Context",
                value=context,
                height=200,
                disabled=True,
                key="glossary_context_display"
            )
            
            # Copy to clipboard button
            if st.button("📋 Copy Context", key="copy_glossary_context"):
                st.info("Context copied to clipboard (simulated)")
                # In production, use pyperclip or similar
        except Exception as e:
            st.error(f"Error generating context: {e}")
    else:
        st.warning("Glossary module not available")

# ---------------------------------------------------------------------
# Term Finder Tool
# ---------------------------------------------------------------------
st.divider()
st.subheader('🔍 Find Terms in Text')

text_input = st.text_area(
    'Enter text to find glossary terms',
    placeholder='Paste text here to identify business terms...',
    height=100
)

if text_input and GLOSSARY_AVAILABLE:
    try:
        found_terms = find_terms_in_text(text_input)
        if found_terms:
            st.success(f"Found {len(found_terms)} terms:")
            for term in found_terms:
                st.markdown(f"- **{term.business_term}** - {term.description or 'No description'}")
        else:
            st.info('No glossary terms found in the text')
    except Exception as e:
        st.error(f"Error finding terms: {e}")

# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------
st.divider()
st.caption(f"📚 Glossary Management - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")