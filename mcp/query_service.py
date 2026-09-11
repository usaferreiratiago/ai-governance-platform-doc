"""
================================================================================
Semantic Query Service – Governed Power BI Semantic Model Q&A
Version: 1.6 (Multilingual documentation detection)
================================================================================
"""

from __future__ import annotations

import sys
import json
import os
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests

# Try to import msal, but handle gracefully if not installed
try:
    from msal import ConfidentialClientApplication
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False
    logger.warning("msal not installed - Power BI authentication disabled")

from guardrails.mandatory_filters import validate_filters
from guardrails.prompt_injection import validate_user_question
from guardrails.response_validator import validate_and_format_response
from guardrails.semantic_allowlist import validate_question_against_allowlist
from mcp.cache import cache
from mcp.gemini_client import ask_gemini
from mcp.claude_client import ask_claude
from mcp.metadata_service import build_semantic_context
from mcp.semantic_router import prepare_semantic_context, _index

# Import database for context memory
try:
    from streamlit_app.db import SessionLocal, QueryExecution
    from sqlalchemy import text, desc
    DB_AVAILABLE = True
except ImportError:
    logger.warning("Database not available, context memory disabled")
    DB_AVAILABLE = False


# ---------------------------------------------------------------------
# Environment & Production settings
# ---------------------------------------------------------------------
PRODUCTION_MODE = os.getenv('PRODUCTION_MODE', 'false').lower() == 'true'
MOCK_MODE = os.getenv('MCP_MOCK_MODE', 'true').lower() == 'true'

PRIMARY_MODEL = os.getenv('MCP_MODEL_PRIMARY', 'gemini').lower()
SECONDARY_MODEL = os.getenv('MCP_MODEL_SECONDARY', 'claude' if PRIMARY_MODEL == 'gemini' else 'gemini').lower()
FALLBACK_ENABLED = os.getenv('MCP_MODEL_FALLBACK_ENABLED', 'true').lower() == 'true'

if PRODUCTION_MODE:
    MOCK_MODE = False
    logger.info("🔒 Production mode enabled – mock mode forced OFF")

PBI_API_BASE = os.getenv('PBI_API_BASE_URL', 'https://api.powerbi.com/v1.0/myorg')
TENANT_ID = os.getenv('PBI_TENANT_ID')
CLIENT_ID = os.getenv('PBI_CLIENT_ID')
CLIENT_SECRET = os.getenv('PBI_CLIENT_SECRET')
DATASET_ID = os.getenv('PBI_DATASET_ID')

CONTEXT_HISTORY_LIMIT = int(os.getenv('MCP_CONTEXT_HISTORY', '5'))
CONTEXT_DAYS_LIMIT = int(os.getenv('MCP_CONTEXT_DAYS', '7'))

