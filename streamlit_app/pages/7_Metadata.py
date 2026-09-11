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

# Import metadata service
try:
    from mcp.metadata_service import (
        get_table_metadata,
        get_all_tables,
        build_semantic_context
    )
    METADATA_AVAILABLE = True
except ImportError as e:
    st.error(f"⚠️ Metadata module not available: {e}")
    METADATA_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title='Metadata Management',
    page_icon='📊',
    layout='wide',
)

# Render header
render_header()

st.header('📊 Semantic Model Metadata Management')

# ---------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------
if 'metadata_tables' not in st.session_state:
    st.session_state.metadata_tables = []
    
if 'metadata_selected_table' not in st.session_state:
    st.session_state.metadata_selected_table = None

if 'metadata_edit_mode' not in st.session_state:
    st.session_state.metadata_edit_mode = False

if 'metadata_search' not in st.session_state:
    st.session_state.metadata_search = ''

# ---------------------------------------------------------------------
# Helper Functions for Column Handling
# ---------------------------------------------------------------------
def get_column_name(col):
    """
    Extract column name from either string or dict format.
    
    Args:
        col: Column name as string or dict with 'name' key
    
    Returns:
        str: Column name
    """
    if isinstance(col, dict):
        return col.get('name', str(col))
    return str(col)

def get_columns_list(table):
    """
    Get list of column names from a table, handling both string and dict formats.
    
    Args:
        table: Table dict with 'columns' key
    
    Returns:
        list: List of column names as strings
    """
    columns = table.get('columns', [])
    if not columns:
        return []
    
    if isinstance(columns, list):
        return [get_column_name(col) for col in columns]
    return []

def has_column(table, column_name):
    """
    Check if a table has a specific column.
    
    Args:
        table: Table dict
        column_name: Column name to check
    
    Returns:
        bool: True if column exists
    """
    columns = get_columns_list(table)
    return column_name in columns

# ---------------------------------------------------------------------
# Load Metadata
# ---------------------------------------------------------------------
def load_metadata():
    """Load metadata from available sources."""
    if not METADATA_AVAILABLE:
        return get_default_metadata()
    
    try:
        tables = get_all_tables()
        if tables:
            return tables
        return get_default_metadata()
    except Exception as e:
        st.error(f"Error loading metadata: {e}")
        return get_default_metadata()

def get_default_metadata():
    """Return default metadata structure."""
    return [
        {
            'name': 'financials',
            'description': 'Financial data including revenue, margins, and costs',
            'columns': ['date', 'net_revenue', 'gross_margin', 'cost_of_goods', 'operating_expenses'],
            'primary_key': 'date',
            'foreign_keys': []
        },
        {
            'name': 'sales',
            'description': 'Sales transaction data including products and customers',
            'columns': ['date', 'product_id', 'customer_id', 'sales_total', 'quantity', 'unit_price'],
            'primary_key': 'sale_id',
            'foreign_keys': ['product_id', 'customer_id']
        },
        {
            'name': 'orders',
            'description': 'Order data including status and amounts',
            'columns': ['order_id', 'order_date', 'customer_id', 'status', 'total_amount', 'shipping_cost'],
            'primary_key': 'order_id',
            'foreign_keys': ['customer_id']
        },
        {
            'name': 'customers',
            'description': 'Customer master data including demographics',
            'columns': ['customer_id', 'name', 'email', 'phone', 'region', 'created_at', 'active'],
            'primary_key': 'customer_id',
            'foreign_keys': []
        },
        {
            'name': 'products',
            'description': 'Product master data including category and pricing',
            'columns': ['product_id', 'name', 'category', 'subcategory', 'unit_price', 'cost', 'supplier_id'],
            'primary_key': 'product_id',
            'foreign_keys': ['supplier_id']
        },
        {
            'name': 'inventory',
            'description': 'Inventory data including stock levels and warehouse information',
            'columns': ['product_id', 'warehouse', 'inventory_value', 'stock_quantity', 'reorder_level', 'last_updated'],
            'primary_key': 'inventory_id',
            'foreign_keys': ['product_id']
        }
    ]

