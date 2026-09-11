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
# Paths
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT_DIR / 'prompts'
SYSTEM_PROMPT_FILE = PROMPTS_DIR / 'system_prompt_v1.md'
SEMANTIC_CONTEXT_FILE = PROMPTS_DIR / 'generated_context.md'


# ---------------------------------------------------------------------
# Environment – default to a model that definitely exists
# ---------------------------------------------------------------------
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')   # changed default
GEMINI_BASE_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models'
)

MCP_MOCK_MODE = os.getenv('MCP_MOCK_MODE', 'true').lower() == 'true'
REQUEST_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT_SECONDS', '30'))
CONTEXT_MEMORY_ENABLED = os.getenv('MCP_CONTEXT_MEMORY', 'true').lower() == 'true'
MAX_CONTEXT_TOKENS = int(os.getenv('MCP_MAX_CONTEXT_TOKENS', '4000'))


# ---------------------------------------------------------------------
# Import database for context memory
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
class GeminiResponse:
    answer: str
    model: str
    raw_response: Optional[Dict] = None
    query_id: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    execution_time_ms: Optional[int] = None
    context_used: Optional[Dict] = field(default_factory=dict)


# ---------------------------------------------------------------------
# Context Memory Manager for Gemini
# ---------------------------------------------------------------------
class GeminiContextManager:
    """
    Manages context memory for Gemini client.
    Handles conversation history, similar questions, and context summarization.
    """
    
    def __init__(self, user_id: Optional[str] = None, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.user_id = user_id or 'default_user'
        self.max_tokens = max_tokens
        self.history_limit = int(os.getenv('MCP_CONTEXT_HISTORY', '5'))
        self.days_limit = int(os.getenv('MCP_CONTEXT_DAYS', '7'))
    
    def get_conversation_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve recent conversation history from database.
        
        Args:
            limit: Maximum number of history items to retrieve
        
        Returns:
            List of conversation history items
        """
        if not DB_AVAILABLE or not CONTEXT_MEMORY_ENABLED:
            return []
        
        limit = limit or self.history_limit
        
        try:
            db = SessionLocal()
            
            # Get recent query executions
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
            
            formatted_history = []
            for item in history:
                formatted_history.append({
                    'question': item[0],
                    'answer': item[1] or '',
                    'timestamp': item[2] if item[2] else ''
                })
            
            return formatted_history
            
        except Exception as e:
            logger.warning(f"Error retrieving conversation history: {e}")
            return []
    
    def get_similar_questions(self, question: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find similar questions from history.
        
        Args:
            question: The current question
            limit: Maximum number of similar questions
        
        Returns:
            List of similar questions with answers
        """
        if not DB_AVAILABLE or not CONTEXT_MEMORY_ENABLED:
            return []
        
        try:
            db = SessionLocal()
            
            # Extract keywords from question
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
        """
        Generate a context summary from conversation history.
        
        Returns:
            String with context summary
        """
        history = self.get_conversation_history()
        
        if not history:
            return "No previous conversation history available."
        
        lines = []
        lines.append("## Previous Conversation Summary")
        lines.append("")
        
        # Show recent interactions
        for i, item in enumerate(reversed(history)):
            lines.append(f"**Q{i+1}:** {item['question']}")
            if item['answer']:
                # Truncate long answers
                answer_preview = item['answer'][:150] + "..." if len(item['answer']) > 150 else item['answer']
                lines.append(f"**A{i+1}:** {answer_preview}")
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
        """
        Save a conversation to the database.
        
        Args:
            question: User question
            response: Model response
            model_used: Model name
            execution_time_ms: Execution time
            status: Execution status
            error_message: Error message if failed
            result_rows: Number of result rows
        
        Returns:
            Query ID if successful
        """
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
# Enhanced Prompt Builder
# ---------------------------------------------------------------------
def build_enhanced_prompt(
    question: str,
    system_prompt: str,
    semantic_context: str,
    context_manager: Optional[GeminiContextManager] = None,
    include_history: bool = True,
    include_similar: bool = True
) -> str:
    """
    Build an enhanced prompt with context memory.
    
    Args:
        question: User question
        system_prompt: System prompt
        semantic_context: Semantic context
        context_manager: Context memory manager
        include_history: Whether to include history
        include_similar: Whether to include similar questions
    
    Returns:
        Enhanced prompt string
    """
    prompt_parts = []
    
    # System prompt
    prompt_parts.append(f"## SYSTEM PROMPT\n{system_prompt}")
    
    # Semantic context
    prompt_parts.append(f"\n## SEMANTIC CONTEXT\n{semantic_context}")
    
    # Context memory
    if context_manager and CONTEXT_MEMORY_ENABLED:
        if include_history:
            history = context_manager.get_conversation_history()
            if history:
                prompt_parts.append("\n## CONVERSATION HISTORY")
                for i, item in enumerate(history):
                    prompt_parts.append(f"Q: {item['question']}")
                    if item['answer']:
                        # Truncate long answers
                        answer_preview = item['answer'][:200] + "..." if len(item['answer']) > 200 else item['answer']
                        prompt_parts.append(f"A: {answer_preview}")
                    prompt_parts.append("")
        
        if include_similar:
            similar = context_manager.get_similar_questions(question)
            if similar:
                prompt_parts.append("\n## SIMILAR QUESTIONS (for reference)")
                for i, item in enumerate(similar):
                    prompt_parts.append(f"Q: {item['question']}")
                    if item['answer']:
                        answer_preview = item['answer'][:150] + "..." if len(item['answer']) > 150 else item['answer']
                        prompt_parts.append(f"A: {answer_preview}")
                    prompt_parts.append("")
    
    # User question
    prompt_parts.append(f"\n## USER QUESTION\n{question}")
    
    # Instructions
    prompt_parts.append("\n## INSTRUCTIONS")
    prompt_parts.append("1. Use ONLY information from the semantic model.")
    prompt_parts.append("2. Reference previous conversations if relevant.")
    prompt_parts.append("3. If information is not available, state clearly.")
    prompt_parts.append("4. Provide a concise, accurate answer.")
    
    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------
class GeminiClient:
    """
    Gemini API client with context memory support.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        self.user_id = user_id or 'default_user'
        self.context_manager = GeminiContextManager(self.user_id)
    
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
    ) -> GeminiResponse:
        """
        Send a question to Gemini with context memory.
        
        Args:
            question: User question
            system_prompt: System prompt
            semantic_context: Semantic context
            include_history: Include conversation history
            include_similar: Include similar questions
        
        Returns:
            GeminiResponse with answer and metadata
        """
        start_time = datetime.now()
        
        if MCP_MOCK_MODE:
            response = self._mock_response(question, include_history)
            # Save to database
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            query_id = self.context_manager.save_conversation(
                question=question,
                response=response.answer,
                model_used='mock',
                execution_time_ms=execution_time
            )
            response.query_id = query_id
            response.execution_time_ms = execution_time
            return response
        
        if not self.api_key:
            error_msg = 'GEMINI_API_KEY environment variable is not configured.'
            # Save error to database
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
        
        # Build enhanced prompt with context memory
        enhanced_prompt = build_enhanced_prompt(
            question=question,
            system_prompt=system_prompt,
            semantic_context=semantic_context,
            context_manager=self.context_manager,
            include_history=include_history,
            include_similar=include_similar
        )
        
        # Build payload
        payload = self._build_payload(enhanced_prompt)
        
        # Build URL – safe version for logging (without key)
        url_with_key = f'{GEMINI_BASE_URL}/{self.model}:generateContent?key={self.api_key}'
        url_safe = f'{GEMINI_BASE_URL}/{self.model}:generateContent'  # no key
        
        logger.info('Calling Gemini model %s for user %s', self.model, self.user_id)
        
        try:
            response = requests.post(
                url_with_key,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            
            # If status is 404, the model doesn't exist – give a clear user message
            if response.status_code == 404:
                error_msg = (
                    f"The model '{self.model}' was not found. Please check your GEMINI_MODEL environment variable. "
                    f"Common valid models: gemini-2.5-pro, gemini-1.5-pro, gemini-pro. "
                    f"Current value: {self.model}"
                )
                logger.error(error_msg)
                self.context_manager.save_conversation(
                    question=question,
                    response='',
                    model_used=self.model,
                    status='FAILED',
                    error_message=error_msg
                )
                return GeminiResponse(
                    answer=f"Error: {error_msg}",
                    model=self.model,
                    raw_response={'error': 'model_not_found'}
                )
            
            response.raise_for_status()
            data = response.json()
            answer = self._extract_text(data)
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Extract token usage if available
            tokens_input = None
            tokens_output = None
            if 'usageMetadata' in data:
                usage = data['usageMetadata']
                tokens_input = usage.get('promptTokenCount')
                tokens_output = usage.get('candidatesTokenCount')
            
            # Save to database
            query_id = self.context_manager.save_conversation(
                question=question,
                response=answer,
                model_used=self.model,
                execution_time_ms=execution_time,
                status='COMPLETED'
            )
            
            return GeminiResponse(
                answer=answer,
                model=self.model,
                raw_response=data,
                query_id=query_id,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                execution_time_ms=execution_time,
                context_used={
                    'history_included': include_history,
                    'similar_included': include_similar,
                    'context_manager': self.context_manager.__class__.__name__
                }
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
            return GeminiResponse(
                answer=f'Error: {error_msg}',
                model=self.model,
                raw_response={'error': 'timeout'}
            )
            
        except requests.exceptions.RequestException as e:
            # Sanitise error message – remove any URL that might contain the key
            error_msg = str(e)
            # Remove anything that looks like a URL with a key
            error_msg = re.sub(r'https?://[^\s]+key=[^\s]+', '[API_KEY_MASKED]', error_msg)
            logger.error('Gemini API error: %s', error_msg)
            self.context_manager.save_conversation(
                question=question,
                response='',
                model_used=self.model,
                status='FAILED',
                error_message=error_msg
            )
            return GeminiResponse(
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
            return GeminiResponse(
                answer=f'Unexpected error: {error_msg}',
                model=self.model,
                raw_response={'error': error_msg}
            )
    
    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------
    def _build_payload(self, prompt: str) -> Dict:
        """Build the Gemini API payload."""
        return {
            'contents': [
                {
                    'role': 'user',
                    'parts': [
                        {'text': prompt},
                    ],
                }
            ]
        }
    
    def _extract_text(self, data: Dict) -> str:
        """Extract text from Gemini response."""
        try:
            candidates = data.get('candidates', [])
            
            if not candidates:
                return 'No response returned by Gemini.'
            
            parts = candidates[0]['content']['parts']
            
            texts = [
                part.get('text', '')
                for part in parts
                if part.get('text')
            ]
            
            return '\n'.join(texts).strip()
            
        except Exception as exc:
            logger.exception('Failed to parse Gemini response: %s', exc)
            return 'Unable to parse Gemini response.'
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from database or file."""
        try:
            from mcp.prompt_loader import get_prompt_from_db
            content = get_prompt_from_db('system_prompt_v1')
            if content:
                return content
        except Exception:
            pass
        
        # Fallback to file
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
        
        # Fallback to file
        if SEMANTIC_CONTEXT_FILE.exists():
            return SEMANTIC_CONTEXT_FILE.read_text(encoding='utf-8')
        
        return 'No semantic context available.'
    
    # -----------------------------------------------------------------
    # Mock mode
    # -----------------------------------------------------------------
    def _mock_response(self, question: str, include_history: bool = True) -> GeminiResponse:
        """Generate mock response."""
        q = question.lower()
        
        # Check if we have context history
        history_context = ""
        if include_history and CONTEXT_MEMORY_ENABLED:
            history = self.context_manager.get_conversation_history()
            if history:
                history_context = f" (Previous conversation: {len(history)} interactions)"
        
        if 'revenue' in q or 'sales' in q:
            answer = (
                f'Based on the approved semantic model, Net Revenue is '
                f'$12,435,221.{history_context}'
            )
        
        elif 'gross margin' in q:
            answer = (
                f'Based on the approved semantic model, Gross Margin % is '
                f'42.1%.{history_context}'
            )
        
        elif 'average unit price' in q or 'unit price' in q:
            answer = (
                f'Based on the approved semantic model, Average Unit Price is '
                f'$89.34.{history_context}'
            )
        
        elif 'table' in q:
            answer = (
                f'The approved semantic model contains the following governed '
                f'tables: Sales, Customer, Product, and Date.{history_context}'
            )
        
        else:
            answer = (
                f'The requested information is not available in the approved '
                f'semantic model.{history_context}'
            )
        
        return GeminiResponse(
            answer=answer,
            model='mock-semantic-model',
            raw_response={'mock': True, 'history_included': include_history},
            context_used={'history_included': include_history}
        )
    
    # -----------------------------------------------------------------
    # Context management
    # -----------------------------------------------------------------
    def clear_context(self) -> None:
        """Clear the context memory for this user."""
        if self.context_manager:
            self.context_manager.history_limit = 0
    
    def set_user_id(self, user_id: str) -> None:
        """Set the user ID for context tracking."""
        self.user_id = user_id
        self.context_manager = GeminiContextManager(user_id)


# ---------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------
_client = GeminiClient()


def ask_gemini(
    question: str,
    system_prompt: Optional[str] = None,
    semantic_context: Optional[str] = None,
    user_id: Optional[str] = None,
    include_history: bool = True,
) -> str:
    """
    Simplified API for Gemini with context memory.
    
    Args:
        question: User question
        system_prompt: System prompt
        semantic_context: Semantic context
        user_id: User ID for context tracking
        include_history: Include conversation history
    
    Returns:
        String with the answer
    """
    if user_id:
        _client.set_user_id(user_id)
    
    response = _client.ask(
        question=question,
        system_prompt=system_prompt,
        semantic_context=semantic_context,
        include_history=include_history,
    )
    return response.answer


def ask_gemini_full(
    question: str,
    system_prompt: Optional[str] = None,
    semantic_context: Optional[str] = None,
    user_id: Optional[str] = None,
    include_history: bool = True,
) -> GeminiResponse:
    """
    Full API for Gemini with context memory.
    
    Returns:
        GeminiResponse with answer and metadata
    """
    if user_id:
        _client.set_user_id(user_id)
    
    return _client.ask(
        question=question,
        system_prompt=system_prompt,
        semantic_context=semantic_context,
        include_history=include_history,
    )


# ---------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    print('🔍 Gemini Client with Context Memory')
    print('=' * 60)
    print(f'MCP_MOCK_MODE = {MCP_MOCK_MODE}')
    print(f'GEMINI_MODEL  = {GEMINI_MODEL}')
    print(f'CONTEXT_MEMORY_ENABLED = {CONTEXT_MEMORY_ENABLED}')
    print(f'MAX_CONTEXT_TOKENS = {MAX_CONTEXT_TOKENS}')
    print('=' * 60)
    print()
    
    # Test with context memory
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
        
        response = ask_gemini_full(
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
    
    # Show context summary
    print('\n📊 Context Summary:')
    print('-' * 60)
    context_manager = GeminiContextManager(test_user)
    print(context_manager.get_context_summary())