if PRODUCTION_MODE:
    required_vars = {
        'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
        'PBI_TENANT_ID': TENANT_ID,
        'PBI_CLIENT_ID': CLIENT_ID,
        'PBI_CLIENT_SECRET': CLIENT_SECRET,
        'PBI_DATASET_ID': DATASET_ID,
    }
    models_to_check = [PRIMARY_MODEL]
    if FALLBACK_ENABLED:
        models_to_check.append(SECONDARY_MODEL)
    for model in set(models_to_check):
        if model == 'claude':
            required_vars['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        raise RuntimeError(f"Production mode requires: {', '.join(missing)}")
    if not MSAL_AVAILABLE:
        raise RuntimeError("Production mode requires msal library.")

if len(_index.tables) == 0:
    logger.warning("Semantic index is empty. Set TMDL_DEFINITION_DIR environment variable.")

if MOCK_MODE:
    logger.warning("⚠️ Running in MOCK mode – answers will be hard‑coded. Set MCP_MOCK_MODE=false for real data.")

logger.info(f"🤖 Primary: {PRIMARY_MODEL}, Secondary: {SECONDARY_MODEL}, Fallback: {FALLBACK_ENABLED}")


# ---------------------------------------------------------------------
# Helper: call model with fallback
# ---------------------------------------------------------------------
def _call_model_with_fallback(
    model_type: str,
    question: str,
    semantic_context: str,
    user_id: str,
    include_history: bool,
    system_prompt: Optional[str] = None,
) -> tuple[str, str]:
    def _call_single(model: str) -> str:
        if model == 'claude':
            return ask_claude(
                question=question,
                system_prompt=system_prompt,
                semantic_context=semantic_context,
                user_id=user_id,
                include_history=include_history
            )
        else:
            return ask_gemini(
                question=question,
                system_prompt=system_prompt,
                semantic_context=semantic_context,
                user_id=user_id,
                include_history=include_history
            )

    attempts = [model_type]
    if FALLBACK_ENABLED:
        if model_type == PRIMARY_MODEL:
            attempts.append(SECONDARY_MODEL)
        else:
            attempts.append(PRIMARY_MODEL)

    last_error = None
    for attempt_model in attempts:
        try:
            logger.info(f"Attempting call with {attempt_model}")
            result = _call_single(attempt_model)
            if attempt_model != model_type:
                logger.info(f"✅ Fallback to {attempt_model} succeeded")
            return result, attempt_model
        except Exception as e:
            logger.warning(f"❌ {attempt_model} failed: {e}")
            last_error = e
            if not FALLBACK_ENABLED or attempt_model == attempts[-1]:
                raise
    raise last_error


# ---------------------------------------------------------------------
# Context Memory Manager
# ---------------------------------------------------------------------
class ContextMemoryManager:
    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id or 'default_user'
        self.history_limit = CONTEXT_HISTORY_LIMIT
        self.days_limit = CONTEXT_DAYS_LIMIT

    def get_conversation_history(self, limit: int = None) -> List[Dict[str, Any]]:
        if not DB_AVAILABLE:
            return []
        limit = limit or self.history_limit
        cutoff_date = datetime.now() - timedelta(days=self.days_limit)
        try:
            db = SessionLocal()
            history = db.query(QueryExecution).filter(
                QueryExecution.user_name == self.user_id,
                QueryExecution.created_at >= cutoff_date,
                QueryExecution.status == 'COMPLETED'
            ).order_by(desc(QueryExecution.created_at)).limit(limit).all()
            db.close()
            return [{
                'question': item.question,
                'answer': item.generated_sql or '',
                'timestamp': item.created_at.isoformat() if item.created_at else '',
                'status': item.status
            } for item in history]
        except Exception as e:
            logger.error("Error retrieving conversation history: %s", e)
            return []

    def save_query_execution(self, question: str, response: str, status: str = 'COMPLETED',
                             model_used: str = None, execution_time_ms: int = None) -> Optional[str]:
        if not DB_AVAILABLE:
            return None
        try:
            import uuid
            query_id = f"qe-{uuid.uuid4().hex[:8]}"
            db = SessionLocal()
            query_exec = QueryExecution(
                id=query_id,
                question=question,
                generated_sql=response[:500] if response else '',
                status=status,
                model_used=model_used or 'gemini',
                user_name=self.user_id,
                execution_time_ms=execution_time_ms,
                created_at=datetime.now()
            )
            db.add(query_exec)
            db.commit()
            db.close()
            return query_id
        except Exception as e:
            logger.error("Error saving query execution: %s", e)
            return None

    def get_similar_questions(self, question: str, limit: int = 3) -> List[Dict[str, Any]]:
        if not DB_AVAILABLE:
            return []
        try:
            db = SessionLocal()
            keywords = [w for w in question.lower().split() if len(w) > 3][:5]
            if not keywords:
                db.close()
                return []
            conditions = []
            params = {'user_name': self.user_id, 'status': 'COMPLETED', 'current_question': question, 'limit': limit}
            for i, keyword in enumerate(keywords):
                param_key = f'kw_{i}'
                conditions.append(f"LOWER(question) LIKE :{param_key}")
                params[param_key] = f"%{keyword}%"
            query_text = f"""
                SELECT question, generated_sql as answer, created_at
                FROM query_executions 
                WHERE user_name = :user_name 
                AND status = :status
                AND question != :current_question
                AND ({' OR '.join(conditions)})
                ORDER BY created_at DESC 
                LIMIT :limit
            """
            result = db.execute(text(query_text), params).fetchall()
            db.close()
            return [{'question': item[0], 'answer': item[1] or '', 'timestamp': item[2] if item[2] else ''} for item in result]
        except Exception as e:
            logger.error("Error finding similar questions: %s", e)
            return []


# ---------------------------------------------------------------------
# Power BI authentication & query execution
# ---------------------------------------------------------------------
def _get_access_token() -> str:
    if MOCK_MODE:
        return "mock_token"
    if not MSAL_AVAILABLE:
        raise RuntimeError('msal library not installed.')
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
        raise RuntimeError('Power BI credentials are not configured.')
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f'https://login.microsoftonline.com/{TENANT_ID}',
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=['https://analysis.windows.net/powerbi/api/.default'])
    if 'access_token' not in result:
        raise RuntimeError(f'Failed to obtain Power BI token: {result}')
    return result['access_token']

