from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

import yaml

from metadata.glossary import load_glossary_yaml


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]

RAW_METADATA_DIR = ROOT_DIR / 'metadata' / 'raw'
CURATED_METADATA_DIR = ROOT_DIR / 'metadata' / 'curated'
CONTEXT_CACHE_DIR = ROOT_DIR / 'metadata' / 'context_cache'

# Create directories if they don't exist
RAW_METADATA_DIR.mkdir(parents=True, exist_ok=True)
CURATED_METADATA_DIR.mkdir(parents=True, exist_ok=True)
CONTEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Import database for context caching
# ---------------------------------------------------------------------
try:
    from streamlit_app.db import SessionLocal
    from sqlalchemy import text
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


# ---------------------------------------------------------------------
# Generic loaders
# ---------------------------------------------------------------------
def _load_json(path: Path, default: Any):
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _load_yaml(path: Path, default: Any):
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception:
            return default
    return default


# ---------------------------------------------------------------------
# Business glossary
# ---------------------------------------------------------------------
def get_business_glossary() -> List[Dict]:
    """Get business glossary terms."""
    try:
        data = load_glossary_yaml()
        if data:
            return data.get('terms', [])
        return []
    except Exception:
        return []


# ---------------------------------------------------------------------
# Certified Measures
# ---------------------------------------------------------------------
def load_certified_measures_from_file() -> List[Dict]:
    """
    Load certified measures from certified_measures.yaml file.
    
    Returns:
        List of certified measure definitions
    """
    path = ROOT_DIR / 'metadata' / 'certified_measures.yaml'
    data = _load_yaml(path, {})
    
    # Handle different formats
    if 'certified_measures' in data:
        return data.get('certified_measures', [])
    if 'measures' in data:
        return data.get('measures', [])
    
    # Return default certified measures if file not found
    return get_default_certified_measures()


def get_default_certified_measures() -> List[Dict]:
    """Return default certified measures."""
    return [
        {
            'name': 'Net Revenue',
            'business_name': 'Net Revenue',
            'description': 'Total net sales amount after discounts, returns, and allowances',
            'table': 'sales',
            'field': 'net_revenue',
            'dax': 'SUM(Sales[NetAmount])',
            'certified': True,
            'certification_date': '2026-07-01',
            'certified_by': 'Data Governance Team',
            'owner': 'Retail Analytics',
            'mandatory_filters': ['Date', 'Organization']
        },
        {
            'name': 'Gross Margin %',
            'business_name': 'Gross Margin Percentage',
            'description': 'Gross profit percentage over net revenue',
            'table': 'sales',
            'field': 'gross_margin_percent',
            'dax': 'DIVIDE([Gross Margin Amount], [Net Revenue], 0)',
            'certified': True,
            'certification_date': '2026-07-01',
            'certified_by': 'Data Governance Team',
            'owner': 'Retail Analytics',
            'mandatory_filters': ['Date', 'Organization']
        },
        {
            'name': 'Average Unit Price',
            'business_name': 'Average Unit Price',
            'description': 'Average selling price per unit sold',
            'table': 'sales',
            'field': 'avg_unit_price',
            'dax': 'DIVIDE([Net Revenue], [Units Sold], 0)',
            'certified': True,
            'certification_date': '2026-07-01',
            'certified_by': 'Data Governance Team',
            'owner': 'Retail Analytics',
            'mandatory_filters': ['Date', 'Organization']
        },
        {
            'name': 'Inventory Value',
            'business_name': 'Inventory Value',
            'description': 'Total monetary value of inventory on hand',
            'table': 'product',
            'field': 'inventory_value',
            'dax': 'SUM(Product[InventoryValue])',
            'certified': True,
            'certification_date': '2026-07-01',
            'certified_by': 'Data Governance Team',
            'owner': 'Supply Chain Analytics',
            'mandatory_filters': ['Date', 'Organization', 'Warehouse']
        },
        {
            'name': 'Return Rate',
            'business_name': 'Return Rate',
            'description': 'Percentage of sold units returned by customers',
            'table': 'sales',
            'field': 'return_rate',
            'dax': 'DIVIDE([Returned Units], [Units Sold], 0)',
            'certified': True,
            'certification_date': '2026-07-01',
            'certified_by': 'Data Governance Team',
            'owner': 'Retail Analytics',
            'mandatory_filters': ['Date', 'Organization']
        }
    ]


