"""
Load semantic model data from files into the database.
This script populates the semantic_models table with baseline model data.
"""
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from streamlit_app.db import engine, SessionLocal, SemanticModel


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
SEMANTIC_MODEL_DIR = ROOT_DIR / 'semantic-model'
BASELINE_MODEL_FILE = SEMANTIC_MODEL_DIR / 'baseline-model.json'
MEASURES_FILE = SEMANTIC_MODEL_DIR / 'measures.csv'
TABLES_FILE = SEMANTIC_MODEL_DIR / 'tables.csv'
BACKUPS_DIR = SEMANTIC_MODEL_DIR / 'backups'


# ---------------------------------------------------------------------
# Semantic Model Loader
# ---------------------------------------------------------------------
class SemanticModelLoader:
    """
    Loads semantic model data from files into the database.
    """
    
    def __init__(self):
        self.loaded = 0
        self.errors = []
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """Ensure the semantic_models table exists."""
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS semantic_models (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        content TEXT,
                        version TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_by TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ semantic_models table verified/created")
        except Exception as e:
            print(f"⚠️ Error creating semantic_models table: {e}")
    
    def load_baseline_model(self) -> Optional[Dict[str, Any]]:
        """
        Load baseline model from JSON file.
        
        Returns:
            Baseline model dictionary or None
        """
        if not BASELINE_MODEL_FILE.exists():
            self.errors.append(f"File not found: {BASELINE_MODEL_FILE}")
            return None
        
        try:
            with open(BASELINE_MODEL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.errors.append(f"Error loading baseline model: {e}")
            return None
    
    def load_measures_from_csv(self) -> List[Dict[str, Any]]:
        """
        Load measures from CSV file.
        
        Returns:
            List of measure dictionaries
        """
        if not MEASURES_FILE.exists():
            self.errors.append(f"File not found: {MEASURES_FILE}")
            return []
        
        try:
            measures = []
            with open(MEASURES_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    measures.append(row)
            return measures
        except Exception as e:
            self.errors.append(f"Error loading measures: {e}")
            return []
    
    def load_tables_from_csv(self) -> List[Dict[str, Any]]:
        """
        Load tables from CSV file.
        
        Returns:
            List of table dictionaries
        """
        if not TABLES_FILE.exists():
            self.errors.append(f"File not found: {TABLES_FILE}")
            return []
        
        try:
            tables = []
            with open(TABLES_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tables.append(row)
            return tables
        except Exception as e:
            self.errors.append(f"Error loading tables: {e}")
            return []
    
    def build_model_content(
        self,
        baseline: Optional[Dict],
        measures: List[Dict],
        tables: List[Dict]
    ) -> Dict[str, Any]:
        """
        Build the complete model content.
        
        Args:
            baseline: Baseline model data
            measures: List of measures
            tables: List of tables
        
        Returns:
            Complete model content dictionary
        """
        content = {
            "model": baseline or {},
            "measures": measures,
            "tables": tables,
            "loaded_at": datetime.now().isoformat()
        }
        
        # Add metadata if available
        if baseline:
            content["version"] = baseline.get("version", "1.0.0")
            content["model_name"] = baseline.get("model_name", "Retail Semantic Model")
            content["description"] = baseline.get("description", "")
        
        return content
    
    def save_to_database(
        self,
        content: Dict[str, Any],
        model_id: Optional[str] = None,
        name: str = "Retail Semantic Model",
        description: str = "",
        version: str = "1.0.0",
        created_by: str = "system",
        is_active: bool = True
    ) -> Optional[str]:
        """
        Save semantic model to the database.
        
        Args:
            content: Model content dictionary
            model_id: Optional model ID (generated if not provided)
            name: Model name
            description: Model description
            version: Model version
            created_by: User who created the model
            is_active: Whether the model is active
        
        Returns:
            Model ID if successful, None otherwise
        """
        try:
            # Generate ID if not provided
            if not model_id:
                model_id = f"sm-{uuid.uuid4().hex[:8]}"
            
            db = SessionLocal()
            
            # Check if model already exists
            existing = db.query(SemanticModel).filter(
                SemanticModel.id == model_id
            ).first()
            
            # Convert content to JSON string
            content_json = json.dumps(content, indent=2, default=str)
            
            if existing:
                # Update existing
                existing.name = name
                existing.description = description
                existing.content = content_json
                existing.version = version
                existing.is_active = is_active
                existing.updated_at = datetime.now()
                print(f"  🔄 Updated semantic model: {name} (ID: {model_id})")
            else:
                # Create new
                model = SemanticModel(
                    id=model_id,
                    name=name,
                    description=description,
                    content=content_json,
                    version=version,
                    is_active=is_active,
                    created_by=created_by,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(model)
                print(f"  ✅ Created semantic model: {name} (ID: {model_id})")
            
            db.commit()
            db.close()
            
            self.loaded += 1
            return model_id
            
        except Exception as e:
            self.errors.append(f"Error saving semantic model: {e}")
            return None
    
    def load_all(
        self,
        created_by: str = "system",
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Load all semantic model data into the database.
        
        Args:
            created_by: User who created the data
            force: Force reload even if data exists
        
        Returns:
            Dict with results
        """
        results = {
            'loaded': 0,
            'measures_count': 0,
            'tables_count': 0,
            'errors': []
        }
        
        print("📂 Loading semantic model into database...")
        print("=" * 60)
        
        # Check if models already exist
        if not force:
            try:
                db = SessionLocal()
                count = db.query(SemanticModel).count()
                db.close()
                if count > 0:
                    print(f"ℹ️ Database already has {count} semantic models. Use --force to reload.")
                    return results
            except Exception:
                pass
        
        # Load baseline model
        print("\n📋 Loading baseline model...")
        baseline = self.load_baseline_model()
        if baseline:
            print(f"  ✅ Loaded baseline model: {baseline.get('model_name', 'Unknown')}")
        
        # Load measures
        print("\n📋 Loading measures from CSV...")
        measures = self.load_measures_from_csv()
        results['measures_count'] = len(measures)
        print(f"  ✅ Loaded {len(measures)} measures")
        
        # Load tables
        print("\n📋 Loading tables from CSV...")
        tables = self.load_tables_from_csv()
        results['tables_count'] = len(tables)
        print(f"  ✅ Loaded {len(tables)} tables")
        
        # Build content
        content = self.build_model_content(baseline, measures, tables)
        
        # Extract metadata
        name = baseline.get("model_name", "Retail Semantic Model") if baseline else "Retail Semantic Model"
        description = baseline.get("description", "") if baseline else ""
        version = baseline.get("version", "1.0.0") if baseline else "1.0.0"
        
        # Save to database
        print("\n💾 Saving to database...")
        model_id = self.save_to_database(
            content=content,
            name=name,
            description=description,
            version=version,
            created_by=created_by
        )
        
        if model_id:
            results['loaded'] = 1
            results['model_id'] = model_id
            print(f"\n✅ Saved semantic model: {name} (ID: {model_id})")
        else:
            results['errors'] = self.errors
        
        # Save a backup
        self._save_backup(content)
        
        print("\n" + "=" * 60)
        print(f"✅ Loaded {results['loaded']} semantic model")
        print(f"📊 {results['measures_count']} measures")
        print(f"📊 {results['tables_count']} tables")
        
        if self.errors:
            print(f"\n⚠️ Errors: {len(self.errors)}")
            for err in self.errors:
                print(f"   - {err}")
        
        return results
    
    def _save_backup(self, content: Dict[str, Any]) -> None:
        """Save a backup of the model content."""
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        backup_file = BACKUPS_DIR / f"model_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, default=str)
            print(f"💾 Backup saved to: {backup_file}")
        except Exception as e:
            print(f"⚠️ Error saving backup: {e}")
    
    def verify_database(self) -> Dict[str, Any]:
        """
        Verify semantic models in the database.
        
        Returns:
            Dict with verification results
        """
        try:
            db = SessionLocal()
            models = db.query(SemanticModel).all()
            
            # Count active models
            active = db.query(SemanticModel).filter(
                SemanticModel.is_active == True
            ).count()
            
            # Get model versions
            versions = db.execute(
                text("""
                    SELECT version, COUNT(*) as count
                    FROM semantic_models
                    GROUP BY version
                """)
            ).fetchall()
            
            db.close()
            
            return {
                'total': len(models),
                'active': active,
                'inactive': len(models) - active,
                'models': [
                    {
                        'id': m.id,
                        'name': m.name,
                        'version': m.version,
                        'is_active': m.is_active,
                        'created_at': m.created_at.isoformat() if m.created_at else None,
                        'description': m.description[:100] if m.description else ''
                    }
                    for m in models
                ],
                'versions': [{'version': v[0], 'count': v[1]} for v in versions]
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_active_model(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently active semantic model.
        
        Returns:
            Active model dictionary or None
        """
        try:
            db = SessionLocal()
            model = db.query(SemanticModel).filter(
                SemanticModel.is_active == True
            ).order_by(
                SemanticModel.created_at.desc()
            ).first()
            db.close()
            
            if model:
                content = json.loads(model.content) if model.content else {}
                return {
                    'id': model.id,
                    'name': model.name,
                    'description': model.description,
                    'content': content,
                    'version': model.version,
                    'is_active': model.is_active,
                    'created_by': model.created_by,
                    'created_at': model.created_at.isoformat() if model.created_at else None,
                    'updated_at': model.updated_at.isoformat() if model.updated_at else None
                }
            return None
        except Exception as e:
            print(f"⚠️ Error getting active model: {e}")
            return None


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Load semantic model into database')
    parser.add_argument('--load', action='store_true', help='Load semantic model from files')
    parser.add_argument('--force', action='store_true', help='Force reload')
    parser.add_argument('--verify', action='store_true', help='Verify database')
    parser.add_argument('--clear', action='store_true', help='Clear semantic models from database')
    parser.add_argument('--active', action='store_true', help='Show active semantic model')
    parser.add_argument('--user', default='system', help='User who created the data')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('SEMANTIC MODEL LOADER')
    print('=' * 60)
    
    loader = SemanticModelLoader()
    
    if args.clear:
        print('\n🗑️ Clearing semantic models from database...')
        try:
            db = SessionLocal()
            count = db.query(SemanticModel).delete()
            db.commit()
            db.close()
            print(f'✅ Cleared {count} semantic models from database')
        except Exception as e:
            print(f'❌ Error clearing semantic models: {e}')
    
    elif args.verify:
        print('\n📊 Verification:')
        print('-' * 60)
        result = loader.verify_database()
        if 'error' in result:
            print(f'❌ Error: {result["error"]}')
        else:
            print(f"Total Models: {result.get('total', 0)}")
            print(f"Active: {result.get('active', 0)}")
            print(f"Inactive: {result.get('inactive', 0)}")
            
            print("\n📋 Models:")
            for m in result.get('models', []):
                status = "✅ Active" if m['is_active'] else "❌ Inactive"
                print(f"  - {m['name']} v{m['version']} ({status})")
                print(f"    ID: {m['id']}")
                print(f"    Description: {m['description'][:80]}...")
            
            if result.get('versions'):
                print("\n📊 Versions:")
                for v in result['versions']:
                    print(f"  - {v['version']}: {v['count']} models")
    
    elif args.active:
        print('\n📋 Active Semantic Model:')
        print('-' * 60)
        model = loader.get_active_model()
        if model:
            print(f"ID: {model['id']}")
            print(f"Name: {model['name']}")
            print(f"Version: {model['version']}")
            print(f"Description: {model['description']}")
            print(f"Created At: {model['created_at']}")
            if model.get('content'):
                content = model['content']
                print(f"Tables: {len(content.get('tables', []))}")
                print(f"Measures: {len(content.get('measures', []))}")
        else:
            print("❌ No active semantic model found")
    
    elif args.load:
        loader.load_all(created_by=args.user, force=args.force)
    
    else:
        print("\n💡 Available commands:")
        print("  --load        Load semantic model from files into database")
        print("  --force       Force reload even if data exists")
        print("  --verify      Verify semantic models in database")
        print("  --clear       Clear semantic models from database")
        print("  --active      Show active semantic model")
        print("  --user NAME   User who created the data (default: system)")