"""Builds an in-memory, searchable index of the semantic model (all tables
parsed from the `definition/tables/*.tmdl` folder) so the calling LLM can
ground natural-language questions in real table/column/measure names
before writing DAX — this is the piece that makes "ask a question in
plain English" actually work reliably instead of hallucinating field
names.

This version also includes a SemanticRouter that uses the index to
return actual tables/measures for a given business domain.

All non‑English keywords have been removed; the router now uses only
English keywords. Queries in other languages will fall back to the LLM
for classification (handled in query_service.py).
"""

from __future__ import annotations

import re
import json
import os
import sys
import glob
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any
from datetime import datetime

# ---------------------------------------------------------------------
# TMDL parser – try absolute import; fall back to dummy if missing
# ---------------------------------------------------------------------
PARSER_AVAILABLE = False
try:
    from tmdl.parser import parse_tmdl_file
    from tmdl.models import Table
    PARSER_AVAILABLE = True
    print("[INFO] TMDL parser imported successfully (absolute import)", file=sys.stderr)
except ImportError:
    # Fallback: try relative import (just in case)
    try:
        from ..tmdl.parser import parse_tmdl_file
        from ..tmdl.models import Table
        PARSER_AVAILABLE = True
        print("[INFO] TMDL parser imported successfully (relative import)", file=sys.stderr)
    except ImportError:
        PARSER_AVAILABLE = False
        print("[WARNING] TMDL parser not available – falling back to dummy parser", file=sys.stderr)
        # Define dummy classes for fallback
        class Table:
            def __init__(self, name, description="", columns=None, measures=None, is_hidden=False):
                self.name = name
                self.description = description
                self.columns = columns or []
                self.measures = measures or []
                self.is_hidden = is_hidden

        def parse_tmdl_file(path):
            return None

# ---------------------------------------------------------------------
# Domain keyword definitions – now only English keywords.
# All non‑English translations have been removed.
# ---------------------------------------------------------------------
SEMANTIC_DOMAINS = {
    'sales': {
        'keywords': [
            'revenue', 'sales', 'turnover', 'net revenue', 'invoice',
            'sell', 'sold', 'net sales', 'average unit price', 'unit price',
            'average price', 'avg price', 'revenue for', 'sales by',
            'sales amount', 'net sales amount'
        ],
    },
    'profitability': {
        'keywords': [
            'gross margin', 'margin', 'profitability', 'margin percentage',
            'gross profit', 'margin %', 'gross margin by', 'margin by',
            'profit', 'gross margin percentage'
        ],
    },
    'inventory': {
        'keywords': [
            'inventory', 'stock', 'warehouse', 'inventory value',
            'stock value', 'inventory quantity', 'inventory by',
            'inventory on hand', 'stock level'
        ],
    },
    'returns': {
        'keywords': [
            'return', 'returns', 'refund', 'return rate',
            'return percentage', 'return by', 'returned', 'refund rate'
        ],
    },
    'tables': {
        'keywords': [
            'tables', 'table', 'show tables', 'list tables',
            'what tables', 'available tables', 'model tables',
            'information about the tables', 'tell me about the tables',
            'which tables', 'all tables'
        ],
    },
    'customer': {
        'keywords': [
            'customer', 'active customer', 'customer tier', 'tier',
            'customer activity', 'customer month', 'active customer month',
            'hi ticket', 'ticket', 'superprova', 'super prova',
            'customer tier', 'tier code', 'tier label', 'customer retention',
            'active customers'
        ],
    },
    'manager': {
        'keywords': [
            'area manager', 'manager', 'regional', 'territory',
            'area manager code', 'area manager description',
            'sales manager', 'regional manager', 'territory manager',
            'area manager performance', 'manager sales'
        ],
    },
    'product': {
        'keywords': [
            'color', 'colour', 'collection', 'season', 'article',
            'item code', 'color code', 'color group', 'collection year',
            'collection season', 'delivery', 'composition', 'retail flag',
            'product color', 'color description', 'color group description',
            'buying logic', 'selling logic', 'marketing type', 'sponsor event',
            'colors available', 'available colors', 'category', 'gender',
            'family', 'commercial model', 'commercial family', 'sub category',
            'business code', 'stage of life', 'product hierarchy', 'categories',
            'category code', 'sub category code', 'item description',
            'family code', 'gender code', 'cites code', 'sales category',
            'category or family', 'category/family',
            'Category Code', 'Category Description ENG', 'Category Description ITA',
            'Category Group Code', 'Category Group Description',
            'category group', 'category description', 'category code',
            'product class', 'product classification', 'classe prodotto'
        ],
    },
    'business': {
        'keywords': [
            'business', 'macro business', 'macrobusiness', 'macro category',
            'business code', 'business description', 'business classification',
            'macro business group', 'business hierarchy', 'business performance',
            'sales by business', 'business by', 'macro business grp',
            'macrobusiness code', 'macrobusiness description'
        ],
    },
    'time_intelligence': {
        'keywords': [
            'year-over-year', 'yoy', 'year over year', 'previous year',
            'fiscal year', 'fiscal quarter', 'fiscal month', 'fiscal week',
            'week-over-week', 'wow', 'week over week',
            'quarter-over-quarter', 'qoq', 'quarter over quarter',
            'month-over-month', 'mom', 'month over month',
            'time intelligence', 'period comparison', 'same period',
            'prior year', 'previous period', 'sales by month',
            'sales by quarter', 'sales by week', 'monthly sales',
            'quarterly revenue', 'weekly sales', 'year to date', 'ytd',
            'quarter to date', 'qtd', 'month to date', 'mtd'
        ],
    },
    'currency': {
        'keywords': [
            'currency', 'currencies', 'currency selector', 'available currencies',
            'supported currencies', 'show currencies', 'list currencies',
            'what currencies', 'currency table', 'currency list'
        ],
    }
}

