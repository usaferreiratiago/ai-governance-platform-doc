from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime

import requests

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------
# Paths (for prompt files, if used)
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT_DIR / 'prompts'
SYSTEM_PROMPT_FILE = PROMPTS_DIR / 'system_prompt_v1.md'
SEMANTIC_CONTEXT_FILE = PROMPTS_DIR / 'generated_context.md'

# ---------------------------------------------------------------------
# Environment – Claude defaults
# ---------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')  # stable default
ANTHROPIC_BASE_URL = os.getenv('ANTHROPIC_BASE_URL', 'https://api.anthropic.com/v1/messages')

# Reuse mock mode and timeout settings
MCP_MOCK_MODE = os.getenv('MCP_MOCK_MODE', 'true').lower() == 'true'
REQUEST_TIMEOUT = int(os.getenv('CLAUDE_TIMEOUT_SECONDS', '60'))   # separate timeout for Claude
CONTEXT_MEMORY_ENABLED = os.getenv('MCP_CONTEXT_MEMORY', 'true').lower() == 'true'
MAX_CONTEXT_TOKENS = int(os.getenv('MCP_MAX_CONTEXT_TOKENS', '4000'))
CLAUDE_MAX_TOKENS = int(os.getenv('CLAUDE_MAX_TOKENS', '1024'))   # max output tokens

# ---------------------------------------------------------------------
# Database for context memory (reuse same DB)
# ---------------------------------------------------------------------
try:
    from streamlit_app.db import SessionLocal
    from sqlalchemy import text, desc
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database not available, context memory disabled")

# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------
@dataclass
class ClaudeResponse:
    answer: str
    model: str
    raw_response: Optional[Dict] = None
    query_id: Optional[str] = None
    tokens_input: Optional[int] = None   # Claude doesn't provide token counts directly, but we can extract from usage if available
    tokens_output: Optional[int] = None
    execution_time_ms: Optional[int] = None
    context_used: Optional[Dict] = field(default_factory=dict)