# ---------------------------------------------------------------------
# Curated metadata
# ---------------------------------------------------------------------
def load_curated_tables() -> List[Dict]:
    path = CURATED_METADATA_DIR / 'tables.yaml'
    data = _load_yaml(path, {})
    if 'tables' in data:
        return data.get('tables', [])
    return []


def load_curated_measures() -> List[Dict]:
    path = CURATED_METADATA_DIR / 'measures.yaml'
    data = _load_yaml(path, {})
    
    # If measures file exists, use it
    if 'measures' in data:
        return data.get('measures', [])
    
    # Otherwise, use certified measures from certified_measures.yaml
    certified = load_certified_measures_from_file()
    if certified:
        return certified
    
    # Fallback to default
    return get_default_certified_measures()


def load_curated_relationships() -> List[Dict]:
    path = CURATED_METADATA_DIR / 'relationships.yaml'
    data = _load_yaml(path, {})
    if 'relationships' in data:
        return data.get('relationships', [])
    return []


def load_semantic_model_info() -> Dict:
    path = CURATED_METADATA_DIR / 'semantic_model.json'
    return _load_json(path, {})


# ---------------------------------------------------------------------
# Raw metadata fallback
# ---------------------------------------------------------------------
def load_raw_tables() -> List[Dict]:
    path = RAW_METADATA_DIR / 'tables.json'
    return _load_json(path, [])


def load_raw_relationships() -> List[Dict]:
    path = RAW_METADATA_DIR / 'relationships.json'
    return _load_json(path, [])


# ---------------------------------------------------------------------
# Public loaders with curated-first strategy
# ---------------------------------------------------------------------
def load_tables() -> List[Dict]:
    curated = load_curated_tables()
    if curated:
        return curated
    return load_raw_tables()


def load_relationships() -> List[Dict]:
    curated = load_curated_relationships()
    if curated:
        return curated
    return load_raw_relationships()


def load_measures() -> List[Dict]:
    measures = load_curated_measures()
    if measures:
        return measures
    return get_default_certified_measures()


# ---------------------------------------------------------------------
# Certified measures
# ---------------------------------------------------------------------
def get_certified_measures() -> List[str]:
    measures = load_measures()
    return [
        m['name']
        for m in measures
        if m.get('certified', True)
    ]


def is_measure_certified(measure_name: str) -> bool:
    """Check if a measure is certified."""
    certified = get_certified_measures()
    return measure_name in certified


def get_measure_by_name(name: str) -> Optional[Dict]:
    """Get a measure by its name."""
    measures = load_measures()
    for measure in measures:
        if measure.get('name') == name:
            return measure
    return None


# ---------------------------------------------------------------------
# Table lookup
# ---------------------------------------------------------------------
def get_table(name: str) -> Optional[Dict]:
    for table in load_tables():
        if table.get('name') == name:
            return table
    return None


# ---------------------------------------------------------------------
# Measure lookup
# ---------------------------------------------------------------------
def get_measure(name: str) -> Optional[Dict]:
    for measure in load_measures():
        if measure.get('name') == name:
            return measure
    return None


