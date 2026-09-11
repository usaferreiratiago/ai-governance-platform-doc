"""
LLM Request Manager - Handles saving and retrieving LLM requests from the database.
"""
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from streamlit_app.db import SessionLocal, LLMRequest, engine


# ---------------------------------------------------------------------
# LLM Request Manager
# ---------------------------------------------------------------------
class LLMRequestManager:
    """
    Manages LLM requests in the database.
    """
    
    def __init__(self):
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """Ensure the llm_requests table exists."""
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS llm_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT UNIQUE,
                        question TEXT NOT NULL,
                        response TEXT,
                        model_used TEXT,
                        tokens_input INTEGER,
                        tokens_output INTEGER,
                        execution_time_ms INTEGER,
                        status TEXT,
                        user_name TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ llm_requests table verified/created")
        except Exception as e:
            print(f"⚠️ Error creating llm_requests table: {e}")
    
    def save_request(
        self,
        question: str,
        response: str = None,
        model_used: str = None,
        tokens_input: int = None,
        tokens_output: int = None,
        execution_time_ms: int = None,
        status: str = 'PENDING',
        user_name: str = 'system'
    ) -> Optional[str]:
        """
        Save an LLM request to the database.
        
        Args:
            question: The question asked to the LLM
            response: The response from the LLM
            model_used: The model used for the request
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens
            execution_time_ms: Execution time in milliseconds
            status: Status of the request (PENDING, COMPLETED, FAILED)
            user_name: Name of the user who made the request
        
        Returns:
            request_id if successful, None otherwise
        """
        try:
            request_id = f"llm-{uuid.uuid4().hex[:8]}"
            
            db = SessionLocal()
            
            llm_request = LLMRequest(
                request_id=request_id,
                question=question,
                response=response,
                model_used=model_used,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                execution_time_ms=execution_time_ms,
                status=status,
                user_name=user_name,
                created_at=datetime.now()
            )
            
            db.add(llm_request)
            db.commit()
            db.close()
            
            return request_id
        except Exception as e:
            print(f"❌ Error saving LLM request: {e}")
            return None
    
    def update_response(
        self,
        request_id: str,
        response: str,
        tokens_input: int = None,
        tokens_output: int = None,
        execution_time_ms: int = None,
        status: str = 'COMPLETED'
    ) -> bool:
        """
        Update an LLM request with the response.
        
        Args:
            request_id: The request ID
            response: The response from the LLM
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens
            execution_time_ms: Execution time in milliseconds
            status: Status of the request
        
        Returns:
            bool: True if successful
        """
        try:
            db = SessionLocal()
            llm_request = db.query(LLMRequest).filter(
                LLMRequest.request_id == request_id
            ).first()
            
            if not llm_request:
                db.close()
                return False
            
            llm_request.response = response
            llm_request.tokens_input = tokens_input
            llm_request.tokens_output = tokens_output
            llm_request.execution_time_ms = execution_time_ms
            llm_request.status = status
            
            db.commit()
            db.close()
            return True
        except Exception as e:
            print(f"❌ Error updating LLM request: {e}")
            return False
    
    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an LLM request by ID.
        
        Args:
            request_id: The request ID
        
        Returns:
            Dict with request data or None
        """
        try:
            db = SessionLocal()
            llm_request = db.query(LLMRequest).filter(
                LLMRequest.request_id == request_id
            ).first()
            db.close()
            
            if llm_request:
                return {
                    'id': llm_request.id,
                    'request_id': llm_request.request_id,
                    'question': llm_request.question,
                    'response': llm_request.response,
                    'model_used': llm_request.model_used,
                    'tokens_input': llm_request.tokens_input,
                    'tokens_output': llm_request.tokens_output,
                    'execution_time_ms': llm_request.execution_time_ms,
                    'status': llm_request.status,
                    'user_name': llm_request.user_name,
                    'created_at': llm_request.created_at.isoformat() if llm_request.created_at else None
                }
            return None
        except Exception as e:
            print(f"⚠️ Error getting LLM request: {e}")
            return None
    
    def get_requests_by_user(
        self,
        user_name: str,
        limit: int = 50,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get LLM requests by user.
        
        Args:
            user_name: Name of the user
            limit: Maximum number of requests
            status: Filter by status
        
        Returns:
            List of request dictionaries
        """
        try:
            db = SessionLocal()
            query = db.query(LLMRequest).filter(LLMRequest.user_name == user_name)
            
            if status:
                query = query.filter(LLMRequest.status == status)
            
            requests = query.order_by(
                LLMRequest.created_at.desc()
            ).limit(limit).all()
            
            db.close()
            
            return [
                {
                    'id': r.id,
                    'request_id': r.request_id,
                    'question': r.question,
                    'response': r.response,
                    'model_used': r.model_used,
                    'tokens_input': r.tokens_input,
                    'tokens_output': r.tokens_output,
                    'execution_time_ms': r.execution_time_ms,
                    'status': r.status,
                    'user_name': r.user_name,
                    'created_at': r.created_at.isoformat() if r.created_at else None
                }
                for r in requests
            ]
        except Exception as e:
            print(f"⚠️ Error getting LLM requests: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about LLM requests.
        
        Returns:
            Dict with statistics
        """
        try:
            db = SessionLocal()
            
            total = db.query(LLMRequest).count()
            completed = db.query(LLMRequest).filter(
                LLMRequest.status == 'COMPLETED'
            ).count()
            failed = db.query(LLMRequest).filter(
                LLMRequest.status == 'FAILED'
            ).count()
            pending = db.query(LLMRequest).filter(
                LLMRequest.status == 'PENDING'
            ).count()
            
            # Token usage
            token_stats = db.execute(
                text("""
                    SELECT 
                        SUM(tokens_input) as total_input,
                        SUM(tokens_output) as total_output,
                        AVG(tokens_input) as avg_input,
                        AVG(tokens_output) as avg_output
                    FROM llm_requests
                    WHERE status = 'COMPLETED'
                """)
            ).fetchone()
            
            # Model usage
            models = db.execute(
                text("""
                    SELECT model_used, COUNT(*) as count
                    FROM llm_requests
                    WHERE model_used IS NOT NULL
                    GROUP BY model_used
                    ORDER BY count DESC
                """)
            ).fetchall()
            
            db.close()
            
            return {
                'total': total,
                'completed': completed,
                'failed': failed,
                'pending': pending,
                'token_usage': {
                    'total_input': token_stats[0] or 0,
                    'total_output': token_stats[1] or 0,
                    'avg_input': token_stats[2] or 0,
                    'avg_output': token_stats[3] or 0
                },
                'models': [{'model': m[0], 'count': m[1]} for m in models]
            }
        except Exception as e:
            print(f"⚠️ Error getting LLM request statistics: {e}")
            return {
                'total': 0,
                'completed': 0,
                'failed': 0,
                'pending': 0,
                'token_usage': {},
                'models': []
            }
    
    def clear_old_requests(self, days: int = 30) -> int:
        """
        Clear LLM requests older than specified days.
        
        Args:
            days: Number of days to keep
        
        Returns:
            Number of deleted requests
        """
        try:
            db = SessionLocal()
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted = db.query(LLMRequest).filter(
                LLMRequest.created_at < cutoff_date
            ).delete()
            db.commit()
            db.close()
            return deleted
        except Exception as e:
            print(f"⚠️ Error clearing old LLM requests: {e}")
            return 0


# ---------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------
_request_manager = LLMRequestManager()


# ---------------------------------------------------------------------
# Public API Functions
# ---------------------------------------------------------------------
def save_llm_request(
    question: str,
    response: str = None,
    model_used: str = None,
    tokens_input: int = None,
    tokens_output: int = None,
    execution_time_ms: int = None,
    status: str = 'PENDING',
    user_name: str = 'system'
) -> Optional[str]:
    """Save an LLM request."""
    return _request_manager.save_request(
        question=question,
        response=response,
        model_used=model_used,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        execution_time_ms=execution_time_ms,
        status=status,
        user_name=user_name
    )


def update_llm_response(
    request_id: str,
    response: str,
    tokens_input: int = None,
    tokens_output: int = None,
    execution_time_ms: int = None,
    status: str = 'COMPLETED'
) -> bool:
    """Update an LLM request with the response."""
    return _request_manager.update_response(
        request_id=request_id,
        response=response,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        execution_time_ms=execution_time_ms,
        status=status
    )


def get_llm_request(request_id: str) -> Optional[Dict[str, Any]]:
    """Get an LLM request by ID."""
    return _request_manager.get_request(request_id)


def get_llm_requests_by_user(
    user_name: str,
    limit: int = 50,
    status: str = None
) -> List[Dict[str, Any]]:
    """Get LLM requests by user."""
    return _request_manager.get_requests_by_user(user_name, limit, status)


def get_llm_statistics() -> Dict[str, Any]:
    """Get statistics about LLM requests."""
    return _request_manager.get_statistics()


# ---------------------------------------------------------------------
# Decorator for tracking LLM requests
# ---------------------------------------------------------------------
def track_llm_request(user_name: str = "system"):
    """
    Decorator to track LLM requests.
    
    Usage:
        @track_llm_request(user_name="admin")
        def ask_llm(question):
            # Your LLM logic here
            return response
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract question from args or kwargs
            question = kwargs.get('question')
            if not question and args:
                question = args[0]
            if not question:
                return func(*args, **kwargs)
            
            # Save initial request
            request_id = save_llm_request(
                question=question,
                status='PENDING',
                user_name=user_name
            )
            
            # Execute function
            start_time = datetime.now()
            try:
                response = func(*args, **kwargs)
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                
                # Update request with response
                update_llm_response(
                    request_id=request_id,
                    response=response,
                    execution_time_ms=execution_time,
                    status='COMPLETED'
                )
                
                return response
            except Exception as e:
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                update_llm_response(
                    request_id=request_id,
                    response=str(e),
                    execution_time_ms=execution_time,
                    status='FAILED'
                )
                raise
        return wrapper
    return decorator


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM Request Manager')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--list', action='store_true', help='List recent requests')
    parser.add_argument('--user', help='Filter by user')
    parser.add_argument('--limit', type=int, default=10, help='Number of requests to show')
    parser.add_argument('--clear', type=int, help='Clear requests older than N days')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('LLM REQUEST MANAGER')
    print('=' * 60)
    
    if args.clear:
        print(f'\n🗑️ Clearing requests older than {args.clear} days...')
        deleted = _request_manager.clear_old_requests(args.clear)
        print(f"✅ Deleted {deleted} requests")
    
    elif args.stats:
        print('\n📊 Statistics:')
        print('-' * 60)
        stats = get_llm_statistics()
        print(f"Total: {stats.get('total', 0)}")
        print(f"Completed: {stats.get('completed', 0)}")
        print(f"Failed: {stats.get('failed', 0)}")
        print(f"Pending: {stats.get('pending', 0)}")
        
        token_usage = stats.get('token_usage', {})
        if token_usage:
            print(f"\nToken Usage:")
            print(f"  Total Input: {token_usage.get('total_input', 0)}")
            print(f"  Total Output: {token_usage.get('total_output', 0)}")
            print(f"  Avg Input: {token_usage.get('avg_input', 0):.0f}")
            print(f"  Avg Output: {token_usage.get('avg_output', 0):.0f}")
        
        models = stats.get('models', [])
        if models:
            print(f"\nModels Used:")
            for m in models:
                print(f"  {m['model']}: {m['count']} requests")
    
    elif args.list:
        print('\n📋 Recent LLM Requests:')
        print('-' * 60)
        
        user = args.user or 'system'
        requests = get_llm_requests_by_user(user, limit=args.limit)
        
        if requests:
            for r in requests:
                status_emoji = '✅' if r['status'] == 'COMPLETED' else '❌' if r['status'] == 'FAILED' else '⏳'
                print(f"\n{status_emoji} {r['request_id']} [{r['status']}]")
                print(f"   Question: {r['question'][:80]}...")
                print(f"   Model: {r['model_used'] or 'N/A'}")
                print(f"   Tokens: {r['tokens_input'] or 0}→{r['tokens_output'] or 0}")
                print(f"   Time: {r['execution_time_ms'] or 0}ms")
                print(f"   User: {r['user_name']}")
                print(f"   Created: {r['created_at']}")
        else:
            print(f"No requests found for user: {user}")
    
    else:
        print("\n💡 Available commands:")
        print("  --stats       Show statistics")
        print("  --list        List recent requests")
        print("  --user NAME   Filter by user")
        print("  --limit N     Number of requests to show (default: 10)")
        print("  --clear DAYS  Clear requests older than N days")