def execute_dax_query(dax_query: str) -> Dict:
    if MOCK_MODE:
        return {'mock': True, 'query': dax_query}
    if not DATASET_ID:
        raise RuntimeError('PBI_DATASET_ID is not configured.')
    token = _get_access_token()
    url = f'{PBI_API_BASE}/datasets/{DATASET_ID}/executeQueries'
    payload = {'queries': [{'query': dax_query}], 'serializerSettings': {'includeNulls': True}}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

def format_dax_result(result: Dict) -> str:
    if not result or 'results' not in result:
        return "No data returned from Power BI."
    tables = result.get('results', [])
    if not tables:
        return "Empty result set."
    table_data = tables[0].get('tables', [])
    if not table_data:
        return "Empty table."
    rows = table_data[0].get('rows', [])
    if not rows:
        return "No rows returned."
    columns = list(rows[0].keys())
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, '')) for col in columns) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Helpers for filter validation
# ---------------------------------------------------------------------
def _is_filter_valid(validation_result) -> bool:
    if validation_result is None:
        return True
    if isinstance(validation_result, dict):
        return validation_result.get('valid', False) or validation_result.get('passed', False)
    if hasattr(validation_result, 'passed'):
        return validation_result.passed
    if hasattr(validation_result, 'valid'):
        return validation_result.valid
    return True

def _get_filter_message(validation_result) -> str:
    if validation_result is None:
        return "Filter validation passed."
    if isinstance(validation_result, dict):
        return validation_result.get('message', validation_result.get('answer', "Validation failed."))
    if hasattr(validation_result, 'message'):
        return validation_result.message
    return "Validation failed."

def _get_missing_filters(validation_result) -> list:
    if isinstance(validation_result, dict):
        return validation_result.get('missing_filters', [])
    if hasattr(validation_result, 'missing_filters'):
        return validation_result.missing_filters
    return []


# ---------------------------------------------------------------------
# Language‑agnostic table name extractor (unchanged)
# ---------------------------------------------------------------------
def _extract_table_name(question: str) -> Optional[str]:
    table_names = {t.name.lower() for t in _index.tables}
    if not table_names:
        return None
    list_phrases = [
        'list all tables', 'show tables', 'available tables',
        'what tables', 'all tables', 'all the tables',
        'liste alle tabellen', 'todas as tabelas', 'tutte le tabelle',
        'todas las tablas', 'toutes les tables', 'alle tabellen',
        '全部表', 'すべてのテーブル', 'جميع الجداول'
    ]
    q_lower = question.lower()
    if any(phrase in q_lower for phrase in list_phrases):
        return None
    potential_names = re.findall(r'\b[A-Za-z_]{2,}\b', question)
    for token in potential_names:
        if token.lower() in table_names:
            return token.upper()
    indicator_patterns = re.compile(
        r'(?:table|tabela|tabella|tabelle|tabla|tableau|tavola|tabel)\s+([A-Za-z_]+)',
        re.IGNORECASE
    )
    match = indicator_patterns.search(question)
    if match:
        candidate = match.group(1).strip()
        if candidate.lower() in table_names:
            return candidate.upper()
    words = re.findall(r'\b\w+\b', question.lower())
    for word in words:
        if word in table_names:
            return word.upper()
    return None