# ---------------------------------------------------------------------
# Currency configuration
# ---------------------------------------------------------------------
DEFAULT_CURRENCY_CONFIG = {
    'USD': {
        'symbol': '$',
        'code': 'USD',
        'name': 'US Dollar',
        'default': True,
        'format': '${:,.2f}',
        'exchange_rate': 1.0
    },
    'EUR': {
        'symbol': '€',
        'code': 'EUR',
        'name': 'Euro',
        'default': False,
        'format': '€{:,.2f}',
        'exchange_rate': 0.85
    },
    'GBP': {
        'symbol': '£',
        'code': 'GBP',
        'name': 'British Pound',
        'default': False,
        'format': '£{:,.2f}',
        'exchange_rate': 0.78
    },
    'CAD': {
        'symbol': 'C$',
        'code': 'CAD',
        'name': 'Canadian Dollar',
        'default': False,
        'format': 'C${:,.2f}',
        'exchange_rate': 1.35
    },
    'AUD': {
        'symbol': 'A$',
        'code': 'AUD',
        'name': 'Australian Dollar',
        'default': False,
        'format': 'A${:,.2f}',
        'exchange_rate': 1.48
    }
}

# ---------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------
@dataclass
class SchemaMatch:
    table: str
    kind: str  # "table" | "column" | "measure"
    name: str
    score: float
    detail: dict

@dataclass
class RoutingResult:
    domain: str
    tables: List[str]
    measures: List[str]
    confidence: float
    ambiguous: bool
    clarification_message: Optional[str] = None
    currency: Optional[str] = None
    currency_symbol: Optional[str] = None

@dataclass
class CurrencyContext:
    code: str
    symbol: str
    name: str
    format: str
    exchange_rate: float
    is_default: bool