# ---------------------------------------------------------------------
# Context Memory Manager for Metadata
# ---------------------------------------------------------------------
class MetadataContextManager:
    """
    Manages metadata context with caching and memory.
    Tracks frequently accessed metadata and provides smart context building.
    """
    
    def __init__(self):
        self.cache = {}
        self.access_history = []
        self.max_cache_size = 100
        self.cache_dir = CONTEXT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cached_context(self, context_key: str) -> Optional[Dict]:
        """Get cached context by key."""
        cache_file = self.cache_dir / f"{context_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def save_cached_context(self, context_key: str, context_data: Dict) -> None:
        """Save context to cache."""
        cache_file = self.cache_dir / f"{context_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def track_access(self, entity_type: str, entity_name: str) -> None:
        """Track access to metadata entities."""
        self.access_history.append({
            'type': entity_type,
            'name': entity_name,
            'timestamp': datetime.now().isoformat()
        })
        # Keep only last 1000 accesses
        if len(self.access_history) > 1000:
            self.access_history = self.access_history[-1000:]
    
    def get_frequently_accessed(self, limit: int = 10) -> Dict[str, List[str]]:
        """Get frequently accessed metadata entities."""
        from collections import Counter
        
        types_counter = Counter()
        names_counter = Counter()
        
        for access in self.access_history:
            types_counter[access['type']] += 1
            names_counter[f"{access['type']}::{access['name']}"] += 1
        
        result = {}
        for entity_type, count in types_counter.most_common(limit):
            result[entity_type] = []
        
        for key, count in names_counter.most_common(limit):
            if '::' in key:
                etype, ename = key.split('::', 1)
                if etype in result:
                    result[etype].append(ename)
        
        return result
    
    def get_context_summary(self) -> str:
        """Generate a summary of context usage."""
        summary = []
        summary.append("## Metadata Context Summary")
        summary.append("")
        
        frequently_accessed = self.get_frequently_accessed()
        
        if frequently_accessed:
            summary.append("### Frequently Accessed Entities:")
            for entity_type, names in frequently_accessed.items():
                summary.append(f"- {entity_type}: {', '.join(names[:5])}")
                if len(names) > 5:
                    summary.append(f"  ... and {len(names) - 5} more")
        else:
            summary.append("No access history available.")
        
        summary.append("")
        summary.append(f"Cache Size: {len(self.cache)}")
        summary.append(f"Access History Size: {len(self.access_history)}")
        
        return "\n".join(summary)
    
    def clear_cache(self) -> None:
        """Clear the context cache."""
        self.cache = {}
        self.access_history = []
        if self.cache_dir.exists():
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Enhanced Semantic Context Builder
# ---------------------------------------------------------------------
class EnhancedContextBuilder:
    """
    Builds enhanced semantic contexts with memory and caching.
    """
    
    def __init__(self):
        self.context_manager = MetadataContextManager()
    
    def build_semantic_context(
        self,
        query: Optional[str] = None,
        include_glossary: bool = True,
        include_frequent: bool = True,
        include_history: bool = True,
        cache_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Builds an enhanced semantic context with memory.
        
        Args:
            query: Query or user question
            include_glossary: Whether to include glossary
            include_frequent: Whether to include frequently accessed entities
            include_history: Whether to include access history
            cache_key: Cache key for retrieving cached context
        
        Returns:
            Dict with enhanced semantic context
        """
        # Check cache first
        if cache_key:
            cached = self.context_manager.get_cached_context(cache_key)
            if cached:
                return cached
        
        # Build base context
        model_info = load_semantic_model_info()
        tables = load_tables()
        measures = load_measures()
        relationships = load_relationships()
        glossary_terms = get_business_glossary()
        
        # Track access
        for table in tables:
            self.context_manager.track_access('table', table.get('name', 'unknown'))
        for measure in measures:
            self.context_manager.track_access('measure', measure.get('name', 'unknown'))
        
        # Build context
        context = {
            "model": model_info,
            "tables": tables,
            "measures": measures,
            "relationships": relationships,
            "glossary": glossary_terms if include_glossary else [],
            "query": query or "",
            "context_id": datetime.now().isoformat(),
            "metadata": {
                "total_tables": len(tables),
                "total_measures": len(measures),
                "total_relationships": len(relationships),
                "total_glossary_terms": len(glossary_terms),
                "certified_measures": len(get_certified_measures()),
                "generated_at": datetime.now().isoformat()
            },
            "certified_measures_info": load_certified_measures_from_file()
        }
        
        # Add frequently accessed entities
        if include_frequent:
            frequent = self.context_manager.get_frequently_accessed()
            context["frequently_accessed"] = frequent
        
        # Add access history summary
        if include_history:
            context["access_history_summary"] = self.context_manager.get_context_summary()
        
        # Cache the context
        if cache_key:
            self.context_manager.save_cached_context(cache_key, context)
        
        return context
    
    def build_semantic_context_string(
        self,
        query: Optional[str] = None,
        include_frequent: bool = True,
        include_history: bool = True
    ) -> str:
        """
        Builds a string representation of the enhanced semantic context.
        
        Returns:
            String with enhanced semantic context
        """
        context = self.build_semantic_context(
            query=query,
            include_frequent=include_frequent,
            include_history=include_history
        )
        
        lines: List[str] = []
        
        # Model info
        model = context.get('model', {})
        lines.append('# Approved Semantic Model')
        lines.append(f"Model: {model.get('model_name', 'Unknown')}")
        lines.append(f"Version: {model.get('version', 'Unknown')}")
        lines.append(f"Environment: {model.get('environment', 'Unknown')}")
        lines.append("")
        
        # Metadata
        metadata = context.get('metadata', {})
        lines.append("## Model Statistics")
        lines.append(f"- Total Tables: {metadata.get('total_tables', 0)}")
        lines.append(f"- Total Measures: {metadata.get('total_measures', 0)}")
        lines.append(f"- Certified Measures: {metadata.get('certified_measures', 0)}")
        lines.append(f"- Total Relationships: {metadata.get('total_relationships', 0)}")
        lines.append("")
        
        # Certified Measures
        certified_info = context.get('certified_measures_info', [])
        if certified_info:
            lines.append("## Certified Measures")
            for measure in certified_info:
                lines.append(f"- {measure.get('name', 'Unknown')}")
                if measure.get('description'):
                    lines.append(f"  Description: {measure.get('description')}")
                if measure.get('mandatory_filters'):
                    filters = ', '.join(measure.get('mandatory_filters', []))
                    lines.append(f"  Mandatory Filters: {filters}")
                lines.append("")
        
        # Tables
        tables = context.get('tables', [])
        if tables:
            lines.append("## Tables")
            for table in tables[:10]:  # Limit to first 10 for brevity
                lines.append(f"- {table.get('business_name', table.get('name'))}")
                description = table.get('description')
                if description:
                    lines.append(f"  Description: {description}")
                certified = table.get('certified', False)
                lines.append(f"  Certified: {certified}")
                lines.append("")
            if len(tables) > 10:
                lines.append(f"... and {len(tables) - 10} more tables")
                lines.append("")
        
        # Frequently accessed
        frequent = context.get('frequently_accessed', {})
        if frequent:
            lines.append("## Frequently Accessed")
            for entity_type, names in frequent.items():
                if names:
                    lines.append(f"- {entity_type}: {', '.join(names[:5])}")
                    if len(names) > 5:
                        lines.append(f"  ... and {len(names) - 5} more")
            lines.append("")
        
        # Glossary
        glossary = context.get('glossary', [])
        if glossary:
            lines.append("## Business Glossary")
            for term in glossary[:10]:
                lines.append(f"- {term.get('business_term', 'Unknown')}: {term.get('description', '')}")
            if len(glossary) > 10:
                lines.append(f"... and {len(glossary) - 10} more terms")
            lines.append("")
        
        # Query
        if query:
            lines.append("## Current Query")
            lines.append(f"{query}")
            lines.append("")
        
        # User question prompt
        lines.append("## Instructions")
        lines.append("Answer based ONLY on the semantic model information provided above.")
        lines.append("If information is not available, respond: 'The requested information is not available in the approved semantic model.'")
        lines.append("Always apply mandatory filters when using certified measures.")
        
        return "\n".join(lines)
    
    def build_context_for_query(
        self,
        query: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a context specifically for a user query.
        
        Args:
            query: User query
            user_id: User ID for personalized context
        
        Returns:
            Dict with query-specific context
        """
        context = self.build_semantic_context(
            query=query,
            include_glossary=True,
            include_frequent=True,
            include_history=True
        )
        
        # Add user-specific context if user_id provided
        if user_id:
            cache_key = f"user_{user_id}_context"
            user_context = self.context_manager.get_cached_context(cache_key)
            if user_context:
                context["user_context"] = user_context
        
        return context


# ---------------------------------------------------------------------
# Semantic context builder (compatibility)
# ---------------------------------------------------------------------
_builder = EnhancedContextBuilder()


def build_semantic_context(
    query: str = None,
    include_glossary: bool = True,
    include_frequent: bool = True,
    include_history: bool = True
) -> Dict[str, Any]:
    """
    Builds the semantic context for a query with memory.
    
    Args:
        query: Query or user question
        include_glossary: Whether to include glossary in context
        include_frequent: Whether to include frequently accessed entities
        include_history: Whether to include access history
    
    Returns:
        Dict with semantic context
    """
    return _builder.build_semantic_context(
        query=query,
        include_glossary=include_glossary,
        include_frequent=include_frequent,
        include_history=include_history
    )


def build_semantic_context_string(
    query: str = None,
    include_frequent: bool = True,
    include_history: bool = True
) -> str:
    """
    Builds a string representation of the semantic context with memory.
    
    Returns:
        String with semantic context
    """
    return _builder.build_semantic_context_string(
        query=query,
        include_frequent=include_frequent,
        include_history=include_history
    )


# ---------------------------------------------------------------------
# Table metadata (compatibility)
# ---------------------------------------------------------------------
def get_table_metadata(table_name: str) -> Optional[Dict[str, Any]]:
    """
    Gets metadata for a specific table.
    
    Args:
        table_name: Name of the table
    
    Returns:
        Dict with table metadata or None if not found
    """
    # Track access
    _builder.context_manager.track_access('table', table_name)
    
    # Check curated tables first
    for table in load_curated_tables():
        if table.get('name') == table_name or table.get('business_name') == table_name:
            return {
                'name': table.get('name'),
                'business_name': table.get('business_name', table.get('name')),
                'description': table.get('description', ''),
                'columns': table.get('columns', []),
                'primary_key': table.get('primary_key', ''),
                'foreign_keys': table.get('foreign_keys', []),
                'owner': table.get('owner', ''),
                'certified': table.get('certified', False),
                'source': 'curated'
            }
    
    # Check raw tables
    for table in load_raw_tables():
        if table.get('name') == table_name:
            return {
                'name': table.get('name'),
                'business_name': table.get('business_name', table.get('name')),
                'description': table.get('description', ''),
                'columns': table.get('columns', []),
                'primary_key': table.get('primary_key', ''),
                'foreign_keys': table.get('foreign_keys', []),
                'source': 'raw'
            }
    
    # Return default metadata if not found
    return get_default_table_metadata(table_name)


# ---------------------------------------------------------------------
# Default table metadata
# ---------------------------------------------------------------------
def get_default_table_metadata(table_name: str) -> Optional[Dict[str, Any]]:
    """Return default metadata for common tables."""
    default_tables = {
        'financials': {
            'name': 'financials',
            'business_name': 'Financials',
            'description': 'Financial data including revenue, margins, and costs',
            'columns': ['date', 'net_revenue', 'gross_margin', 'cost_of_goods', 'operating_expenses'],
            'primary_key': 'date',
            'foreign_keys': []
        },
        'sales': {
            'name': 'sales',
            'business_name': 'Sales',
            'description': 'Sales transaction data including products and customers',
            'columns': ['date', 'product_id', 'customer_id', 'sales_total', 'quantity', 'unit_price'],
            'primary_key': 'sale_id',
            'foreign_keys': ['product_id', 'customer_id']
        },
        'orders': {
            'name': 'orders',
            'business_name': 'Orders',
            'description': 'Order data including status and amounts',
            'columns': ['order_id', 'order_date', 'customer_id', 'status', 'total_amount', 'shipping_cost'],
            'primary_key': 'order_id',
            'foreign_keys': ['customer_id']
        },
        'customers': {
            'name': 'customers',
            'business_name': 'Customers',
            'description': 'Customer master data including demographics',
            'columns': ['customer_id', 'name', 'email', 'phone', 'region', 'created_at', 'active'],
            'primary_key': 'customer_id',
            'foreign_keys': []
        },
        'products': {
            'name': 'products',
            'business_name': 'Products',
            'description': 'Product master data including category and pricing',
            'columns': ['product_id', 'name', 'category', 'subcategory', 'unit_price', 'cost', 'supplier_id'],
            'primary_key': 'product_id',
            'foreign_keys': ['supplier_id']
        },
        'inventory': {
            'name': 'inventory',
            'business_name': 'Inventory',
            'description': 'Inventory data including stock levels and warehouse information',
            'columns': ['product_id', 'warehouse', 'inventory_value', 'stock_quantity', 'reorder_level', 'last_updated'],
            'primary_key': 'inventory_id',
            'foreign_keys': ['product_id']
        }
    }
    
    return default_tables.get(table_name)


# ---------------------------------------------------------------------
# All tables (compatibility)
# ---------------------------------------------------------------------
def get_all_tables() -> List[Dict[str, Any]]:
    """
    Gets all available tables with their metadata.
    
    Returns:
        List of table metadata dictionaries
    """
    tables = []
    
    # Get curated tables
    curated_tables = load_curated_tables()
    for table in curated_tables:
        # Track access
        _builder.context_manager.track_access('table', table.get('name', 'unknown'))
        tables.append({
            'name': table.get('name'),
            'business_name': table.get('business_name', table.get('name')),
            'description': table.get('description', ''),
            'columns': table.get('columns', []),
            'primary_key': table.get('primary_key', ''),
            'foreign_keys': table.get('foreign_keys', []),
            'owner': table.get('owner', ''),
            'certified': table.get('certified', False),
            'source': 'curated'
        })
    
    # Get raw tables if no curated tables exist
    if not tables:
        raw_tables = load_raw_tables()
        for table in raw_tables:
            tables.append({
                'name': table.get('name'),
                'business_name': table.get('business_name', table.get('name')),
                'description': table.get('description', ''),
                'columns': table.get('columns', []),
                'primary_key': table.get('primary_key', ''),
                'foreign_keys': table.get('foreign_keys', []),
                'source': 'raw'
            })
    
    # If still no tables, return default tables
    if not tables:
        default_names = ['financials', 'sales', 'orders', 'customers', 'products', 'inventory']
        for name in default_names:
            table = get_default_table_metadata(name)
            if table:
                tables.append(table)
    
    return tables


# ---------------------------------------------------------------------
# Metadata summary API (enhanced)
# ---------------------------------------------------------------------
def get_metadata_summary(include_context: bool = False) -> Dict:
    """
    Get metadata summary with optional context information.
    
    Args:
        include_context: Whether to include context usage information
    
    Returns:
        Dict with metadata summary
    """
    tables = load_tables()
    measures = load_measures()
    relationships = load_relationships()
    glossary_terms = get_business_glossary()
    certified_measures = load_certified_measures_from_file()
    
    summary = {
        'tables_count': len(tables),
        'measures_count': len(measures),
        'relationships_count': len(relationships),
        'glossary_terms_count': len(glossary_terms),
        'certified_measures_count': len(certified_measures),
        'tables': [t.get('name') for t in tables],
        'certified_measures': [m.get('name') for m in certified_measures],
        'generated_at': datetime.now().isoformat()
    }
    
    if include_context:
        summary['context_usage'] = {
            'frequently_accessed': _builder.context_manager.get_frequently_accessed(),
            'access_history_count': len(_builder.context_manager.access_history),
            'cache_size': len(_builder.context_manager.cache)
        }
    
    return summary


# ---------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------
def validate_metadata() -> Dict:
    """Validate metadata integrity."""
    errors: List[str] = []
    warnings: List[str] = []

    tables = load_tables()
    measures = load_measures()
    certified_measures = load_certified_measures_from_file()

    table_names = {t.get('name') for t in tables}
    measure_names = {m.get('name') for m in measures}

    # Check measure references
    for measure in measures:
        table_name = measure.get('table')
        if table_name and table_name not in table_names:
            errors.append(
                f"Measure '{measure.get('name')}' references missing table '{table_name}'."
            )
    
    # Check certified measures
    for cert_measure in certified_measures:
        if cert_measure.get('name') not in measure_names:
            warnings.append(
                f"Certified measure '{cert_measure.get('name')}' not found in measures."
            )
    
    # Check mandatory filters
    for measure in measures:
        if measure.get('mandatory_filters'):
            filters = measure.get('mandatory_filters', [])
            if not filters:
                warnings.append(
                    f"Measure '{measure.get('name')}' has empty mandatory_filters."
                )

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


# ---------------------------------------------------------------------
# Context management functions
# ---------------------------------------------------------------------
def clear_context_cache() -> None:
    """Clear the context cache."""
    if CONTEXT_CACHE_DIR.exists():
        import shutil
        shutil.rmtree(CONTEXT_CACHE_DIR)
    CONTEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_context_summary() -> str:
    """Get a summary of the metadata context usage."""
    return _builder.context_manager.get_context_summary()


# ---------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    print('=' * 80)
    print('METADATA SERVICE WITH CONTEXT MEMORY')
    print('=' * 80)
    
    print('\n📊 METADATA SUMMARY:')
    print(json.dumps(get_metadata_summary(include_context=True), indent=2, ensure_ascii=False))
    
    print('\n' + '=' * 80)
    print('VALIDATION:')
    print('=' * 80)
    
    validation = validate_metadata()
    if validation['valid']:
        print('✅ Metadata validation passed.')
    else:
        print('❌ Metadata validation failed:')
        for err in validation['errors']:
            print('-', err)
    
    if validation.get('warnings'):
        print('\n⚠️ Warnings:')
        for warn in validation['warnings']:
            print('-', warn)
    
    print('\n' + '=' * 80)
    print('ENHANCED SEMANTIC CONTEXT PREVIEW:')
    print('=' * 80)
    
    context_string = build_semantic_context_string(
        query='What was net revenue in Q2 2026?',
        include_frequent=True,
        include_history=True
    )
    print(context_string[:2000])
    print('...')
    
    print('\n' + '=' * 80)
    print('CONTEXT SUMMARY:')
    print('=' * 80)
    print(get_context_summary())