def _handle_table_query_by_name(table_name: str) -> Optional[str]:
    table_obj = _index.get_table(table_name)
    if not table_obj:
        return None
    lines = [f"## 📋 Table: `{table_obj.name}`"]
    if table_obj.description:
        lines.append(f"**Description:** {table_obj.description}")
    lines.append("\n### 📊 Columns")
    if table_obj.columns:
        lines.append("| Column Name | Data Type | Description |")
        lines.append("|-------------|-----------|-------------|")
        for col in table_obj.columns:
            if col.is_hidden:
                continue
            lines.append(f"| `{col.name}` | {col.data_type or 'N/A'} | {col.description or ''} |")
    else:
        lines.append("*No columns defined.*")
    lines.append("\n### 📈 Measures")
    if table_obj.measures:
        lines.append("| Measure Name | Expression | Description | Format String |")
        lines.append("|--------------|------------|-------------|---------------|")
        for m in table_obj.measures:
            if m.is_hidden:
                continue
            expr = m.expression[:50] + "..." if len(m.expression) > 50 else m.expression
            lines.append(f"| `{m.name}` | `{expr}` | {m.description or ''} | {m.format_string or ''} |")
    else:
        lines.append("*No measures defined.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Mock Answers (only used when MOCK_MODE=True)
# ---------------------------------------------------------------------
def _mock_answer(question: str, context_history: List[Dict] = None, currency: str = 'USD') -> str:
    # Simplified mock – only used when MOCK_MODE is true.
    # We keep it minimal; real answers come from the LLM.
    q = question.lower()
    if 'table' in q or 'tables' in q or 'document' in q:
        return "The approved semantic model exposes tables: Sales, Customer, Product, Date, Inventory, ACTIVE_CUSTOMER_MONTH, AREA_MANAGER, ARTICOLI_COLORE, ARTICOLI, BUSINESS, CALENDARIO, Category or Family, Currency Selector, CLASSE_PRODOTTO, and many more. Use real mode for full list."
    if 'revenue' in q or 'sales' in q:
        return "Net Revenue for Q2 2026 is $12,435,221."
    return "The requested information is not available in the approved semantic model."


# ---------------------------------------------------------------------
# Build enhanced semantic context with full schema and language instruction
# ---------------------------------------------------------------------
def build_enhanced_context(
    question: str,
    memory_manager: ContextMemoryManager,
    include_history: bool = True,
    include_similar: bool = True,
    provided_filters: Optional[Dict[str, Any]] = None,
    mode: str = 'text'
) -> str:
    # 1. Build a rich schema summary from the index
    schema_summary = _index.schema_summary(include_hidden=False)
    schema_json = json.dumps(schema_summary, indent=2, default=str)

    # 2. Base context (legacy)
    base_context = build_semantic_context()
    if not base_context:
        base_context = "No additional context."

    parts = []
    parts.append("=" * 60)
    parts.append("SEMANTIC MODEL SCHEMA (full)")
    parts.append("=" * 60)
    parts.append(schema_json)

    parts.append("\n" + "=" * 60)
    parts.append("ADDITIONAL CONTEXT")
    parts.append("=" * 60)
    parts.append(str(base_context))

    if provided_filters:
        parts.append("\n" + "=" * 60)
        parts.append("USER PROVIDED FILTERS")
        parts.append("=" * 60)
        for key, value in provided_filters.items():
            if value:
                parts.append(f"- {key}: {value}")

    if include_history:
        history = memory_manager.get_conversation_history()
        if history:
            parts.append("\n" + "=" * 60)
            parts.append("CONVERSATION HISTORY")
            parts.append("=" * 60)
            for i, item in enumerate(history):
                parts.append(f"\n**[Previous {i+1}]**")
                parts.append(f"Q: {item['question']}")
                if item['answer']:
                    preview = item['answer'][:300] + "..." if len(item['answer']) > 300 else item['answer']
                    parts.append(f"A: {preview}")

        if include_similar:
            similar = memory_manager.get_similar_questions(question)
            if similar:
                parts.append("\n" + "=" * 60)
                parts.append("SIMILAR QUESTIONS")
                parts.append("=" * 60)
                for i, item in enumerate(similar):
                    parts.append(f"\n**[Related {i+1}]**")
                    parts.append(f"Q: {item['question']}")
                    if item['answer']:
                        preview = item['answer'][:200] + "..." if len(item['answer']) > 200 else item['answer']
                        parts.append(f"A: {preview}")

    # Language instruction
    parts.append("\n" + "=" * 60)
    parts.append("LANGUAGE INSTRUCTION")
    parts.append("=" * 60)
    parts.append("Answer in the same language as the user's question.")

    # Mode instruction
    if mode == 'dax':
        parts.append("\n" + "=" * 60)
        parts.append("GENERATE DAX QUERY")
        parts.append("=" * 60)
        parts.append("Based on the schema and filters, generate a single DAX query. Return ONLY the DAX query, nothing else.")
    else:
        parts.append("\n" + "=" * 60)
        parts.append("PROVIDE TEXT SUMMARY")
        parts.append("=" * 60)
        parts.append("Provide a clear, concise answer using the schema and filters. Use tables if appropriate.")

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Generate full model documentation (uses the index directly)
# ---------------------------------------------------------------------
def generate_model_documentation() -> str:
    if not _index.tables:
        return "⚠️ No tables loaded – the semantic index is empty."
    lines = ["# 📊 Semantic Model Documentation"]
    lines.append(f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n---\n")
    total_tables = len(_index.tables)
    total_columns = sum(len(t.columns) for t in _index.tables)
    total_measures = sum(len(t.measures) for t in _index.tables)
    lines.append(f"- **Tables:** {total_tables}\n- **Columns:** {total_columns}\n- **Measures:** {total_measures}\n")
    lines.append("## 📋 Tables Overview\n| Table Name | Description | Columns | Measures | Hidden |")
    lines.append("|------------|-------------|---------|----------|--------|")
    for t in sorted(_index.tables, key=lambda x: x.name):
        hidden = "✅" if t.is_hidden else ""
        lines.append(f"| `{t.name}` | {t.description or ''} | {len(t.columns)} | {len(t.measures)} | {hidden} |")
    lines.append("\n## 🔍 Detailed Table Schemas")
    for t in sorted(_index.tables, key=lambda x: x.name):
        lines.append(f"\n### Table: `{t.name}`")
        if t.description:
            lines.append(f"**Description:** {t.description}")
        if t.is_hidden:
            lines.append("**Hidden:** ✅")
        lines.append("\n#### Columns")
        if t.columns:
            lines.append("| Column Name | Data Type | Description | Hidden |")
            lines.append("|-------------|-----------|-------------|--------|")
            for col in sorted(t.columns, key=lambda x: x.name):
                hidden = "✅" if col.is_hidden else ""
                lines.append(f"| `{col.name}` | {col.data_type or 'N/A'} | {col.description or ''} | {hidden} |")
        else:
            lines.append("*No columns defined.*")
        lines.append("\n#### Measures")
        if t.measures:
            lines.append("| Measure Name | Expression | Description | Format String | Hidden |")
            lines.append("|--------------|------------|-------------|---------------|--------|")
            for m in sorted(t.measures, key=lambda x: x.name):
                hidden = "✅" if m.is_hidden else ""
                expr = m.expression[:50] + "..." if len(m.expression) > 50 else m.expression
                lines.append(f"| `{m.name}` | `{expr}` | {m.description or ''} | {m.format_string or ''} | {hidden} |")
        else:
            lines.append("*No measures defined.*")
        lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# LLM‑based fallback routing (now detects documentation intent)
# ---------------------------------------------------------------------
def _llm_classify_domain(question: str, user_id: str) -> Dict[str, Any]:
    prompt = f"""Classify the following user question into one of these business domains: 
sales, customers, inventory, returns, managers, products, colors, categories, 
business, time_intelligence, tables, currencies.

Also detect the user's intent:
- If the user is asking for a full list/documentation of all tables (e.g., "show me all tables", "document the model", "list tables", "generate documentation"), set intent to "documentation".
- Otherwise, set intent to "question".

Also extract any specific measure mentioned (e.g., Net Revenue, Gross Margin %, Average Unit Price).

Return a JSON object with keys: domain, detected_measure, time_filters (object with year, quarter, month if present), intent.

Question: {question}
"""
    try:
        response, _ = _call_model_with_fallback(
            model_type=PRIMARY_MODEL,
            question=prompt,
            semantic_context="",
            user_id=user_id,
            include_history=False,
            system_prompt="You are a classification assistant. Output only valid JSON."
        )
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return {
                'domain': data.get('domain', 'unknown'),
                'detected_measure': data.get('detected_measure'),
                'time_filters': data.get('time_filters', {}),
                'intent': data.get('intent', 'question')
            }
        else:
            return {'domain': 'unknown', 'intent': 'question'}
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return {'domain': 'unknown', 'intent': 'question'}


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------
def ask_semantic_model(
    question: str,
    user_id: Optional[str] = None,
    include_history: bool = True,
    provided_filters: Optional[Dict[str, str]] = None,
    return_type: str = 'text'
) -> Dict:
    question = (question or '').strip()
    provided_filters = provided_filters or {}

    if not question:
        return {'answer': 'Please enter a business question.', 'source': 'Validation'}

    memory_manager = ContextMemoryManager(user_id)
    cache_key = f'{return_type}::{question}::user::{user_id or "default"}::filters::{json.dumps(provided_filters)}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Guardrails
    injection = validate_user_question(question)
    if not injection.get('allowed', True):
        return {'answer': injection.get('answer', 'Question blocked.'), 'source': 'Prompt Injection Guardrail'}

    allowlist = validate_question_against_allowlist(question)
    if not allowlist.get('allowed', True):
        return {'answer': allowlist.get('answer', 'Question not allowed.'), 'source': 'Semantic Allowlist Guardrail'}

    # Semantic routing
    routing = prepare_semantic_context(question)
    if not routing.get('allowed', True) or routing.get('domain') in ('unknown', 'ambiguous'):
        logger.info("Router uncertain – using LLM fallback for classification.")
        classification = _llm_classify_domain(question, user_id)
        domain = classification.get('domain', 'unknown')
        detected_measure = classification.get('detected_measure')
        time_filters = classification.get('time_filters', {})
        intent = classification.get('intent', 'question')
        routing = {
            'allowed': True,
            'domain': domain,
            'tables': [],
            'measures': [],
            'confidence': 0.7,
            'detected_measure': detected_measure,
            'time_filters': time_filters,
            'currency': None,
            'currency_symbol': None,
            'intent': intent
        }
    else:
        detected_measure = routing.get('detected_measure')
        intent = routing.get('intent', 'question')

    # ---- DETECT DOCUMENTATION INTENT ----
    # If the intent is 'documentation' or the domain is 'tables' and the question
    # contains words like 'all', 'list', 'document', etc., we call the full documentation.
    # Also handle the fast English triggers here.
    q_lower = question.lower()
    if (intent == 'documentation' or 
        (routing.get('domain') == 'tables' and any(w in q_lower for w in ['all', 'list', 'document', 'show me all', 'generate documentation'])) or
        any(phrase in q_lower for phrase in ['describe the model', 'full documentation', 'generate documentation', 'model documentation'])):
        doc = generate_model_documentation()
        return {
            'answer': doc,
            'source': 'Semantic Index',
            'domain': 'documentation',
            'confidence': 1.0,
            'filters_applied': provided_filters,
            'return_type': 'text'
        }

    # 1. Handle explicit table name queries (language‑agnostic)
    table_name = _extract_table_name(question)
    if table_name and return_type != 'dax':
        table_answer = _handle_table_query_by_name(table_name)
        if table_answer:
            result = {
                'answer': table_answer,
                'source': 'Semantic Index',
                'domain': 'tables',
                'confidence': 1.0,
                'filters_applied': provided_filters,
                'return_type': 'text'
            }
            cache.set(cache_key, result)
            return result

    # 2. "Make measure" -> DAX mode
    if 'make measure' in q_lower or 'create measure' in q_lower:
        if any(kw in q_lower for kw in ['to return', 'top', 'rank', 'list', 'show', 'calculate']):
            return_type = 'dax'

    # 3. Mandatory filter validation
    filter_validation = validate_filters(detected_measure, provided_filters)
    if not _is_filter_valid(filter_validation):
        return {
            'answer': _get_filter_message(filter_validation),
            'source': 'Mandatory Filter Guardrail',
            'measure': detected_measure,
            'missing_filters': _get_missing_filters(filter_validation),
        }

    # 4. Build enhanced context (includes full schema and language instruction)
    semantic_context = build_enhanced_context(
        question=question,
        memory_manager=memory_manager,
        include_history=include_history,
        include_similar=True,
        provided_filters=provided_filters,
        mode=return_type
    )

    start_time = datetime.now()

    if return_type == 'dax':
        if MOCK_MODE:
            dummy_dax = "EVALUATE SUMMARIZE(Sales, 'ARTICOLI'[Gender Code], 'Net Revenue')"
            dummy_result = {"results": [{"tables": [{"rows": [{"Gender Code": "Women", "Net Revenue": 6500000}]}]}]}
            answer = format_dax_result(dummy_result)
            answer = f"**Mock DAX Query**:\n```dax\n{dummy_dax}\n```\n\n**Results**:\n{answer}"
            source = 'Mock DAX'
        else:
            try:
                model_response, model_used = _call_model_with_fallback(
                    model_type=PRIMARY_MODEL,
                    question=question,
                    semantic_context=semantic_context,
                    user_id=user_id,
                    include_history=include_history,
                    system_prompt=None
                )
                dax_query = model_response
                match = re.search(r'```(?:dax)?\s*(.*?)\s*```', dax_query, re.DOTALL)
                if match:
                    dax_query = match.group(1).strip()
                else:
                    dax_query = dax_query.strip()
                result_json = execute_dax_query(dax_query)
                formatted_result = format_dax_result(result_json)
                answer = f"**DAX Query**:\n```dax\n{dax_query}\n```\n\n**Results**:\n{formatted_result}"
                source = f'{model_used.capitalize()} + Power BI'
            except Exception as e:
                logger.exception("DAX generation/execution failed")
                answer = f"Error generating or executing DAX: {str(e)}"
                source = 'DAX Error'
        result = {
            'answer': answer,
            'source': source,
            'domain': routing.get('domain'),
            'confidence': routing.get('confidence'),
            'filters_applied': provided_filters,
            'return_type': 'dax'
        }
    else:
        if MOCK_MODE:
            answer = _mock_answer(question, memory_manager.get_conversation_history() if include_history else [])
            result = validate_and_format_response(
                question=question,
                answer=answer,
                measure=detected_measure,
                source='Governed Semantic Model',
                domain=routing.get('domain'),
                confidence=routing.get('confidence'),
                history_included=include_history,
                filters_applied=provided_filters
            )
            model_used = 'mock'
        else:
            try:
                model_response, model_used = _call_model_with_fallback(
                    model_type=PRIMARY_MODEL,
                    question=question,
                    semantic_context=semantic_context,
                    user_id=user_id,
                    include_history=include_history,
                    system_prompt=None
                )
                result = validate_and_format_response(
                    question=question,
                    answer=model_response,
                    measure=detected_measure,
                    source=f'{model_used.capitalize()} + Governed Semantic Model',
                    domain=routing.get('domain'),
                    confidence=routing.get('confidence'),
                    history_included=include_history,
                    filters_applied=provided_filters
                )
            except Exception as e:
                logger.exception("All model attempts failed")
                answer = f"Unable to generate an answer: {str(e)}"
                result = {
                    'answer': answer,
                    'source': 'Error',
                    'domain': routing.get('domain'),
                    'confidence': 0.0,
                    'filters_applied': provided_filters,
                    'return_type': 'text'
                }
                model_used = 'error'
        result['return_type'] = 'text'

    cache.set(cache_key, result)
    execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
    model_used = model_used if 'model_used' in locals() else ('dax' if return_type == 'dax' else ('mock' if MOCK_MODE else PRIMARY_MODEL))
    memory_manager.save_query_execution(
        question=question,
        response=result.get('answer', ''),
        status='COMPLETED',
        model_used=model_used,
        execution_time_ms=execution_time
    )

    return result


def ask_semantic_model_text(
    question: str,
    user_id: Optional[str] = None,
    include_history: bool = True,
    provided_filters: Optional[Dict[str, str]] = None,
    return_type: str = 'text'
) -> str:
    result = ask_semantic_model(question, user_id, include_history, provided_filters, return_type)
    return result.get('answer', 'No answer available.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--doc', action='store_true')
    parser.add_argument('--question', type=str)
    parser.add_argument('--filters', type=str)
    parser.add_argument('--return-type', type=str, default='text', choices=['text', 'dax'])
    args = parser.parse_args()

    if args.doc:
        print(generate_model_documentation())
    elif args.question:
        filters = json.loads(args.filters) if args.filters else {}
        result = ask_semantic_model(args.question, provided_filters=filters, return_type=args.return_type)
        print(result.get('answer', 'No answer'))
    else:
        print("🔍 Semantic Query Service (multilingual) – type your question (any language).")
        while True:
            q = input("\nQuestion: ")
            if q.lower() in ('exit', 'quit'):
                break
            if not q:
                continue
            result = ask_semantic_model(q, user_id='cli_user', provided_filters={'Date': 'Q2 2026', 'Organization': 'Retail'})
            print("\nAnswer:", result.get('answer'))
            print("Source:", result.get('source'))