# ---------------------------------------------------------------------
# SemanticIndex – reads the actual model from TMDL (or from a JSON file)
# ---------------------------------------------------------------------
class SemanticIndex:
    def __init__(self, definition_dir: str, schema_json_path: Optional[str] = None):
        self.definition_dir = definition_dir
        self.tables: List[Table] = []
        self.schema_json_path = schema_json_path
        self.refresh()

    def refresh(self) -> None:
        """Reload the index from the definition directory or JSON file."""
        # If a JSON file is provided, use it
        if self.schema_json_path and os.path.exists(self.schema_json_path):
            self.tables = self._load_from_json(self.schema_json_path)
            print(f"[INFO] Loaded {len(self.tables)} tables from JSON: {self.schema_json_path}", file=sys.stderr)
            return

        # If parser is available and the folder exists, parse each .tmdl file
        if PARSER_AVAILABLE and os.path.exists(self.definition_dir):
            tmdl_files = glob.glob(os.path.join(self.definition_dir, "*.tmdl"))
            if tmdl_files:
                tables = []
                for filepath in tmdl_files:
                    try:
                        table = parse_tmdl_file(filepath)
                        if table is not None:
                            tables.append(table)
                    except Exception as e:
                        print(f"⚠️ Failed to parse {filepath}: {e}", file=sys.stderr)
                self.tables = tables
                print(f"[INFO] Loaded {len(self.tables)} tables from {self.definition_dir}", file=sys.stderr)
            else:
                print(f"[WARNING] No .tmdl files found in {self.definition_dir}", file=sys.stderr)
                self.tables = []
        else:
            if not PARSER_AVAILABLE:
                print("[WARNING] TMDL parser not available – cannot load tables.", file=sys.stderr)
            if not os.path.exists(self.definition_dir):
                print(f"[WARNING] Definition directory does not exist: {self.definition_dir}", file=sys.stderr)
            self.tables = []

    def _load_from_json(self, json_path: str) -> List[Table]:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        tables = []
        for t_data in data.get('tables', []):
            columns = []
            for c in t_data.get('columns', []):
                col = type('Column', (), {})()
                col.name = c.get('name', '')
                col.data_type = c.get('type', 'string')
                col.description = c.get('description', '')
                col.is_hidden = c.get('is_hidden', False)
                columns.append(col)
            measures = []
            for m in t_data.get('measures', []):
                meas = type('Measure', (), {})()
                meas.name = m.get('name', '')
                meas.expression = m.get('expression', '')
                meas.description = m.get('description', '')
                meas.format_string = m.get('format_string', '')
                meas.is_hidden = m.get('is_hidden', False)
                measures.append(meas)
            table = Table(
                name=t_data.get('name', ''),
                description=t_data.get('description', ''),
                columns=columns,
                measures=measures,
                is_hidden=t_data.get('is_hidden', False)
            )
            tables.append(table)
        return tables

    def load_from_dict(self, schema_dict: dict) -> None:
        """Manually load schema from a dict (same structure as schema_summary)."""
        tables = []
        for t_data in schema_dict.get('tables', []):
            columns = []
            for c in t_data.get('columns', []):
                col = type('Column', (), {})()
                col.name = c.get('name', '')
                col.data_type = c.get('type', 'string')
                col.description = c.get('description', '')
                col.is_hidden = c.get('is_hidden', False)
                columns.append(col)
            measures = []
            for m in t_data.get('measures', []):
                meas = type('Measure', (), {})()
                meas.name = m.get('name', '')
                meas.expression = m.get('expression', '')
                meas.description = m.get('description', '')
                meas.format_string = m.get('format_string', '')
                meas.is_hidden = m.get('is_hidden', False)
                measures.append(meas)
            table = Table(
                name=t_data.get('name', ''),
                description=t_data.get('description', ''),
                columns=columns,
                measures=measures,
                is_hidden=t_data.get('is_hidden', False)
            )
            tables.append(table)
        self.tables = tables

    def get_table(self, name: str) -> Optional[Table]:
        for t in self.tables:
            if t.name.lower() == name.lower():
                return t
        return None

    def schema_summary(self, include_hidden: bool = False) -> dict:
        out = {"tables": []}
        for t in self.tables:
            if t.is_hidden and not include_hidden:
                continue
            out["tables"].append(
                {
                    "name": t.name,
                    "description": t.description,
                    "columns": [
                        {"name": c.name, "type": c.data_type, "description": c.description}
                        for c in t.columns
                        if include_hidden or not c.is_hidden
                    ],
                    "measures": [
                        {
                            "name": m.name,
                            "expression": m.expression,
                            "description": m.description,
                            "format_string": m.format_string,
                        }
                        for m in t.measures
                        if include_hidden or not m.is_hidden
                    ],
                }
            )
        return out

    def search(self, query: str, limit: int = 15) -> List[SchemaMatch]:
        q = query.lower().strip()
        results: List[SchemaMatch] = []

        def score(text: Optional[str]) -> float:
            if not text:
                return 0.0
            text = text.lower()
            if q in text:
                return 0.9 + 0.1 * (len(q) / max(len(text), 1))
            return SequenceMatcher(None, q, text).ratio()

        for t in self.tables:
            s = score(t.name)
            if s > 0.35:
                results.append(SchemaMatch(t.name, "table", t.name, s, {"description": t.description}))
            for c in t.columns:
                s = max(score(c.name), score(c.description) * 0.8)
                if s > 0.35:
                    results.append(
                        SchemaMatch(
                            t.name, "column", c.name, s,
                            {"data_type": c.data_type, "description": c.description},
                        )
                    )
            for m in t.measures:
                s = max(score(m.name), score(m.description) * 0.8)
                if s > 0.35:
                    results.append(
                        SchemaMatch(
                            t.name, "measure", m.name, s,
                            {"expression": m.expression, "description": m.description},
                        )
                    )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

