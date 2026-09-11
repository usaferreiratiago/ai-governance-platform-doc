"""
Load prompts from markdown files into the database.
This script populates the prompts table with system prompts and generated contexts.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path (go up 2 levels since we're in prompts/)
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from streamlit_app.db import engine, SessionLocal, Prompt


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
PROMPTS_DIR = ROOT_DIR / 'prompts'
SYSTEM_PROMPT_FILE = PROMPTS_DIR / 'system_prompt_v1.md'
GENERATED_CONTEXT_FILE = PROMPTS_DIR / 'generated_context.md'


# ---------------------------------------------------------------------
# Prompt Loader
# ---------------------------------------------------------------------
class PromptLoader:
    """
    Loads prompts from markdown files into the database.
    """
    
    def __init__(self):
        self.loaded = 0
        self.errors = []
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """Ensure the prompts table exists."""
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS prompts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        content TEXT NOT NULL,
                        description TEXT,
                        version TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_by TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ Prompts table verified/created")
        except Exception as e:
            print(f"⚠️ Error creating prompts table: {e}")
    
    def load_system_prompt(self) -> bool:
        """
        Load system prompt from file into database.
        
        Returns:
            bool: True if successful
        """
        if not SYSTEM_PROMPT_FILE.exists():
            self.errors.append(f"File not found: {SYSTEM_PROMPT_FILE}")
            return False
        
        try:
            content = SYSTEM_PROMPT_FILE.read_text(encoding='utf-8')
            
            # Extract metadata from the markdown
            version = "1.0.0"
            description = "Official enterprise analytics assistant system prompt"
            name = "system_prompt_v1"
            
            # Try to extract version from markdown
            for line in content.split('\n'):
                if 'Version:' in line:
                    version = line.split('Version:')[-1].strip()
                    break
            
            db = SessionLocal()
            
            # Check if prompt already exists
            existing = db.query(Prompt).filter(Prompt.name == name).first()
            
            if existing:
                # Update existing
                existing.content = content
                existing.version = version
                existing.description = description
                existing.updated_at = datetime.now()
                existing.is_active = True
                print(f"  🔄 Updated prompt: {name}")
            else:
                # Create new
                prompt = Prompt(
                    name=name,
                    content=content,
                    description=description,
                    version=version,
                    is_active=True,
                    created_by='system',
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(prompt)
                print(f"  ✅ Created prompt: {name}")
            
            db.commit()
            db.close()
            self.loaded += 1
            return True
            
        except Exception as e:
            self.errors.append(f"Error loading system prompt: {e}")
            return False
    
    def load_generated_context(self) -> bool:
        """
        Load generated context from file into database.
        
        Returns:
            bool: True if successful
        """
        if not GENERATED_CONTEXT_FILE.exists():
            self.errors.append(f"File not found: {GENERATED_CONTEXT_FILE}")
            return False
        
        try:
            content = GENERATED_CONTEXT_FILE.read_text(encoding='utf-8')
            
            # Parse metadata
            name = "generated_context"
            description = "Approved semantic model context for LLM"
            version = "1.0.0"
            
            # Try to extract info from content
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'Version:' in line:
                    version = line.split('Version:')[-1].strip()
                if 'Business Domain' in line and i+1 < len(lines):
                    description = lines[i+1].strip() if lines[i+1].strip() else description
            
            db = SessionLocal()
            
            # Check if prompt already exists
            existing = db.query(Prompt).filter(Prompt.name == name).first()
            
            if existing:
                # Update existing
                existing.content = content
                existing.version = version
                existing.description = description
                existing.updated_at = datetime.now()
                existing.is_active = True
                print(f"  🔄 Updated prompt: {name}")
            else:
                # Create new
                prompt = Prompt(
                    name=name,
                    content=content,
                    description=description,
                    version=version,
                    is_active=True,
                    created_by='system',
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(prompt)
                print(f"  ✅ Created prompt: {name}")
            
            db.commit()
            db.close()
            self.loaded += 1
            return True
            
        except Exception as e:
            self.errors.append(f"Error loading generated context: {e}")
            return False
    
    def load_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Load all prompts into the database.
        
        Args:
            force: Force reload even if prompts exist
        
        Returns:
            Dict with results
        """
        results = {
            'loaded': 0,
            'errors': []
        }
        
        print("📂 Loading prompts into database...")
        print("=" * 60)
        
        # Check if prompts already exist
        if not force:
            try:
                db = SessionLocal()
                count = db.query(Prompt).count()
                db.close()
                if count > 0:
                    print(f"ℹ️ Database already has {count} prompts. Use --force to reload.")
                    return results
            except Exception:
                pass
        
        # Load system prompt
        print("\n📋 Loading system prompt...")
        if self.load_system_prompt():
            results['loaded'] += 1
        
        # Load generated context
        print("\n📋 Loading generated context...")
        if self.load_generated_context():
            results['loaded'] += 1
        
        results['errors'] = self.errors
        
        print("\n" + "=" * 60)
        print(f"✅ Loaded {results['loaded']} prompts")
        
        if self.errors:
            print(f"\n⚠️ Errors: {len(self.errors)}")
            for err in self.errors:
                print(f"   - {err}")
        
        return results
    
    def verify_database(self) -> Dict[str, Any]:
        """
        Verify prompts in the database.
        
        Returns:
            Dict with verification results
        """
        try:
            db = SessionLocal()
            prompts = db.query(Prompt).all()
            db.close()
            
            return {
                'count': len(prompts),
                'prompts': [
                    {
                        'name': p.name,
                        'version': p.version,
                        'is_active': p.is_active,
                        'description': p.description,
                        'created_at': p.created_at.isoformat() if p.created_at else None
                    }
                    for p in prompts
                ]
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_active_prompt(self, name: str = None) -> Optional[Dict[str, Any]]:
        """
        Get an active prompt by name.
        
        Args:
            name: Name of the prompt (if None, returns the first active prompt)
        
        Returns:
            Dict with prompt data or None
        """
        try:
            db = SessionLocal()
            query = db.query(Prompt).filter(Prompt.is_active == True)
            
            if name:
                query = query.filter(Prompt.name == name)
            
            prompt = query.first()
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
            print(f"⚠️ Error getting active prompt: {e}")
            return None


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Load prompts into database')
    parser.add_argument('--load', action='store_true', help='Load prompts from files')
    parser.add_argument('--force', action='store_true', help='Force reload')
    parser.add_argument('--verify', action='store_true', help='Verify database')
    parser.add_argument('--clear', action='store_true', help='Clear prompts from database')
    parser.add_argument('--show', help='Show content of a specific prompt')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('PROMPT LOADER')
    print('=' * 60)
    
    loader = PromptLoader()
    
    if args.clear:
        print('\n🗑️ Clearing prompts from database...')
        try:
            db = SessionLocal()
            count = db.query(Prompt).delete()
            db.commit()
            db.close()
            print(f'✅ Cleared {count} prompts from database')
        except Exception as e:
            print(f'❌ Error clearing prompts: {e}')
    
    elif args.verify:
        print('\n📊 Verification:')
        print('-' * 60)
        result = loader.verify_database()
        if 'error' in result:
            print(f'❌ Error: {result["error"]}')
        else:
            print(f"📊 Total Prompts: {result.get('count', 0)}")
            print("\n📋 Prompts:")
            for p in result.get('prompts', []):
                status = "✅ Active" if p['is_active'] else "❌ Inactive"
                print(f"  - {p['name']} v{p['version']} ({status})")
                print(f"    Description: {p['description']}")
    
    elif args.show:
        print(f'\n📄 Content of prompt: {args.show}')
        print('-' * 60)
        prompt = loader.get_active_prompt(args.show)
        if prompt:
            print(prompt['content'])
        else:
            print(f"❌ Prompt '{args.show}' not found or inactive")
    
    elif args.load:
        loader.load_all(force=args.force)
    
    else:
        print("\n💡 Available commands:")
        print("  --load        Load prompts from files into database")
        print("  --force       Force reload even if data exists")
        print("  --verify      Verify prompts in database")
        print("  --clear       Clear prompts from database")
        print("  --show NAME   Show content of a specific prompt")