# ---------------------------------------------------------------------
# Context Memory Manager (copied from gemini_client – could be shared)
# ---------------------------------------------------------------------
class ClaudeContextManager:
    """
    Manages context memory for Claude client.
    Handles conversation history, similar questions, and context summarization.
    """
    def __init__(self, user_id: Optional[str] = None, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.user_id = user_id or 'default_user'
        self.max_tokens = max_tokens
        self.history_limit = int(os.getenv('MCP_CONTEXT_HISTORY', '5'))
        self.days_limit = int(os.getenv('MCP_CONTEXT_DAYS', '7'))

    def get_conversation_history(self, limit: int = None) -> List[Dict[str, Any]]:
        if not DB_AVAILABLE or not CONTEXT_MEMORY_ENABLED:
            return []
        limit = limit or self.history_limit
        try:
            db = SessionLocal()
            history = db.execute(
                text("""
                    SELECT question, generated_sql as answer, created_at
                    FROM query_executions
                    WHERE user_name = :user_name
                    AND status = 'COMPLETED'
                    AND created_at >= datetime('now', :days_limit)
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {
                    "user_name": self.user_id,
                    "days_limit": f"-{self.days_limit} days",
                    "limit": limit
                }
            ).fetchall()
            db.close()
            return [
                {
                    'question': item[0],
                    'answer': item[1] or '',
                    'timestamp': item[2] if item[2] else ''
                }
                for item in history
            ]
        except Exception as e:
            logger.warning(f"Error retrieving conversation history: {e}")
            return []

    def get_similar_questions(self, question: str, limit: int = 3) -> List[Dict[str, Any]]:
        if not DB_AVAILABLE or not CONTEXT_MEMORY_ENABLED:
            return []
        try:
            db = SessionLocal()
            keywords = question.lower().split()
            keyword_conditions = []
            params = {}
            for i, keyword in enumerate(keywords[:5]):
                param_key = f'kw_{i}'
                keyword_conditions.append(f"LOWER(question) LIKE :{param_key}")
                params[param_key] = f"%{keyword}%"
            if keyword_conditions:
                query = f"""
                    SELECT question, generated_sql as answer, created_at
                    FROM query_executions
                    WHERE user_name = :user_name
                    AND status = 'COMPLETED'
                    AND question != :current_question
                    AND ({' OR '.join(keyword_conditions)})
                    ORDER BY created_at DESC
                    LIMIT :limit
                """
                params.update({
                    "user_name": self.user_id,
                    "current_question": question,
                    "limit": limit
                })
                similar = db.execute(text(query), params).fetchall()
                db.close()
                return [
                    {
                        'question': item[0],
                        'answer': item[1] or '',
                        'timestamp': item[2] if item[2] else ''
                    }
                    for item in similar
                ]
            db.close()
            return []
        except Exception as e:
            logger.warning(f"Error finding similar questions: {e}")
            return []

    def get_context_summary(self) -> str:
        history = self.get_conversation_history()
        if not history:
            return "No previous conversation history available."
        lines = ["## Previous Conversation Summary", ""]
        for i, item in enumerate(reversed(history)):
            lines.append(f"**Q{i+1}:** {item['question']}")
            if item['answer']:
                preview = item['answer'][:150] + "..." if len(item['answer']) > 150 else item['answer']
                lines.append(f"**A{i+1}:** {preview}")
            lines.append("")
        return "\n".join(lines)

    def save_conversation(
        self,
        question: str,
        response: str,
        model_used: str,
        execution_time_ms: int = None,
        status: str = 'COMPLETED',
        error_message: str = None,
        result_rows: int = None
    ) -> Optional[str]:
        if not DB_AVAILABLE:
            return None
        try:
            import uuid
            query_id = f"qe-{uuid.uuid4().hex[:8]}"
            db = SessionLocal()
            db.execute(
                text("""
                    INSERT INTO query_executions (
                        id, question, generated_sql, status, model_used, user_name,
                        execution_time_ms, error_message, result_rows, created_at
                    )
                    VALUES (
                        :id, :question, :sql, :status, :model_used, :user_name,
                        :execution_time_ms, :error_message, :result_rows, :created_at
                    )
                """),
                {
                    "id": query_id,
                    "question": question,
                    "sql": response[:500] if response else '',
                    "status": status,
                    "model_used": model_used,
                    "user_name": self.user_id,
                    "execution_time_ms": execution_time_ms,
                    "error_message": error_message,
                    "result_rows": result_rows,
                    "created_at": datetime.now().isoformat()
                }
            )
            db.commit()
            db.close()
            logger.info(f"Saved conversation: {query_id} for user {self.user_id}")
            return query_id
        except Exception as e:
            logger.warning(f"Error saving conversation: {e}")
            return None

# ---------------------------------------------------------------------
# Enhanced Prompt Builder (copied and adapted for Claude)
# ---------------------------------------------------------------------
def build_enhanced_prompt(
    question: str,
    system_prompt: str,
    semantic_context: str,
    context_manager: Optional[ClaudeContextManager] = None,
    include_history: bool = True,
    include_similar: bool = True
) -> Dict[str, Any]:
    """
    Build a prompt structure suitable for Claude's API.
    Returns a dict with 'system', 'messages', and 'context' (for logging).
    """
    # Claude uses a system message and a list of user/assistant messages.
    # We'll build the conversation history, then append the current question.

    messages = []
    # System prompt is separate
    system = system_prompt

    # Add semantic context as a system note (or as a user message?)
    # We'll prepend it to the user question, or put it in a separate system block.
    # We'll combine semantic context with the system prompt for clarity.
    full_system = system_prompt + "\n\n" + semantic_context

    # Add conversation history (if any) as alternating user/assistant messages
    if context_manager and CONTEXT_MEMORY_ENABLED:
        if include_history:
            history = context_manager.get_conversation_history()
            if history:
                # We'll add previous Q&A pairs (up to a reasonable limit to avoid token overflow)
                for item in history:
                    messages.append({"role": "user", "content": item['question']})
                    if item['answer']:
                        # Truncate long answers
                        ans = item['answer'][:200] + "..." if len(item['answer']) > 200 else item['answer']
                        messages.append({"role": "assistant", "content": ans})
        if include_similar:
            similar = context_manager.get_similar_questions(question)
            if similar:
                # Add similar questions as context (but not as full conversation)
                # We'll add them as a single user message mentioning them.
                similar_text = "Similar questions previously asked:\n" + "\n".join(
                    f"- {s['question']}" for s in similar
                )
                messages.append({"role": "user", "content": similar_text})
                # We don't have assistant responses for those, so just include them.

    # Now add the current question
    messages.append({"role": "user", "content": question})

    # Return the payload parts
    return {
        "system": full_system,
        "messages": messages,
        "context_used": {
            "history_included": include_history,
            "similar_included": include_similar,
            "context_manager": context_manager.__class__.__name__ if context_manager else None
        }
    }

# ---------------------------------------------------------------------
# Claude Client
# ---------------------------------------------------------------------
class ClaudeClient:
    """
    Anthropic Claude API client with context memory support.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model or CLAUDE_MODEL
        self.user_id = user_id or 'default_user'
        self.context_manager = ClaudeContextManager(self.user_id)

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def ask(
        self,
        question: str,
        system_prompt: Optional[str] = None,
        semantic_context: Optional[str] = None,
        include_history: bool = True,
        include_similar: bool = True,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> ClaudeResponse:
        """
        Send a question to Claude with context memory.
        """
        start_time = datetime.now()

        if MCP_MOCK_MODE:
            response = self._mock_response(question, include_history)
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            query_id = self.context_manager.save_conversation(
                question=question,
                response=response.answer,
                model_used='mock-claude',
                execution_time_ms=execution_time
            )
            response.query_id = query_id
            response.execution_time_ms = execution_time
            return response

        if not self.api_key:
            error_msg = 'ANTHROPIC_API_KEY environment variable is not configured.'
            self.context_manager.save_conversation(
                question=question,
                response='',
                model_used=self.model,
                status='FAILED',
                error_message=error_msg
            )
            raise RuntimeError(error_msg)

        # Load prompts
        system_prompt = system_prompt or self._load_system_prompt()
        semantic_context = semantic_context or self._load_semantic_context()

        # Build enhanced prompt
        prompt_data = build_enhanced_prompt(
            question=question,
            system_prompt=system_prompt,
            semantic_context=semantic_context,
            context_manager=self.context_manager,
            include_history=include_history,
            include_similar=include_similar
        )

        # Prepare API payload
        payload = {
            "model": self.model,
            "max_tokens": max_tokens or CLAUDE_MAX_TOKENS,
            "temperature": temperature,
            "top_p": top_p,
            "system": prompt_data["system"],
            "messages": prompt_data["messages"]
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        logger.info('Calling Claude model %s for user %s', self.model, self.user_id)

        try:
            response = requests.post(
                ANTHROPIC_BASE_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            # Extract answer
            # Claude response format: {"content": [{"type": "text", "text": "..."}]}
            answer = ""
            if 'content' in data and data['content']:
                for block in data['content']:
                    if block.get('type') == 'text':
                        answer += block.get('text', '')
            if not answer:
                answer = "No text content in Claude response."

            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Token counts are not returned by Claude API, but we can infer from usage if present
            tokens_input = None
            tokens_output = None
            if 'usage' in data:
                tokens_input = data['usage'].get('input_tokens')
                tokens_output = data['usage'].get('output_tokens')

            query_id = self.context_manager.save_conversation(
                question=question,
                response=answer,
                model_used=self.model,
                execution_time_ms=execution_time,
                status='COMPLETED'
            )

            return ClaudeResponse(
                answer=answer,
                model=self.model,
                raw_response=data,
                query_id=query_id,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                execution_time_ms=execution_time,
                context_used=prompt_data.get('context_used', {})
            )

        except requests.exceptions.Timeout:
            error_msg = f'Request timed out after {REQUEST_TIMEOUT} seconds.'
            logger.error(error_msg)
            self.context_manager.save_conversation(
                question=question,
                response='',
                model_used=self.model,
                status='FAILED',
                error_message=error_msg
            )
            return ClaudeResponse(
                answer=f'Error: {error_msg}',
                model=self.model,
                raw_response={'error': 'timeout'}
            )

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            # Mask any API key in the error
            error_msg = re.sub(r'api-key[:\s]+[^\s]+', 'api-key: [MASKED]', error_msg)
            logger.error('Claude API error: %s', error_msg)
            self.context_manager.save_conversation(
                question=question,
                response='',
                model_used=self.model,
                status='FAILED',
                error_message=error_msg
            )
            return ClaudeResponse(
                answer=f'Error: {error_msg}',
                model=self.model,
                raw_response={'error': error_msg}
            )

        except Exception as e:
            error_msg = str(e)
            logger.exception('Unexpected error: %s', error_msg)
            self.context_manager.save_conversation(
                question=question,
                response='',
                model_used=self.model,
                status='FAILED',
                error_message=error_msg
            )
            return ClaudeResponse(
                answer=f'Unexpected error: {error_msg}',
                model=self.model,
                raw_response={'error': error_msg}
            )

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------
    def _load_system_prompt(self) -> str:
        """Load system prompt from database or file."""
        try:
            from mcp.prompt_loader import get_prompt_from_db
            content = get_prompt_from_db('system_prompt_v1')
            if content:
                return content
        except Exception:
            pass
        if SYSTEM_PROMPT_FILE.exists():
            return SYSTEM_PROMPT_FILE.read_text(encoding='utf-8')
        return (
            'You are a governed enterprise analytics assistant. '
            'Answer only using the approved semantic model.'
        )

    def _load_semantic_context(self) -> str:
        """Load semantic context from database or file."""
        try:
            from mcp.prompt_loader import get_prompt_from_db
            content = get_prompt_from_db('generated_context')
            if content:
                return content
        except Exception:
            pass
        if SEMANTIC_CONTEXT_FILE.exists():
            return SEMANTIC_CONTEXT_FILE.read_text(encoding='utf-8')
        return 'No semantic context available.'

    # -----------------------------------------------------------------
    # Mock mode
    # -----------------------------------------------------------------
    def _mock_response(self, question: str, include_history: bool = True) -> ClaudeResponse:
        """Generate mock response (similar to Gemini mock but with Claude label)."""
        q = question.lower()
        history_context = ""
        if include_history and CONTEXT_MEMORY_ENABLED:
            history = self.context_manager.get_conversation_history()
            if history:
                history_context = f" (Previous conversation: {len(history)} interactions)"

        if 'revenue' in q or 'sales' in q:
            answer = f'Based on the approved semantic model, Net Revenue is $12,435,221.{history_context}'
        elif 'gross margin' in q:
            answer = f'Based on the approved semantic model, Gross Margin % is 42.1%.{history_context}'
        elif 'average unit price' in q or 'unit price' in q:
            answer = f'Based on the approved semantic model, Average Unit Price is $89.34.{history_context}'
        elif 'table' in q:
            answer = f'The approved semantic model contains Sales, Customer, Product, and Date tables.{history_context}'
        else:
            answer = f'The requested information is not available in the approved semantic model.{history_context}'

        return ClaudeResponse(
            answer=answer,
            model='mock-claude',
            raw_response={'mock': True, 'history_included': include_history},
            context_used={'history_included': include_history}
        )

    # -----------------------------------------------------------------
    # Context management
    # -----------------------------------------------------------------
    def clear_context(self) -> None:
        if self.context_manager:
            self.context_manager.history_limit = 0

    def set_user_id(self, user_id: str) -> None:
        self.user_id = user_id
        self.context_manager = ClaudeContextManager(user_id)

# ---------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------
_client = ClaudeClient()

def ask_claude(
    question: str,
    system_prompt: Optional[str] = None,
    semantic_context: Optional[str] = None,
    user_id: Optional[str] = None,
    include_history: bool = True,
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
) -> str:
    """
    Simplified API for Claude with context memory.
    Returns only the answer string.
    """
    if user_id:
        _client.set_user_id(user_id)
    response = _client.ask(
        question=question,
        system_prompt=system_prompt,
        semantic_context=semantic_context,
        include_history=include_history,
        max_tokens=max_tokens,
        temperature=temperature
    )
    return response.answer

def ask_claude_full(
    question: str,
    system_prompt: Optional[str] = None,
    semantic_context: Optional[str] = None,
    user_id: Optional[str] = None,
    include_history: bool = True,
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
) -> ClaudeResponse:
    """
    Full API for Claude with context memory.
    Returns a ClaudeResponse object.
    """
    if user_id:
        _client.set_user_id(user_id)
    return _client.ask(
        question=question,
        system_prompt=system_prompt,
        semantic_context=semantic_context,
        include_history=include_history,
        max_tokens=max_tokens,
        temperature=temperature
    )

# ---------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    print('🔍 Claude Client with Context Memory')
    print('=' * 60)
    print(f'MCP_MOCK_MODE = {MCP_MOCK_MODE}')
    print(f'CLAUDE_MODEL  = {CLAUDE_MODEL}')
    print(f'CONTEXT_MEMORY_ENABLED = {CONTEXT_MEMORY_ENABLED}')
    print(f'MAX_CONTEXT_TOKENS = {MAX_CONTEXT_TOKENS}')
    print('=' * 60)
    print()

    test_user = 'cli_test_user'
    questions = [
        'What is net revenue?',
        'What is gross margin?',
        'Show the information about the tables',
        'What is average unit price?',
    ]

    for question in questions:
        print('=' * 80)
        print(f'Question: {question}')
        response = ask_claude_full(
            question=question,
            user_id=test_user,
            include_history=True
        )
        print(f'Model   : {response.model}')
        print(f'Answer  : {response.answer[:200]}...')
        print(f'Query ID: {response.query_id}')
        print(f'Tokens Input: {response.tokens_input}')
        print(f'Tokens Output: {response.tokens_output}')
        print(f'Execution Time: {response.execution_time_ms}ms')
        print(f'Context Used: {response.context_used}')
        print('=' * 80)
        print()

    print('\n📊 Context Summary:')
    print('-' * 60)
    context_manager = ClaudeContextManager(test_user)
    print(context_manager.get_context_summary())