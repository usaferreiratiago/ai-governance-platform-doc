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

# Import guardrails modules
try:
    from guardrails.mandatory_filters import (
        MandatoryFilterValidator,
        MandatoryFilterRepository,
        validate_filters,
        validate_mandatory_filters,
        validate_required_filters,
        get_missing_filters,
        ValidationResult
    )
    GUARDRAILS_AVAILABLE = True
except ImportError as e:
    st.error(f"⚠️ Guardrails module not available: {e}")
    GUARDRAILS_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title='Guardrails Management',
    page_icon='🛡️',
    layout='wide',
)

# Render header
render_header()

st.header('🛡️ Guardrails & Compliance Management')

# ---------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------
if 'guardrails_measures' not in st.session_state:
    st.session_state.guardrails_measures = {}

if 'guardrails_edit_mode' not in st.session_state:
    st.session_state.guardrails_edit_mode = False

if 'guardrails_selected_measure' not in st.session_state:
    st.session_state.guardrails_selected_measure = None

if 'guardrails_test_query' not in st.session_state:
    st.session_state.guardrails_test_query = ''

if 'guardrails_test_filters' not in st.session_state:
    st.session_state.guardrails_test_filters = {}

# ---------------------------------------------------------------------
# Load Guardrails Data
# ---------------------------------------------------------------------
def load_guardrails():
    """Load mandatory filters from the repository."""
    if not GUARDRAILS_AVAILABLE:
        return get_default_measures()
    
    try:
        repo = MandatoryFilterRepository()
        filters = repo.load()
        return filters
    except Exception as e:
        st.error(f"Error loading guardrails: {e}")
        return get_default_measures()

def get_default_measures():
    """Return default mandatory filters."""
    return {
        'Net Revenue': ['Date'],
        'Gross Margin %': ['Date'],
        'Average Unit Price': ['Date'],
        'Return Rate': ['Date'],
        'Inventory Value': ['Date', 'Warehouse'],
        'Sales': ['Date', 'Region'],
        'Orders': ['Date', 'Status'],
        'Customer Count': ['Date', 'Segment'],
        'Profit': ['Date', 'Product Category'],
        'Expenses': ['Date', 'Department']
    }

def save_guardrails(measures_data):
    """Save mandatory filters to the repository."""
    if not GUARDRAILS_AVAILABLE:
        return False
    
    try:
        repo = MandatoryFilterRepository()
        repo.save(measures_data)
        return True
    except Exception as e:
        st.error(f"Error saving guardrails: {e}")
        return False

# Load guardrails into session state
if not st.session_state.guardrails_measures:
    st.session_state.guardrails_measures = load_guardrails()

# ---------------------------------------------------------------------
# Sidebar - Actions
# ---------------------------------------------------------------------
with st.sidebar:
    st.subheader('🔧 Actions')
    
    # Add new measure
    if st.button('➕ Add New Measure', use_container_width=True):
        st.session_state.guardrails_edit_mode = True
        st.session_state.guardrails_selected_measure = None
        st.rerun()
    
    # Refresh guardrails
    if st.button('🔄 Refresh Rules', use_container_width=True):
        st.session_state.guardrails_measures = load_guardrails()
        st.success('Guardrails refreshed!')
        st.rerun()
    
    # Export guardrails
    if st.button('📥 Export Rules', use_container_width=True):
        if st.session_state.guardrails_measures:
            export_data = []
            for measure, filters in st.session_state.guardrails_measures.items():
                export_data.append({
                    'measure': measure,
                    'mandatory_filters': ', '.join(filters)
                })
            df = pd.DataFrame(export_data)
            csv = df.to_csv(index=False)
            st.download_button(
                label='Download CSV',
                data=csv,
                file_name=f'guardrails_export_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
                key='export_guardrails_download'
            )
        else:
            st.warning('No rules to export')
    
    # Import guardrails
    uploaded_file = st.file_uploader("📤 Import Rules (CSV)", type=['csv'])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            import_data = {}
            for _, row in df.iterrows():
                measure = row.get('measure', '')
                filters = [f.strip() for f in row.get('mandatory_filters', '').split(',') if f.strip()]
                if measure and filters:
                    import_data[measure] = filters
            
            if import_data and st.button('Confirm Import'):
                if save_guardrails(import_data):
                    st.session_state.guardrails_measures = import_data
                    st.success('Guardrails imported successfully!')
                    st.rerun()
                else:
                    st.error('Failed to import guardrails')
        except Exception as e:
            st.error(f'Error reading CSV: {e}')

st.divider()

# ---------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric('Total Measures', len(st.session_state.guardrails_measures))

with col2:
    total_filters = sum(len(filters) for filters in st.session_state.guardrails_measures.values())
    st.metric('Total Mandatory Filters', total_filters)

with col3:
    avg_filters = total_filters / len(st.session_state.guardrails_measures) if st.session_state.guardrails_measures else 0
    st.metric('Avg Filters per Measure', f'{avg_filters:.1f}')

st.divider()

