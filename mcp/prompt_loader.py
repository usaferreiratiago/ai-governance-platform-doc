"""
Load prompts from database with fallback to files.
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

try:
    from streamlit_app.db import SessionLocal, Prompt
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠️ Database not available, using file fallback")


def get_prompt_from_db(name: str) -> Optional[str]:
    """
    Get a prompt from the database by name.
    
    Args:
        name: Name of the prompt
    
    Returns:
        Prompt content or None
    """
    if not DB_AVAILABLE:
        return None
    
    try:
        db = SessionLocal()
        prompt = db.query(Prompt).filter(
            Prompt.name == name,
            Prompt.is_active == True
        ).first()
        db.close()
        
        return prompt.content if prompt else None
    except Exception as e:
        print(f"⚠️ Error loading prompt from database: {e}")
        return None


def get_prompt_details(name: str) -> Optional[Dict[str, Any]]:
    """
    Get full prompt details from the database.
    
    Args:
        name: Name of the prompt
    
    Returns:
        Prompt details dictionary or None
    """
    if not DB_AVAILABLE:
        return None
    
    try:
        db = SessionLocal()
        prompt = db.query(Prompt).filter(
            Prompt.name == name,
            Prompt.is_active == True
        ).first()
        db.close()
        
        if prompt:
            return {
                'id': prompt.id,
                'name': prompt.name,
                'content': prompt.content,
                'version': prompt.version,
                'description': prompt.description,
                'is_active': prompt.is_active,
                'created_by': prompt.created_by,
                'created_at': prompt.created_at.isoformat() if prompt.created_at else None,
                'updated_at': prompt.updated_at.isoformat() if prompt.updated_at else None
            }
        return None
    except Exception as e:
        print(f"⚠️ Error getting prompt details: {e}")
        return None


def get_all_active_prompts() -> List[Dict[str, Any]]:
    """
    Get all active prompts from the database.
    
    Returns:
        List of prompt dictionaries
    """
    if not DB_AVAILABLE:
        return []
    
    try:
        db = SessionLocal()
        prompts = db.query(Prompt).filter(Prompt.is_active == True).all()
        db.close()
        
        return [
            {
                'name': p.name,
                'content': p.content,
                'version': p.version,
                'description': p.description,
                'is_active': p.is_active
            }
            for p in prompts
        ]
    except Exception as e:
        print(f"⚠️ Error getting all prompts: {e}")
        return []


def get_active_prompt_content(name: str = None) -> Optional[str]:
    """
    Get the content of an active prompt.
    
    Args:
        name: Name of the prompt (if None, returns the first active prompt)
    
    Returns:
        Prompt content or None
    """
    if not DB_AVAILABLE:
        return None
    
    try:
        db = SessionLocal()
        query = db.query(Prompt).filter(Prompt.is_active == True)
        
        if name:
            query = query.filter(Prompt.name == name)
        
        prompt = query.first()
        db.close()
        
        return prompt.content if prompt else None
    except Exception as e:
        print(f"⚠️ Error getting active prompt: {e}")
        return None


def load_system_prompt(file_path: Path = None) -> str:
    """
    Load system prompt from database or fallback to file.
    
    Args:
        file_path: Path to file fallback
    
    Returns:
        System prompt content
    """
    # Try database first
    content = get_prompt_from_db('system_prompt_v1')
    if content:
        return content
    
    # Fallback to file
    if file_path and file_path.exists():
        return file_path.read_text(encoding='utf-8')
    
    # Default fallback
    return """You are a governed enterprise analytics assistant. 
Answer only using the approved semantic model.

If information is not available, respond:
"The requested information is not available in the approved semantic model."""


def load_generated_context(file_path: Path = None) -> str:
    """
    Load generated context from database or fallback to file.
    
    Args:
        file_path: Path to file fallback
    
    Returns:
        Generated context content
    """
    # Try database first
    content = get_prompt_from_db('generated_context')
    if content:
        return content
    
    # Fallback to file
    if file_path and file_path.exists():
        return file_path.read_text(encoding='utf-8')
    
    return "No semantic context available."


def load_prompt_by_name(name: str, fallback_content: str = None) -> str:
    """
    Load a prompt by name from database with fallback.
    
    Args:
        name: Name of the prompt
        fallback_content: Fallback content if not found
    
    Returns:
        Prompt content
    """
    # Try database first
    content = get_prompt_from_db(name)
    if content:
        return content
    
    # Use fallback
    return fallback_content or f"No prompt found with name: {name}"


def get_prompt_version(name: str) -> Optional[str]:
    """
    Get the version of a prompt.
    
    Args:
        name: Name of the prompt
    
    Returns:
        Version string or None
    """
    if not DB_AVAILABLE:
        return None
    
    try:
        db = SessionLocal()
        prompt = db.query(Prompt).filter(
            Prompt.name == name,
            Prompt.is_active == True
        ).first()
        db.close()
        
        return prompt.version if prompt else None
    except Exception as e:
        print(f"⚠️ Error getting prompt version: {e}")
        return None


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Prompt Loader Utility')
    parser.add_argument('--list', action='store_true', help='List all active prompts')
    parser.add_argument('--show', help='Show content of a specific prompt')
    parser.add_argument('--system', action='store_true', help='Show system prompt')
    parser.add_argument('--context', action='store_true', help='Show generated context')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('PROMPT LOADER')
    print('=' * 60)
    print(f"Database available: {DB_AVAILABLE}")
    print()
    
    if args.list:
        print('📋 Active Prompts:')
        print('-' * 60)
        prompts = get_all_active_prompts()
        if prompts:
            for p in prompts:
                status = "✅ Active"
                print(f"\n🔹 {p['name']} v{p['version']} ({status})")
                print(f"   Description: {p['description']}")
                print(f"   Content Preview: {p['content'][:100]}...")
        else:
            print("No active prompts found.")
    
    elif args.show:
        print(f'📄 Content of: {args.show}')
        print('-' * 60)
        content = get_prompt_from_db(args.show)
        if content:
            print(content)
        else:
            print(f"❌ Prompt '{args.show}' not found.")
    
    elif args.system:
        print('📄 System Prompt:')
        print('-' * 60)
        content = load_system_prompt()
        print(content)
    
    elif args.context:
        print('📄 Generated Context:')
        print('-' * 60)
        content = load_generated_context()
        print(content)
    
    else:
        print("💡 Available commands:")
        print("  --list        List all active prompts")
        print("  --show NAME   Show content of a specific prompt")
        print("  --system      Show system prompt")
        print("  --context     Show generated context")