# ---------------------------------------------------------------------
# CurrencySelector – unchanged
# ---------------------------------------------------------------------
class CurrencySelector:
    def __init__(self, config_path: Optional[str] = None, currency_codes: Optional[List[str]] = None):
        self.config = DEFAULT_CURRENCY_CONFIG.copy()
        self.user_preference = None
        self.config_path = config_path
        if currency_codes:
            self._build_config_from_codes(currency_codes)
        self._load_user_preference()

    def _build_config_from_codes(self, codes: List[str]):
        new_config = {}
        for code in codes:
            code_upper = code.upper()
            if code_upper in DEFAULT_CURRENCY_CONFIG:
                new_config[code_upper] = DEFAULT_CURRENCY_CONFIG[code_upper].copy()
            else:
                new_config[code_upper] = {
                    'symbol': code_upper[0] if len(code_upper) > 1 else code_upper,
                    'code': code_upper,
                    'name': code_upper,
                    'default': False,
                    'format': f'{{:,.2f}} {code_upper}',
                    'exchange_rate': 1.0
                }
        self.config = new_config

    def load_currencies_from_table(self, table_data: List[str]):
        if table_data:
            self._build_config_from_codes(table_data)

    def _load_user_preference(self):
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.user_preference = data.get('preferred_currency', 'USD')
            except Exception:
                self.user_preference = 'USD'
        else:
            self.user_preference = 'USD'

    def save_user_preference(self, currency_code: str):
        if currency_code not in self.config:
            raise ValueError(f"Unsupported currency: {currency_code}")
        self.user_preference = currency_code
        if self.config_path:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump({
                    'preferred_currency': currency_code,
                    'updated_at': datetime.now().isoformat()
                }, f)

    def detect_currency(self, question: str) -> Optional[str]:
        q = question.lower()
        currency_patterns = {}
        for code, info in self.config.items():
            patterns = [code.lower()]
            if 'symbol' in info:
                patterns.append(info['symbol'])
            if 'name' in info:
                patterns.append(info['name'].lower())
            if code == 'USD':
                patterns.extend(['dollar', 'us dollar', 'american dollar'])
            elif code == 'EUR':
                patterns.extend(['euro'])
            elif code == 'GBP':
                patterns.extend(['pound', 'sterling', 'british pound'])
            elif code == 'CAD':
                patterns.extend(['canadian dollar', 'canadian'])
            elif code == 'AUD':
                patterns.extend(['australian dollar', 'aussie'])
            currency_patterns[code] = patterns
        for code, patterns in currency_patterns.items():
            for pattern in patterns:
                if pattern in q:
                    return code
        return None

    def get_currency_context(self, currency_code: Optional[str] = None) -> CurrencyContext:
        if not currency_code:
            currency_code = self.user_preference or 'USD'
        if currency_code not in self.config:
            currency_code = 'USD'
        config = self.config[currency_code]
        return CurrencyContext(
            code=config['code'],
            symbol=config['symbol'],
            name=config['name'],
            format=config['format'],
            exchange_rate=config['exchange_rate'],
            is_default=config.get('default', False)
        )

    def format_amount(self, amount: float, currency_code: Optional[str] = None) -> str:
        ctx = self.get_currency_context(currency_code)
        return ctx.format.format(amount)

    def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        if from_currency not in self.config or to_currency not in self.config:
            return amount
        usd_amount = amount / self.config[from_currency]['exchange_rate']
        return usd_amount * self.config[to_currency]['exchange_rate']

    def get_available_currencies(self) -> List[str]:
        return list(self.config.keys())

    def get_currency_info(self, currency_code: str) -> Dict:
        if currency_code not in self.config:
            return {}
        return self.config[currency_code]