# ---------------------------------------------------------------------
# Edit/Create Measure Form
# ---------------------------------------------------------------------
if st.session_state.guardrails_edit_mode:
    st.subheader('✏️ ' + ('Edit Measure' if st.session_state.guardrails_selected_measure else 'Add New Measure'))
    
    with st.form('guardrails_measure_form', clear_on_submit=False):
        is_edit = st.session_state.guardrails_selected_measure is not None
        selected = st.session_state.guardrails_selected_measure or {}
        
        # Measure name
        measure_name = st.text_input(
            'Measure Name *',
            value=selected.get('name', '') if is_edit else '',
            placeholder='e.g., Net Revenue, Gross Margin %'
        )
        
        # Mandatory filters
        st.subheader('🔒 Mandatory Filters')
        filters_str = st.text_area(
            'Filter Names (comma-separated)',
            value=selected.get('filters', '') if is_edit else '',
            placeholder='e.g., Date, Warehouse, Region, Category',
            help='These filters are required before executing queries for this measure'
        )
        filters = [f.strip() for f in filters_str.split(',') if f.strip()]
        
        # Additional options
        st.subheader('⚙️ Additional Options')
        
        col_required, col_optional = st.columns(2)
        
        with col_required:
            require_all = st.checkbox(
                'Require ALL filters',
                value=selected.get('require_all', True) if is_edit else True,
                help='If checked, all filters are mandatory. If unchecked, at least one is required.'
            )
        
        with col_optional:
            case_sensitive = st.checkbox(
                'Case Sensitive Validation',
                value=selected.get('case_sensitive', False) if is_edit else False,
                help='If checked, filter names must match case exactly.'
            )
        
        # Description
        description = st.text_area(
            'Description (optional)',
            value=selected.get('description', '') if is_edit else '',
            placeholder='Describe the purpose of this measure and its mandatory filters...',
            height=80
        )
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            submitted = st.form_submit_button('💾 Save Measure', use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button('❌ Cancel', use_container_width=True):
                st.session_state.guardrails_edit_mode = False
                st.session_state.guardrails_selected_measure = None
                st.rerun()
        
        if submitted:
            if not measure_name.strip():
                st.error('Measure Name is required.')
            elif not filters:
                st.error('At least one mandatory filter is required.')
            else:
                # Check for duplicate measure name (when creating new)
                if not is_edit:
                    if measure_name in st.session_state.guardrails_measures:
                        st.error(f"Measure '{measure_name}' already exists!")
                    else:
                        # Create new measure
                        st.session_state.guardrails_measures[measure_name] = filters
                        
                        if save_guardrails(st.session_state.guardrails_measures):
                            log_event(
                                st.session_state.get('user', 'system'),
                                f'Added new guardrail measure: {measure_name} with filters: {filters}'
                            )
                            st.success(f"✅ Measure '{measure_name}' added successfully!")
                            st.session_state.guardrails_edit_mode = False
                            st.rerun()
                        else:
                            st.error('Failed to save guardrails')
                else:
                    # Update existing measure
                    old_name = selected.get('name')
                    if old_name != measure_name:
                        # Remove old entry and add new one
                        if measure_name in st.session_state.guardrails_measures and measure_name != old_name:
                            st.error(f"Measure '{measure_name}' already exists!")
                        else:
                            del st.session_state.guardrails_measures[old_name]
                            st.session_state.guardrails_measures[measure_name] = filters
                    else:
                        # Just update filters
                        st.session_state.guardrails_measures[measure_name] = filters
                    
                    if save_guardrails(st.session_state.guardrails_measures):
                        log_event(
                            st.session_state.get('user', 'system'),
                            f'Updated guardrail measure: {measure_name}'
                        )
                        st.success(f"✅ Measure '{measure_name}' updated successfully!")
                        st.session_state.guardrails_edit_mode = False
                        st.session_state.guardrails_selected_measure = None
                        st.rerun()
                    else:
                        st.error('Failed to save guardrails')
    
    st.divider()

# ---------------------------------------------------------------------
# Display All Measures
# ---------------------------------------------------------------------
st.subheader('📋 Mandatory Filters by Measure')

if not st.session_state.guardrails_measures:
    st.info('No guardrails defined. Add a new measure using the sidebar.')
else:
    # Sort measures alphabetically
    sorted_measures = sorted(st.session_state.guardrails_measures.items())
    
    for measure, filters in sorted_measures:
        with st.expander(f"📌 **{measure}**", expanded=False):
            col_info, col_actions = st.columns([3, 1])
            
            with col_info:
                st.markdown(f"**Mandatory Filters ({len(filters)}):**")
                for filter_name in filters:
                    st.markdown(f"- 🔒 `{filter_name}`")
            
            with col_actions:
                # Edit button
                if st.button('✏️ Edit', key=f"edit_guardrail_{measure}"):
                    st.session_state.guardrails_edit_mode = True
                    st.session_state.guardrails_selected_measure = {
                        'name': measure,
                        'filters': ', '.join(filters)
                    }
                    st.rerun()
                
                # Delete button with confirmation
                if st.button('🗑️ Delete', key=f"delete_guardrail_{measure}"):
                    del st.session_state.guardrails_measures[measure]
                    
                    if save_guardrails(st.session_state.guardrails_measures):
                        log_event(
                            st.session_state.get('user', 'system'),
                            f'Deleted guardrail measure: {measure}'
                        )
                        st.success(f"✅ Measure '{measure}' deleted successfully!")
                        st.rerun()
                    else:
                        st.error('Failed to delete measure')

# ---------------------------------------------------------------------
# Validation Testing Tool
# ---------------------------------------------------------------------
st.divider()
st.subheader('🧪 Guardrails Validation Tester')

col_test, col_results = st.columns(2)

with col_test:
    # Select measure
    measure_options = list(st.session_state.guardrails_measures.keys())
    selected_measure = st.selectbox(
        'Select Measure',
        [''] + measure_options,
        key='test_measure_select'
    )
    
    if selected_measure:
        # Show expected filters
        expected_filters = st.session_state.guardrails_measures.get(selected_measure, [])
        st.info(f"Expected filters: {', '.join(expected_filters) if expected_filters else 'None'}")
        
        # Test filters input
        st.subheader('Provided Filters')
        filter_input = st.text_area(
            'Enter provided filters (comma-separated)',
            placeholder='e.g., Date, Region, Warehouse',
            value=st.session_state.guardrails_test_filters.get(selected_measure, ''),
            key='test_filters_input'
        )
        
        # Store in session state
        st.session_state.guardrails_test_filters[selected_measure] = filter_input
        
        # Run validation
        if st.button('🔍 Validate Filters', use_container_width=True, key='validate_filters_btn'):
            provided_filters = [f.strip() for f in filter_input.split(',') if f.strip()]
            
            if GUARDRAILS_AVAILABLE:
                # Use the actual validation
                validator = MandatoryFilterValidator()
                result = validator.validate(selected_measure, {f: '' for f in provided_filters})
                
                st.session_state.guardrails_test_result = {
                    'measure': selected_measure,
                    'provided': provided_filters,
                    'expected': expected_filters,
                    'passed': result.passed,
                    'message': result.message,
                    'missing': result.missing_filters
                }
            else:
                # Fallback validation
                missing = [f for f in expected_filters if f not in provided_filters]
                passed = len(missing) == 0
                
                st.session_state.guardrails_test_result = {
                    'measure': selected_measure,
                    'provided': provided_filters,
                    'expected': expected_filters,
                    'passed': passed,
                    'message': 'Validation completed (fallback mode)',
                    'missing': missing
                }
            
            st.rerun()

with col_results:
    # Display results
    if 'guardrails_test_result' in st.session_state:
        result = st.session_state.guardrails_test_result
        
        st.subheader('📊 Validation Results')
        
        # Status
        if result['passed']:
            st.success('✅ PASSED - All mandatory filters are present!')
        else:
            st.error('❌ FAILED - Some mandatory filters are missing!')
        
        # Details
        st.write('**Measure:**', result['measure'])
        st.write('**Provided Filters:**', ', '.join(result['provided']) if result['provided'] else 'None')
        st.write('**Expected Filters:**', ', '.join(result['expected']) if result['expected'] else 'None')
        
        if result.get('missing'):
            st.write('**Missing Filters:**')
            for missing in result['missing']:
                st.error(f"- 🔴 {missing}")
        
        st.write('**Message:**', result['message'])

# ---------------------------------------------------------------------
# Guardrails Log
# ---------------------------------------------------------------------
st.divider()
with st.expander("📋 Guardrails Validation History", expanded=False):
    # Show recent validations (mock data)
    history_data = [
        {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'measure': 'Net Revenue', 'status': '✅ Passed'},
        {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'measure': 'Inventory Value', 'status': '❌ Failed'},
        {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'measure': 'Sales', 'status': '✅ Passed'},
    ]
    df_history = pd.DataFrame(history_data)
    st.dataframe(df_history, use_container_width=True)

# ---------------------------------------------------------------------
# Best Practices Info
# ---------------------------------------------------------------------
with st.expander("📚 Guardrails Best Practices", expanded=False):
    st.markdown("""
    ### 🔒 Mandatory Filters Best Practices
    
    **1. Define Clear Filters**
    - Each measure should have well-defined mandatory filters
    - Use consistent naming conventions
    
    **2. Balance Rigor and Flexibility**
    - Don't over-constrain with too many filters
    - Ensure all security and compliance requirements are met
    
    **3. Document Filters**
    - Clearly describe each filter's purpose
    - Maintain documentation for downstream users
    
    **4. Regular Review**
    - Review mandatory filters periodically
    - Update filters as business needs change
    
    **5. Testing**
    - Test validation rules with sample queries
    - Verify error messages are clear and helpful
    
    **6. Security Considerations**
    - Filters can enforce data access policies
    - Consider using filters for row-level security
    """)

# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------
st.divider()
st.caption(f"🛡️ Guardrails Management - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")