"""
Load metadata from YAML/JSON files into the database.
This script populates metadata_tables and metadata_columns tables.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import yaml
from sqlalchemy import text
from streamlit_app.db import engine, SessionLocal, MetadataTable, MetadataColumn


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
METADATA_DIR = ROOT_DIR / 'metadata'
CURATED_DIR = METADATA_DIR / 'curated'
RAW_DIR = METADATA_DIR / 'raw'


# ---------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------
def load_yaml_file(file_path: Path) -> Dict:
    """Load a YAML file."""
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}

def load_json_file(file_path: Path) -> Dict:
    """Load a JSON file."""
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------
# Metadata Loader
# ---------------------------------------------------------------------
class MetadataLoader:
    """
    Loads metadata from files into the database.
    """
    
    def __init__(self):
        self.tables_loaded = 0
        self.columns_loaded = 0
        self.errors = []
    
    def load_tables_from_yaml(self) -> int:
        """
        Load tables from curated/tables.yaml.
        
        Returns:
            Number of tables loaded
        """
        tables_file = CURATED_DIR / 'tables.yaml'
        if not tables_file.exists():
            print(f"⚠️ File not found: {tables_file}")
            return 0
        
        data = load_yaml_file(tables_file)
        tables = data.get('tables', [])
        
        if not tables:
            print("⚠️ No tables found in curated/tables.yaml")
            return 0
        
        loaded = 0
        
        try:
            db = SessionLocal()
            
            for table_data in tables:
                table_name = table_data.get('name')
                if not table_name:
                    print("⚠️ Table without name, skipping...")
                    continue
                
                # Check if table already exists
                existing = db.query(MetadataTable).filter(
                    MetadataTable.name == table_name
                ).first()
                
                if existing:
                    # Update existing
                    existing.business_name = table_data.get('business_name', table_name)
                    existing.description = table_data.get('description', '')
                    existing.table_type = table_data.get('table_type', '')
                    existing.schema_name = table_data.get('schema', 'dbo')
                    existing.owner = table_data.get('owner', '')
                    existing.is_certified = table_data.get('certified', False)
                    existing.row_count_estimate = table_data.get('row_count_estimate')
                    existing.refresh_frequency = table_data.get('refresh_frequency', '')
                    existing.updated_at = datetime.now()
                    print(f"  🔄 Updated table: {table_name}")
                else:
                    # Create new
                    table = MetadataTable(
                        name=table_name,
                        business_name=table_data.get('business_name', table_name),
                        description=table_data.get('description', ''),
                        table_type=table_data.get('table_type', ''),
                        schema_name=table_data.get('schema', 'dbo'),
                        owner=table_data.get('owner', ''),
                        is_certified=table_data.get('certified', False),
                        row_count_estimate=table_data.get('row_count_estimate'),
                        refresh_frequency=table_data.get('refresh_frequency', ''),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    db.add(table)
                    db.flush()
                    print(f"  ✅ Created table: {table_name}")
                
                # Load columns for this table
                columns = table_data.get('columns', [])
                if columns:
                    col_count = self._load_columns(db, table_name, columns)
                    print(f"     📋 Loaded {col_count} columns for {table_name}")
                else:
                    print(f"     ⚠️ No columns defined for {table_name}")
                
                loaded += 1
            
            db.commit()
            db.close()
            
            self.tables_loaded = loaded
            print(f"\n✅ Loaded/Updated {loaded} tables")
            return loaded
            
        except Exception as e:
            print(f"❌ Error loading tables: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def _load_columns(self, db, table_name: str, columns: List) -> int:
        """
        Load columns for a table.
        
        Args:
            db: Database session
            table_name: Name of the table
            columns: List of column definitions (can be strings or dicts)
        
        Returns:
            Number of columns loaded
        """
        # Get table ID
        table = db.query(MetadataTable).filter(
            MetadataTable.name == table_name
        ).first()
        
        if not table:
            print(f"⚠️ Table '{table_name}' not found in database")
            return 0
        
        loaded = 0
        
        for col_data in columns:
            # Handle both dict and string formats
            if isinstance(col_data, str):
                col_name = col_data
                col_desc = ''
                col_type = ''
                is_pk = False
                is_fk = False
                ref_table = None
                ref_col = None
                nullable = True
            else:
                col_name = col_data.get('name', '')
                col_desc = col_data.get('description', '')
                col_type = col_data.get('data_type', col_data.get('type', ''))
                is_pk = col_data.get('is_primary_key', False)
                is_fk = col_data.get('is_foreign_key', False)
                ref_table = col_data.get('references_table', col_data.get('references'))
                ref_col = col_data.get('references_column', col_data.get('references_column'))
                nullable = col_data.get('nullable', True)
            
            if not col_name:
                continue
            
            # Check if column already exists
            existing = db.query(MetadataColumn).filter(
                MetadataColumn.table_id == table.id,
                MetadataColumn.name == col_name
            ).first()
            
            if existing:
                # Update existing
                existing.business_name = col_data.get('business_name', col_name) if isinstance(col_data, dict) else col_name
                existing.description = col_desc
                existing.data_type = col_type
                existing.is_primary_key = is_pk
                existing.is_foreign_key = is_fk
                existing.references_table = ref_table
                existing.references_column = ref_col
                existing.nullable = nullable
            else:
                # Create new
                column = MetadataColumn(
                    table_id=table.id,
                    name=col_name,
                    business_name=col_data.get('business_name', col_name) if isinstance(col_data, dict) else col_name,
                    description=col_desc,
                    data_type=col_type,
                    is_primary_key=is_pk,
                    is_foreign_key=is_fk,
                    references_table=ref_table,
                    references_column=ref_col,
                    nullable=nullable,
                    created_at=datetime.now()
                )
                db.add(column)
            
            loaded += 1
        
        self.columns_loaded += loaded
        return loaded
    
    def load_tables_from_raw_json(self) -> int:
        """
        Load tables from raw/tables.json as fallback.
        
        Returns:
            Number of tables loaded
        """
        tables_file = RAW_DIR / 'tables.json'
        if not tables_file.exists():
            return 0
        
        tables = load_json_file(tables_file)
        
        if not tables:
            return 0
        
        loaded = 0
        
        try:
            db = SessionLocal()
            
            for table_data in tables:
                table_name = table_data.get('name')
                if not table_name:
                    continue
                
                # Check if table already exists
                existing = db.query(MetadataTable).filter(
                    MetadataTable.name == table_name
                ).first()
                
                if existing:
                    continue
                
                table = MetadataTable(
                    name=table_name,
                    business_name=table_data.get('business_name', table_name),
                    description=table_data.get('description', ''),
                    table_type=table_data.get('type', ''),
                    schema_name=table_data.get('schema', 'dbo'),
                    owner=table_data.get('owner', ''),
                    is_certified=table_data.get('certified', False),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(table)
                loaded += 1
            
            db.commit()
            db.close()
            
            print(f"✅ Loaded {loaded} tables from raw JSON")
            return loaded
            
        except Exception as e:
            print(f"❌ Error loading raw tables: {e}")
            return 0
    
    def load_from_semantic_model_json(self) -> int:
        """
        Load tables from curated/semantic_model.json.
        
        Returns:
            Number of tables loaded
        """
        model_file = CURATED_DIR / 'semantic_model.json'
        if not model_file.exists():
            return 0
        
        data = load_json_file(model_file)
        
        tables = data.get('tables', [])
        if not tables:
            return 0
        
        loaded = 0
        
        try:
            db = SessionLocal()
            
            for table_name in tables:
                # Check if table already exists
                existing = db.query(MetadataTable).filter(
                    MetadataTable.name == table_name
                ).first()
                
                if existing:
                    continue
                
                table = MetadataTable(
                    name=table_name,
                    business_name=table_name,
                    description=data.get('description', f'{table_name} table'),
                    table_type='Dimension',
                    schema_name='dbo',
                    is_certified=False,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(table)
                loaded += 1
            
            db.commit()
            db.close()
            
            print(f"✅ Loaded {loaded} tables from semantic_model.json")
            return loaded
            
        except Exception as e:
            print(f"❌ Error loading from semantic_model.json: {e}")
            return 0
    
    def load_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Load all metadata from files into the database.
        
        Args:
            force: Force reload even if tables exist
        
        Returns:
            Dict with results
        """
        results = {
            'tables_loaded': 0,
            'columns_loaded': 0,
            'errors': []
        }
        
        print("📂 Loading metadata into database...")
        print("=" * 60)
        
        # Check if tables already exist
        if not force:
            try:
                db = SessionLocal()
                count = db.query(MetadataTable).count()
                db.close()
                if count > 0:
                    print(f"ℹ️ Database already has {count} tables. Use --force to reload.")
                    return results
            except Exception:
                pass
        
        # Load from curated/tables.yaml
        print("\n📋 Loading from curated/tables.yaml...")
        tables_loaded = self.load_tables_from_yaml()
        results['tables_loaded'] += tables_loaded
        
        # If no tables loaded, try raw/tables.json
        if tables_loaded == 0:
            print("\n📋 Loading from raw/tables.json...")
            tables_loaded = self.load_tables_from_raw_json()
            results['tables_loaded'] += tables_loaded
        
        # If still no tables, try semantic_model.json
        if tables_loaded == 0:
            print("\n📋 Loading from semantic_model.json...")
            tables_loaded = self.load_from_semantic_model_json()
            results['tables_loaded'] += tables_loaded
        
        results['columns_loaded'] = self.columns_loaded
        
        print("\n" + "=" * 60)
        print(f"✅ Loaded {results['tables_loaded']} tables")
        print(f"✅ Loaded {results['columns_loaded']} columns")
        
        if self.errors:
            print(f"\n⚠️ Errors: {len(self.errors)}")
            for err in self.errors:
                print(f"   - {err}")
        
        return results
    
    def verify_database(self) -> Dict[str, Any]:
        """
        Verify metadata in the database.
        
        Returns:
            Dict with verification results
        """
        try:
            db = SessionLocal()
            
            tables = db.query(MetadataTable).all()
            columns = db.query(MetadataColumn).all()
            
            # Get column count per table
            table_col_counts = {}
            for table in tables:
                count = db.query(MetadataColumn).filter(
                    MetadataColumn.table_id == table.id
                ).count()
                table_col_counts[table.name] = count
            
            db.close()
            
            return {
                'tables_count': len(tables),
                'columns_count': len(columns),
                'tables': [{'name': t.name, 'columns': table_col_counts.get(t.name, 0)} for t in tables],
                'total_columns': columns
            }
        except Exception as e:
            return {'error': str(e)}


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Load metadata into database')
    parser.add_argument('--load', action='store_true', help='Load metadata from files')
    parser.add_argument('--force', action='store_true', help='Force reload')
    parser.add_argument('--verify', action='store_true', help='Verify database')
    parser.add_argument('--clear', action='store_true', help='Clear metadata from database')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('METADATA LOADER')
    print('=' * 60)
    
    loader = MetadataLoader()
    
    if args.clear:
        print('\n🗑️ Clearing metadata from database...')
        try:
            db = SessionLocal()
            col_count = db.query(MetadataColumn).delete()
            table_count = db.query(MetadataTable).delete()
            db.commit()
            db.close()
            print(f'✅ Cleared {table_count} tables and {col_count} columns from database')
        except Exception as e:
            print(f'❌ Error clearing metadata: {e}')
    
    elif args.verify:
        print('\n📊 Verification:')
        print('-' * 60)
        result = loader.verify_database()
        if 'error' in result:
            print(f'❌ Error: {result["error"]}')
        else:
            print(f"📊 Tables: {result.get('tables_count', 0)}")
            print(f"📊 Columns: {result.get('columns_count', 0)}")
            print("\n📋 Tables:")
            for table in result.get('tables', []):
                print(f"  - {table['name']}: {table['columns']} columns")
    
    elif args.load:
        loader.load_all(force=args.force)
    
    else:
        print("\n💡 Available commands:")
        print("  --load        Load metadata from files into database")
        print("  --force       Force reload even if data exists")
        print("  --verify      Verify metadata in database")
        print("  --clear       Clear metadata from database")
        print("  --verbose     Show detailed output")