# ---------------------------------------------------------------------
# SemanticRouter – uses the index for actual table/measure names
# ---------------------------------------------------------------------
class SemanticRouter:
    def __init__(self, index: SemanticIndex, currency_selector: Optional[CurrencySelector] = None):
        self.index = index
        self.currency_selector = currency_selector or CurrencySelector()

    def _fetch_tables_and_measures(self, domain: str, question: str) -> tuple[List[str], List[str]]:
        """Use the index to find the most relevant tables/measures for the domain.
        We search using the domain name and some keywords from the question."""
        search_query = f"{domain} {question}"
        matches = self.index.search(search_query, limit=10)
        tables = []
        measures = []
        for m in matches:
            if m.kind == "table" and m.table not in tables:
                tables.append(m.table)
            elif m.kind == "measure" and m.name not in measures:
                if m.table not in tables:
                    tables.append(m.table)
                measures.append(m.name)
        # If no measures found, try to get all measures from the matched tables
        if not measures:
            for table_name in tables[:3]:
                table = self.index.get_table(table_name)
                if table:
                    for measure in table.measures:
                        if measure.name not in measures:
                            measures.append(measure.name)
        # If still no tables, fallback to all tables (limit to first 5)
        if not tables:
            tables = [t.name for t in self.index.tables[:5]]
        return tables[:10], measures[:10]

    def route(self, question: str) -> RoutingResult:
        # Preprocess question: replace underscores and hyphens with spaces
        question_lower = question.lower().replace('_', ' ').replace('-', ' ')
        # Also keep original for some exact checks
        original_lower = question.lower()

        detected_currency = self.currency_selector.detect_currency(question)
        currency_context = self.currency_selector.get_currency_context(detected_currency)

        # ---- SPECIAL CASES (fast path) ----
        # Currency domain
        if any(kw in question_lower for kw in ['currency', 'currencies', 'currency selector', 'available currencies', 'supported currencies', 'list currencies', 'show currencies']):
            tables, measures = self._fetch_tables_and_measures('currency', question)
            return RoutingResult(
                domain='currency',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # CLASSE_PRODOTTO / Category Group (also catches 'classe_prodotto' after preprocessing)
        if any(kw in question_lower for kw in ['category group', 'category code', 'category description', 'category description ita', 'category description eng', 'category group code', 'category group description', 'classe prodotto', 'product class', 'product classification']):
            tables, measures = self._fetch_tables_and_measures('product', question)
            return RoutingResult(
                domain='product',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Also handle original with underscore (in case preprocessing missed)
        if 'classe_prodotto' in original_lower:
            tables, measures = self._fetch_tables_and_measures('product', question)
            return RoutingResult(
                domain='product',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Category or Family
        if 'category or family' in question_lower or 'category/family' in question_lower:
            tables, measures = self._fetch_tables_and_measures('product', question)
            return RoutingResult(
                domain='product',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Time intelligence
        if any(kw in question_lower for kw in ['year-over-year', 'yoy', 'year over year', 'previous year', 'fiscal year', 'sales by month', 'monthly sales', 'quarterly revenue', 'weekly sales', 'wow', 'qoq', 'mom']):
            tables, measures = self._fetch_tables_and_measures('time_intelligence', question)
            return RoutingResult(
                domain='time_intelligence',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Business
        if any(kw in question_lower for kw in ['business', 'macro business', 'macrobusiness', 'macro category', 'business code', 'business description']):
            tables, measures = self._fetch_tables_and_measures('business', question)
            return RoutingResult(
                domain='business',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Product hierarchy
        if any(kw in question_lower for kw in ['category', 'gender', 'family', 'commercial model', 'commercial family', 'sub category', 'business code', 'stage of life', 'product hierarchy']):
            tables, measures = self._fetch_tables_and_measures('product', question)
            return RoutingResult(
                domain='product',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Regional sales / manager
        if 'regional sales' in question_lower or 'regional performance' in question_lower:
            tables, measures = self._fetch_tables_and_measures('manager', question)
            return RoutingResult(
                domain='manager',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Color / collection
        if any(kw in question_lower for kw in ['color', 'colour', 'collection', 'season', 'colors available', 'available colors']):
            tables, measures = self._fetch_tables_and_measures('product', question)
            return RoutingResult(
                domain='product',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Area manager
        if 'area manager' in question_lower or ('manager' in question_lower and ('regional' in question_lower or 'territory' in question_lower or 'area' in question_lower)):
            tables, measures = self._fetch_tables_and_measures('manager', question)
            return RoutingResult(
                domain='manager',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Customer / tier
        if any(kw in question_lower for kw in ['customer', 'tier', 'hi ticket', 'ticket']):
            tables, measures = self._fetch_tables_and_measures('customer', question)
            return RoutingResult(
                domain='customer',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Average unit price
        if any(kw in question_lower for kw in ['average unit price', 'avg unit price', 'average price']):
            tables, measures = self._fetch_tables_and_measures('sales', question)
            return RoutingResult(
                domain='sales',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Tables listing
        if ('table' in question_lower or 'tables' in question_lower) and any(kw in question_lower for kw in ['show', 'list', 'what', 'information', 'tell', 'which', 'available', 'all']):
            tables, measures = self._fetch_tables_and_measures('tables', question)
            return RoutingResult(
                domain='tables',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Gross margin by month
        if 'gross margin' in question_lower and ('month' in question_lower or 'by month' in question_lower):
            tables, measures = self._fetch_tables_and_measures('profitability', question)
            return RoutingResult(
                domain='profitability',
                tables=tables,
                measures=measures,
                confidence=0.95,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Inventory
        if 'inventory' in question_lower or 'stock' in question_lower:
            tables, measures = self._fetch_tables_and_measures('inventory', question)
            return RoutingResult(
                domain='inventory',
                tables=tables,
                measures=measures,
                confidence=0.9,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Returns
        if 'return' in question_lower or 'refund' in question_lower:
            tables, measures = self._fetch_tables_and_measures('returns', question)
            return RoutingResult(
                domain='returns',
                tables=tables,
                measures=measures,
                confidence=0.9,
                ambiguous=False,
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # ---- SCORE-BASED ROUTING (fallback) ----
        scores: Dict[str, int] = {}
        for domain, config in SEMANTIC_DOMAINS.items():
            score = 0
            for keyword in config['keywords']:
                if keyword in question_lower:
                    score += 1
            scores[domain] = score

        best_domain = max(scores, key=scores.get)
        best_score = scores[best_domain]

        if best_score == 0:
            return RoutingResult(
                domain='unknown',
                tables=[],
                measures=[],
                confidence=0.0,
                ambiguous=True,
                clarification_message=(
                    'I could not determine the business area. '
                    'Please specify whether you are asking about sales, '
                    'customers, inventory, returns, managers, products, colors, categories, '
                    'business, time intelligence, tables, or currencies.'
                ),
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        top_domains = [d for d, s in scores.items() if s == best_score and s > 0]
        if len(top_domains) > 1 and best_score < 3:
            return RoutingResult(
                domain='ambiguous',
                tables=[],
                measures=[],
                confidence=0.5,
                ambiguous=True,
                clarification_message=(
                    f'Your question may refer to multiple business areas ({", ".join(top_domains)}). '
                    'Please specify the KPI or business process.'
                ),
                currency=currency_context.code,
                currency_symbol=currency_context.symbol
            )

        # Fetch actual tables/measures from the index
        tables, measures = self._fetch_tables_and_measures(best_domain, question)
        confidence = min(1.0, 0.6 + 0.1 * best_score)

        return RoutingResult(
            domain=best_domain,
            tables=tables,
            measures=measures,
            confidence=round(confidence, 2),
            ambiguous=False,
            currency=currency_context.code,
            currency_symbol=currency_context.symbol
        )

    def set_user_currency_preference(self, currency_code: str):
        self.currency_selector.save_user_preference(currency_code)

    def get_available_currencies(self) -> List[str]:
        return self.currency_selector.get_available_currencies()

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------
def detect_measure(question: str) -> Optional[str]:
    q = question.lower()
    patterns = {
        'Net Revenue': ['net revenue', 'revenue', 'sales amount', 'net sales', 'revenue for', 'what was revenue', 'show revenue', 'sales', 'sales by'],
        'Gross Margin %': ['gross margin', 'margin percentage', 'margin %', 'margin', 'gross profit', 'gross margin for'],
        '__superprova Hi ticket': ['hi ticket', 'ticket', 'superprova', 'super prova', 'ticket value', 'hi ticket value'],
        'Average Unit Price': ['average unit price', 'unit price', 'average price', 'average selling price', 'avg price', 'avg unit price'],
        'Inventory Value': ['inventory value', 'inventory', 'stock value', 'warehouse value'],
        'Return Rate': ['return rate', 'returns', 'refund rate', 'return percentage'],
    }
    for measure, aliases in patterns.items():
        for alias in aliases:
            if alias in q:
                return measure
    return None

def detect_time_filters(question: str) -> Dict[str, str]:
    q = question.lower()
    filters: Dict[str, str] = {}
    year_match = re.search(r'(20\d{2})', q)
    if year_match:
        filters['year'] = year_match.group(1)
    quarter_match = re.search(r'q([1-4])', q)
    if quarter_match:
        filters['quarter'] = f'Q{quarter_match.group(1)}'
    month_match = re.search(
        r'(january|february|march|april|may|june|july|august|'
        r'september|october|november|december)',
        q, re.IGNORECASE
    )
    if month_match:
        filters['month'] = month_match.group(1).title()
    return filters

def build_clarification(question: str) -> Optional[str]:
    q = question.lower()
    time_indicators = ['month', 'quarter', 'year', '2026', '2025', 'q1', 'q2', 'q3', 'q4', 'week', 'fiscal', 'yoy', 'qoq', 'mom', 'wow']
    has_time = any(indicator in q for indicator in time_indicators)
    has_by = ' by ' in q
    entity_keywords = ['color', 'colour', 'collection', 'season', 'area manager', 'region', 'product', 'category', 'customer', 'store', 'warehouse', 'tier', 'article', 'gender', 'family', 'commercial', 'business', 'macro']
    has_entity = any(kw in q for kw in entity_keywords)
    if has_by or has_entity or has_time:
        return None
    if 'sales' in q and 'margin' not in q and 'revenue' not in q:
        return 'When you say "sales", do you mean **Net Revenue**, **Units Sold**, or **Number of Transactions**?'
    if 'margin' in q and '%' not in q and 'gross' in q:
        return 'Do you mean **Gross Margin %** or an absolute margin value?'
    if 'inventory' in q and 'value' not in q:
        return 'Do you want **Inventory Value**, **Inventory Quantity**, or **Inventory by Product**?'
    if 'return' in q and 'rate' not in q:
        return 'Do you mean **Return Rate** (percentage) or **Return Quantity**?'
    return None

# ---------------------------------------------------------------------
# Global singleton – instantiate with your definition directory
# ---------------------------------------------------------------------
_DEFINITION_DIR = os.environ.get("TMDL_DEFINITION_DIR", "./definition/tables")
_SCHEMA_JSON = os.environ.get("SCHEMA_JSON_PATH", None)

_index = SemanticIndex(_DEFINITION_DIR, schema_json_path=_SCHEMA_JSON)
_router = SemanticRouter(_index)

# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def route_question(question: str) -> RoutingResult:
    return _router.route(question)

def set_user_currency(currency_code: str) -> Dict:
    try:
        _router.set_user_currency_preference(currency_code)
        return {
            'success': True,
            'message': f'Currency set to {currency_code}',
            'currency': currency_code,
            'info': _router.currency_selector.get_currency_info(currency_code)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_currency() -> Dict:
    ctx = _router.currency_selector.get_currency_context()
    return {
        'currency': ctx.code,
        'symbol': ctx.symbol,
        'name': ctx.name,
        'format': ctx.format,
        'exchange_rate': ctx.exchange_rate,
        'is_default': ctx.is_default
    }

def get_available_currencies() -> Dict:
    currencies = _router.get_available_currencies()
    return {
        'currencies': currencies,
        'details': {code: _router.currency_selector.get_currency_info(code) for code in currencies}
    }

def format_currency(amount: float, currency_code: Optional[str] = None) -> str:
    return _router.currency_selector.format_amount(amount, currency_code)

def prepare_semantic_context(question: str) -> Dict:
    routing = _router.route(question)
    if routing.ambiguous:
        return {
            'allowed': False,
            'answer': routing.clarification_message or 'Please clarify your question.',
            'domain': routing.domain,
            'tables': [],
            'measures': [],
            'confidence': routing.confidence,
            'currency': routing.currency,
            'currency_symbol': routing.currency_symbol
        }
    clarification = build_clarification(question)
    if clarification:
        return {
            'allowed': False,
            'answer': clarification,
            'domain': routing.domain,
            'tables': routing.tables,
            'measures': routing.measures,
            'confidence': routing.confidence,
            'currency': routing.currency,
            'currency_symbol': routing.currency_symbol
        }
    return {
        'allowed': True,
        'answer': None,
        'domain': routing.domain,
        'tables': routing.tables,
        'measures': routing.measures,
        'confidence': routing.confidence,
        'detected_measure': detect_measure(question),
        'time_filters': detect_time_filters(question),
        'currency': routing.currency,
        'currency_symbol': routing.currency_symbol
    }

# ---------------------------------------------------------------------
# CLI test – demonstrates usage
# ---------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 80)
    print("SEMANTIC ROUTER TEST")
    print("=" * 80)
    print(f"TMDL Directory: {_DEFINITION_DIR}")
    print(f"Schema JSON: {_SCHEMA_JSON if _SCHEMA_JSON else 'Not set'}")
    print(f"Tables loaded: {len(_index.tables)}")
    print("=" * 80)

    if _index.tables:
        print("\nLoaded Tables:")
        for t in _index.tables[:5]:
            print(f"  - {t.name} (columns: {len(t.columns)}, measures: {len(t.measures)})")
        if len(_index.tables) > 5:
            print(f"  ... and {len(_index.tables)-5} more")
    else:
        print("\n⚠️ No tables loaded. Set TMDL_DEFINITION_DIR or SCHEMA_JSON_PATH.")
        print("   Using a small hard-coded example schema for demonstration.\n")
        example_schema = {
            "tables": [
                {
                    "name": "Sales",
                    "description": "Sales transactions",
                    "columns": [
                        {"name": "SalesAmount", "type": "decimal", "description": "Net revenue"},
                        {"name": "Date", "type": "date", "description": "Transaction date"}
                    ],
                    "measures": [
                        {"name": "Net Revenue", "expression": "SUM(Sales[SalesAmount])", "description": "Total net revenue"}
                    ]
                },
                {
                    "name": "Product",
                    "description": "Product catalog",
                    "columns": [
                        {"name": "ProductID", "type": "string", "description": "Product identifier"},
                        {"name": "Category", "type": "string", "description": "Product category"}
                    ]
                }
            ]
        }
        _index.load_from_dict(example_schema)
        print("✅ Example schema loaded.\n")

    test_questions = [
        "What was net revenue in Q2 2026?",
        "Show gross margin by month",
        "What is the average unit price?",
        "Tell me about the tables",
        "Show me the available currencies",
        "What are the category groups?",
        "Sales by region",
        "Dokumentację dla tabeli CLASSE_PRODOTTO",  # Polish – should fallback to unknown
        "Opisz model",                             # Polish – should fallback
        "Kategoria produktu"                       # Polish – should fallback
    ]

    print("ROUTING RESULTS:\n")
    for q in test_questions:
        print("-" * 60)
        print(f"Question: {q}")
        result = route_question(q)
        print(f"  Domain   : {result.domain}")
        print(f"  Tables   : {result.tables}")
        print(f"  Measures : {result.measures}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Currency : {result.currency} ({result.currency_symbol})")
        if result.ambiguous:
            print(f"  Clarification: {result.clarification_message}")
        print()

    print("=" * 80)
    print("prepare_semantic_context() test:")
    q = "Show revenue in euros"
    ctx = prepare_semantic_context(q)
    print(f"Question: {q}")
    print(f"Allowed: {ctx['allowed']}")
    if not ctx['allowed']:
        print(f"Answer: {ctx['answer']}")
    else:
        print(f"Domain: {ctx['domain']}")
        print(f"Tables: {ctx['tables']}")
        print(f"Measures: {ctx['measures']}")
        print(f"Currency: {ctx['currency']}")
        print(f"Detected measure: {ctx.get('detected_measure')}")