def save_metadata(tables_data):
    """Save metadata to file."""
    try:
        # Save to JSON file
        metadata_file = ROOT_DIR / 'metadata' / 'tables_metadata.json'
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(tables_data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Error saving metadata: {e}")
        return False

# ---------------------------------------------------------------------
# Load metadata into session state
# ---------------------------------------------------------------------
if not st.session_state.metadata_tables:
    st.session_state.metadata_tables = load_metadata()

# ---------------------------------------------------------------------
# Sidebar - Actions
# ---------------------------------------------------------------------
with st.sidebar:
    st.subheader('🔧 Actions')
    
    # Add new table
    if st.button('➕ Add New Table', use_container_width=True):
        st.session_state.metadata_edit_mode = True
        st.session_state.metadata_selected_table = None
        st.rerun()
    
    # Refresh metadata
    if st.button('🔄 Refresh Metadata', use_container_width=True):
        st.session_state.metadata_tables = load_metadata()
        st.success('Metadata refreshed!')
        st.rerun()
    
    # Export metadata
    if st.button('📥 Export Metadata', use_container_width=True):
        if st.session_state.metadata_tables:
            # Flatten for export
            export_data = []
            for table in st.session_state.metadata_tables:
                columns = get_columns_list(table)
                export_data.append({
                    'table_name': table.get('name', ''),
                    'description': table.get('description', ''),
                    'columns': ', '.join(columns),
                    'primary_key': table.get('primary_key', ''),
                    'foreign_keys': ', '.join(table.get('foreign_keys', []))
                })
            df = pd.DataFrame(export_data)
            csv = df.to_csv(index=False)
            st.download_button(
                label='Download CSV',
                data=csv,
                file_name=f'metadata_export_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
                key='export_metadata_download'
            )
        else:
            st.warning('No metadata to export')
    
    # Import metadata
    uploaded_file = st.file_uploader("📤 Import Metadata (CSV)", type=['csv'])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            import_tables = df.to_dict('records')
            # Convert back to proper format
            for table in import_tables:
                if 'columns' in table and isinstance(table['columns'], str):
                    table['columns'] = [c.strip() for c in table['columns'].split(',') if c.strip()]
                if 'foreign_keys' in table and isinstance(table['foreign_keys'], str):
                    table['foreign_keys'] = [c.strip() for c in table['foreign_keys'].split(',') if c.strip()]
            
            if st.button('Confirm Import'):
                if save_metadata(import_tables):
                    st.session_state.metadata_tables = import_tables
                    st.success('Metadata imported successfully!')
                    st.rerun()
                else:
                    st.error('Failed to import metadata')
        except Exception as e:
            st.error(f'Error reading CSV: {e}')

st.divider()

# ---------------------------------------------------------------------
# Search and Filter
# ---------------------------------------------------------------------
col_search, col_filter = st.columns([3, 1])

with col_search:
    search_term = st.text_input(
        '🔍 Search Tables',
        placeholder='Search by table name or description...',
        value=st.session_state.metadata_search,
        key='metadata_search_input'
    )
    st.session_state.metadata_search = search_term

with col_filter:
    # Get all column names safely - handle both string and dict formats
    all_columns = []
    for table in st.session_state.metadata_tables:
        columns = get_columns_list(table)
        all_columns.extend(columns)
    
    # Remove duplicates and sort
    unique_columns = sorted(set(all_columns)) if all_columns else []
    
    if unique_columns:
        selected_column = st.selectbox(
            '📋 Filter by Column',
            ['All Columns'] + unique_columns,
            key='metadata_column_filter'
        )
    else:
        selected_column = 'All Columns'

st.divider()

# ---------------------------------------------------------------------
# Display Statistics
# ---------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric('Total Tables', len(st.session_state.metadata_tables))

with col2:
    total_columns = 0
    for table in st.session_state.metadata_tables:
        columns = get_columns_list(table)
        total_columns += len(columns)
    st.metric('Total Columns', total_columns)

with col3:
    tables_with_pk = sum(1 for t in st.session_state.metadata_tables if t.get('primary_key'))
    st.metric('Tables with PK', tables_with_pk)

with col4:
    tables_with_fk = sum(1 for t in st.session_state.metadata_tables if t.get('foreign_keys'))
    st.metric('Tables with FK', tables_with_fk)

st.divider()

# ---------------------------------------------------------------------
# Edit/Create Table Form
# ---------------------------------------------------------------------
if st.session_state.metadata_edit_mode:
    st.subheader('✏️ ' + ('Edit Table' if st.session_state.metadata_selected_table else 'Add New Table'))
    
    with st.form('metadata_table_form', clear_on_submit=False):
        is_edit = st.session_state.metadata_selected_table is not None
        selected = st.session_state.metadata_selected_table or {}
        
        # Form fields
        table_name = st.text_input(
            'Table Name *',
            value=selected.get('name', '') if is_edit else '',
            placeholder='e.g., sales, customers, orders'
        )
        
        table_description = st.text_area(
            'Description',
            value=selected.get('description', '') if is_edit else '',
            placeholder='Enter a description of the table...',
            height=80
        )
        
        # Columns management
        st.subheader('📋 Columns')
        # Get existing columns as strings
        existing_columns = get_columns_list(selected) if is_edit else []
        columns_str = st.text_area(
            'Column Names (comma-separated)',
            value=', '.join(existing_columns) if existing_columns else '',
            placeholder='e.g., id, name, created_at, updated_at'
        )
        columns = [c.strip() for c in columns_str.split(',') if c.strip()]
        
        # Primary Key
        pk_options = ['None'] + columns if columns else ['None']
        current_pk = selected.get('primary_key', 'None') if is_edit else 'None'
        pk_index = pk_options.index(current_pk) if current_pk in pk_options else 0
        
        primary_key = st.selectbox(
            'Primary Key',
            options=pk_options,
            index=pk_index,
            key='pk_select'
        )
        primary_key = None if primary_key == 'None' else primary_key
        
        # Foreign Keys
        foreign_keys_str = st.text_input(
            'Foreign Keys (comma-separated)',
            value=', '.join(selected.get('foreign_keys', [])) if is_edit else '',
            placeholder='e.g., customer_id, product_id'
        )
        foreign_keys = [c.strip() for c in foreign_keys_str.split(',') if c.strip() and c.strip() != 'None']
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            submitted = st.form_submit_button('💾 Save Table', use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button('❌ Cancel', use_container_width=True):
                st.session_state.metadata_edit_mode = False
                st.session_state.metadata_selected_table = None
                st.rerun()
        
        if submitted:
            if not table_name.strip():
                st.error('Table Name is required.')
            elif not columns:
                st.error('At least one column is required.')
            else:
                # Check for duplicate table name (when creating new)
                if not is_edit:
                    duplicates = [t for t in st.session_state.metadata_tables 
                                 if t.get('name', '').lower() == table_name.strip().lower()]
                    if duplicates:
                        st.error(f"Table '{table_name}' already exists!")
                    else:
                        # Create new table
                        new_table = {
                            'name': table_name.strip(),
                            'description': table_description.strip(),
                            'columns': columns,
                            'primary_key': primary_key,
                            'foreign_keys': foreign_keys
                        }
                        st.session_state.metadata_tables.append(new_table)
                        
                        if save_metadata(st.session_state.metadata_tables):
                            log_event(
                                st.session_state.get('user', 'system'),
                                f'Added new metadata table: {table_name}'
                            )
                            st.success(f"✅ Table '{table_name}' added successfully!")
                            st.session_state.metadata_edit_mode = False
                            st.rerun()
                        else:
                            st.error('Failed to save metadata')
                else:
                    # Update existing table
                    for idx, table in enumerate(st.session_state.metadata_tables):
                        if table.get('name') == selected.get('name'):
                            st.session_state.metadata_tables[idx] = {
                                'name': table_name.strip(),
                                'description': table_description.strip(),
                                'columns': columns,
                                'primary_key': primary_key,
                                'foreign_keys': foreign_keys
                            }
                            break
                    
                    if save_metadata(st.session_state.metadata_tables):
                        log_event(
                            st.session_state.get('user', 'system'),
                            f'Updated metadata table: {table_name}'
                        )
                        st.success(f"✅ Table '{table_name}' updated successfully!")
                        st.session_state.metadata_edit_mode = False
                        st.session_state.metadata_selected_table = None
                        st.rerun()
                    else:
                        st.error('Failed to save metadata')
    
    st.divider()

# ---------------------------------------------------------------------
# Display Tables
# ---------------------------------------------------------------------

# Apply search and filter
filtered_tables = st.session_state.metadata_tables

if st.session_state.metadata_search:
    search_lower = st.session_state.metadata_search.lower()
    filtered_tables = [
        t for t in filtered_tables
        if search_lower in t.get('name', '').lower()
        or search_lower in t.get('description', '').lower()
        or any(search_lower in col_name.lower() for col_name in get_columns_list(t))
    ]

if selected_column != 'All Columns':
    filtered_tables = [
        t for t in filtered_tables
        if has_column(t, selected_column)
    ]

if not filtered_tables:
    st.info('No tables found matching your criteria.')
else:
    # Display tables in cards
    for idx, table in enumerate(filtered_tables):
        with st.expander(f"📊 **{table.get('name', 'Unknown')}**", expanded=False):
            col_info, col_actions = st.columns([3, 1])
            
            with col_info:
                if table.get('description'):
                    st.markdown(f"**Description:** {table.get('description')}")
                
                # Columns
                columns = get_columns_list(table)
                st.markdown(f"**Columns ({len(columns)}):**")
                for col in columns:
                    pk_marker = ' 🔑' if col == table.get('primary_key') else ''
                    fk_marker = ' 🔗' if col in table.get('foreign_keys', []) else ''
                    st.markdown(f"- `{col}`{pk_marker}{fk_marker}")
                
                # Primary Key
                if table.get('primary_key'):
                    st.markdown(f"**Primary Key:** `{table.get('primary_key')}`")
                
                # Foreign Keys
                if table.get('foreign_keys'):
                    fks = ', '.join([f'`{fk}`' for fk in table.get('foreign_keys', [])])
                    st.markdown(f"**Foreign Keys:** {fks}")
            
            with col_actions:
                # Edit button
                if st.button('✏️ Edit', key=f"edit_table_{idx}"):
                    st.session_state.metadata_edit_mode = True
                    st.session_state.metadata_selected_table = table
                    st.rerun()
                
                # Delete button with confirmation
                if st.button('🗑️ Delete', key=f"delete_table_{idx}"):
                    table_name = table.get('name')
                    st.session_state.metadata_tables = [
                        t for t in st.session_state.metadata_tables
                        if t.get('name') != table_name
                    ]
                    
                    if save_metadata(st.session_state.metadata_tables):
                        log_event(
                            st.session_state.get('user', 'system'),
                            f'Deleted metadata table: {table_name}'
                        )
                        st.success(f"✅ Table '{table_name}' deleted successfully!")
                        st.rerun()
                    else:
                        st.error('Failed to delete table')

# ---------------------------------------------------------------------
# Semantic Context Preview
# ---------------------------------------------------------------------
st.divider()
with st.expander("📝 Semantic Context Preview", expanded=False):
    if METADATA_AVAILABLE:
        try:
            # Build context from selected tables
            if st.session_state.metadata_tables:
                # Create a simple context
                context_lines = []
                for table in st.session_state.metadata_tables[:3]:  # Limit to first 3
                    context_lines.append(f"\nTable: {table.get('name')}")
                    context_lines.append(f"Description: {table.get('description', 'No description')}")
                    columns = get_columns_list(table)
                    context_lines.append(f"Columns: {', '.join(columns)}")
                    if table.get('primary_key'):
                        context_lines.append(f"Primary Key: {table.get('primary_key')}")
                    if table.get('foreign_keys'):
                        context_lines.append(f"Foreign Keys: {', '.join(table.get('foreign_keys', []))}")
                    context_lines.append("-" * 40)
                
                context_text = "\n".join(context_lines)
                
                st.text_area(
                    "Semantic Context",
                    value=context_text,
                    height=300,
                    disabled=True,
                    key="semantic_context_display"
                )
            else:
                st.info('No metadata available for context preview')
        except Exception as e:
            st.error(f"Error generating context: {e}")
    else:
        st.warning("Metadata module not available")

# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------
st.divider()
st.caption(f"📊 Metadata Management - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")