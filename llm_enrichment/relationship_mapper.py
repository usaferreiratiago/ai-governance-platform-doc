"""
Relationship Mapper - Loads relationships from JSON and stores them in the database.
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from streamlit_app.db import engine, SessionLocal, Relationship


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
INPUT_FILE = ROOT_DIR / 'metadata' / 'raw' / 'relationships.json'
OUTPUT_FILE = ROOT_DIR / 'metadata' / 'lineage' / 'entity_relationships.json'


# ---------------------------------------------------------------------
# Relationship Mapper
# ---------------------------------------------------------------------
class RelationshipMapper:
    """
    Maps relationships from JSON to the database.
    """
    
    def __init__(self):
        self.loaded = 0
        self.errors = []
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """Ensure the relationships table exists."""
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS relationships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        from_table TEXT NOT NULL,
                        from_column TEXT NOT NULL,
                        to_table TEXT NOT NULL,
                        to_column TEXT NOT NULL,
                        cardinality TEXT,
                        relationship_type TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        description TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ Relationships table verified/created")
        except Exception as e:
            print(f"⚠️ Error creating relationships table: {e}")
    
    def load_relationships_from_json(self) -> List[Dict[str, Any]]:
        """
        Load relationships from JSON file.
        
        Returns:
            List of relationship dictionaries
        """
        if not INPUT_FILE.exists():
            print(f"⚠️ File not found: {INPUT_FILE}")
            return self._get_default_relationships()
        
        try:
            with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'relationships' in data:
                    return data['relationships']
                else:
                    return data
        except Exception as e:
            print(f"⚠️ Error loading relationships: {e}")
            return self._get_default_relationships()
    
    def _get_default_relationships(self) -> List[Dict[str, Any]]:
        """Return default relationships for testing."""
        return [
            {
                'from_table': 'Sales',
                'from_column': 'ProductKey',
                'to_table': 'Product',
                'to_column': 'ProductKey',
                'cardinality': 'ManyToOne',
                'relationship_type': 'Dimension',
                'description': 'Sales to Product dimension'
            },
            {
                'from_table': 'Sales',
                'from_column': 'CustomerKey',
                'to_table': 'Customer',
                'to_column': 'CustomerKey',
                'cardinality': 'ManyToOne',
                'relationship_type': 'Dimension',
                'description': 'Sales to Customer dimension'
            },
            {
                'from_table': 'Sales',
                'from_column': 'DateKey',
                'to_table': 'Date',
                'to_column': 'DateKey',
                'cardinality': 'ManyToOne',
                'relationship_type': 'Dimension',
                'description': 'Sales to Date dimension'
            },
            {
                'from_table': 'Sales',
                'from_column': 'RegionKey',
                'to_table': 'Region',
                'to_column': 'RegionKey',
                'cardinality': 'ManyToOne',
                'relationship_type': 'Dimension',
                'description': 'Sales to Region dimension'
            }
        ]
    
    def save_to_database(self, relationships: List[Dict[str, Any]]) -> int:
        """
        Save relationships to the database.
        
        Args:
            relationships: List of relationship dictionaries
        
        Returns:
            Number of relationships saved
        """
        saved = 0
        
        try:
            db = SessionLocal()
            
            for rel in relationships:
                # Extract fields with defaults
                from_table = rel.get('from_table', '')
                from_column = rel.get('from_column', '')
                to_table = rel.get('to_table', '')
                to_column = rel.get('to_column', '')
                
                if not all([from_table, from_column, to_table, to_column]):
                    print(f"⚠️ Skipping incomplete relationship: {rel}")
                    continue
                
                # Check if relationship already exists
                existing = db.query(Relationship).filter(
                    Relationship.from_table == from_table,
                    Relationship.from_column == from_column,
                    Relationship.to_table == to_table,
                    Relationship.to_column == to_column
                ).first()
                
                if existing:
                    # Update existing
                    existing.cardinality = rel.get('cardinality', 'Unknown')
                    existing.relationship_type = rel.get('relationship_type', '')
                    existing.is_active = rel.get('is_active', True)
                    existing.description = rel.get('description', '')
                    existing.updated_at = datetime.now()
                else:
                    # Create new
                    relationship = Relationship(
                        from_table=from_table,
                        from_column=from_column,
                        to_table=to_table,
                        to_column=to_column,
                        cardinality=rel.get('cardinality', 'Unknown'),
                        relationship_type=rel.get('relationship_type', 'Dimension'),
                        is_active=rel.get('is_active', True),
                        description=rel.get('description', ''),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    db.add(relationship)
                
                saved += 1
            
            db.commit()
            db.close()
            
            print(f"✅ Saved {saved} relationships to database")
            return saved
            
        except Exception as e:
            print(f"❌ Error saving relationships: {e}")
            return 0
    
    def build_graph(self, relationships: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        Build a relationship graph from relationships.
        
        Args:
            relationships: List of relationship dictionaries
        
        Returns:
            Graph dictionary with source tables as keys
        """
        graph = {}
        
        for rel in relationships:
            source = rel.get('from_table')
            target = rel.get('to_table')
            
            if not source or not target:
                continue
            
            graph.setdefault(source, []).append({
                'target_table': target,
                'source_column': rel.get('from_column', ''),
                'target_column': rel.get('to_column', ''),
                'cardinality': rel.get('cardinality', 'Unknown'),
                'relationship_type': rel.get('relationship_type', '')
            })
        
        return graph
    
    def save_graph_to_file(self, graph: Dict[str, List[Dict]]) -> None:
        """
        Save the relationship graph to a JSON file.
        
        Args:
            graph: Relationship graph dictionary
        """
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Relationship graph written to {OUTPUT_FILE}")
    
    def get_relationships_from_db(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get relationships from the database.
        
        Args:
            active_only: Only return active relationships
        
        Returns:
            List of relationship dictionaries
        """
        try:
            db = SessionLocal()
            query = db.query(Relationship)
            
            if active_only:
                query = query.filter(Relationship.is_active == True)
            
            relationships = query.all()
            db.close()
            
            return [
                {
                    'id': r.id,
                    'from_table': r.from_table,
                    'from_column': r.from_column,
                    'to_table': r.to_table,
                    'to_column': r.to_column,
                    'cardinality': r.cardinality,
                    'relationship_type': r.relationship_type,
                    'is_active': r.is_active,
                    'description': r.description,
                    'created_at': r.created_at.isoformat() if r.created_at else None,
                    'updated_at': r.updated_at.isoformat() if r.updated_at else None
                }
                for r in relationships
            ]
        except Exception as e:
            print(f"⚠️ Error getting relationships from database: {e}")
            return []
    
    def run(self, save_to_db: bool = True) -> Dict[str, Any]:
        """
        Main execution method.
        
        Args:
            save_to_db: Whether to save relationships to database
        
        Returns:
            Dict with results
        """
        results = {
            'relationships_loaded': 0,
            'relationships_saved': 0,
            'graph_nodes': 0,
            'errors': []
        }
        
        print("📂 Loading relationships...")
        print("=" * 60)
        
        # Load relationships from JSON
        relationships = self.load_relationships_from_json()
        results['relationships_loaded'] = len(relationships)
        
        if not relationships:
            print("⚠️ No relationships found")
            return results
        
        print(f"✅ Loaded {len(relationships)} relationships")
        
        # Save to database
        if save_to_db:
            print("\n💾 Saving to database...")
            saved = self.save_to_database(relationships)
            results['relationships_saved'] = saved
        
        # Build graph
        print("\n📊 Building relationship graph...")
        graph = self.build_graph(relationships)
        results['graph_nodes'] = len(graph)
        
        # Save graph to file
        self.save_graph_to_file(graph)
        
        # Print graph summary
        print(f"\n📊 Graph Summary:")
        print(f"   Total Nodes: {len(graph)}")
        print(f"   Total Relationships: {len(relationships)}")
        
        for source, targets in list(graph.items())[:5]:
            print(f"   - {source}: {len(targets)} relationships")
            for target in targets[:3]:
                print(f"      → {target['target_table']} ({target['cardinality']})")
        
        if len(graph) > 5:
            print(f"   ... and {len(graph) - 5} more nodes")
        
        results['graph_nodes'] = len(graph)
        
        print("\n✅ Relationship mapping completed!")
        
        return results
    
    def verify_database(self) -> Dict[str, Any]:
        """
        Verify relationships in the database.
        
        Returns:
            Dict with verification results
        """
        try:
            db = SessionLocal()
            total = db.query(Relationship).count()
            active = db.query(Relationship).filter(Relationship.is_active == True).count()
            
            # Get relationship types
            types = db.execute(
                text("""
                    SELECT relationship_type, COUNT(*) as count
                    FROM relationships
                    GROUP BY relationship_type
                """)
            ).fetchall()
            
            # Get cardinalities
            cardinalities = db.execute(
                text("""
                    SELECT cardinality, COUNT(*) as count
                    FROM relationships
                    GROUP BY cardinality
                """)
            ).fetchall()
            
            db.close()
            
            return {
                'total': total,
                'active': active,
                'inactive': total - active,
                'relationship_types': [{'type': t[0], 'count': t[1]} for t in types],
                'cardinalities': [{'cardinality': c[0], 'count': c[1]} for c in cardinalities]
            }
        except Exception as e:
            return {'error': str(e)}


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Relationship Mapper')
    parser.add_argument('--load', action='store_true', help='Load relationships from JSON to database')
    parser.add_argument('--verify', action='store_true', help='Verify relationships in database')
    parser.add_argument('--clear', action='store_true', help='Clear relationships from database')
    parser.add_argument('--no-db', action='store_true', help='Skip saving to database')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('RELATIONSHIP MAPPER')
    print('=' * 60)
    
    mapper = RelationshipMapper()
    
    if args.clear:
        print('\n🗑️ Clearing relationships from database...')
        try:
            db = SessionLocal()
            count = db.query(Relationship).delete()
            db.commit()
            db.close()
            print(f'✅ Cleared {count} relationships from database')
        except Exception as e:
            print(f'❌ Error clearing relationships: {e}')
    
    elif args.verify:
        print('\n📊 Verification:')
        print('-' * 60)
        result = mapper.verify_database()
        if 'error' in result:
            print(f'❌ Error: {result["error"]}')
        else:
            print(f"Total Relationships: {result.get('total', 0)}")
            print(f"Active: {result.get('active', 0)}")
            print(f"Inactive: {result.get('inactive', 0)}")
            
            if result.get('relationship_types'):
                print("\n📋 Relationship Types:")
                for t in result['relationship_types']:
                    print(f"  - {t['type']}: {t['count']}")
            
            if result.get('cardinalities'):
                print("\n📋 Cardinalities:")
                for c in result['cardinalities']:
                    print(f"  - {c['cardinality']}: {c['count']}")
    
    elif args.load:
        mapper.run(save_to_db=not args.no_db)
    
    else:
        print("\n💡 Available commands:")
        print("  --load        Load relationships from JSON to database")
        print("  --no-db       Load relationships but don't save to database")
        print("  --verify      Verify relationships in database")
        print("  --clear       Clear relationships from database")