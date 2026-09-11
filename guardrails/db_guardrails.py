"""
Guardrails Database Manager - Stores and retrieves guardrails from the database.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from streamlit_app.db import SessionLocal, Guardrail, engine


# ---------------------------------------------------------------------
# Default Guardrails (fallback if database is empty)
# ---------------------------------------------------------------------
DEFAULT_GUARDRAILS = [
    {
        'measure_name': 'Net Revenue',
        'mandatory_filters': 'Date, Organization',
        'description': 'Date and Organization filters are mandatory for Net Revenue',
        'is_active': True,
        'created_by': 'system'
    },
    {
        'measure_name': 'Gross Margin %',
        'mandatory_filters': 'Date, Organization',
        'description': 'Date and Organization filters are mandatory for Gross Margin %',
        'is_active': True,
        'created_by': 'system'
    },
    {
        'measure_name': 'Average Unit Price',
        'mandatory_filters': 'Date, Organization',
        'description': 'Date and Organization filters are mandatory for Average Unit Price',
        'is_active': True,
        'created_by': 'system'
    },
    {
        'measure_name': 'Inventory Value',
        'mandatory_filters': 'Date, Organization, Warehouse',
        'description': 'Date, Organization, and Warehouse filters are mandatory for Inventory Value',
        'is_active': True,
        'created_by': 'system'
    },
    {
        'measure_name': 'Return Rate',
        'mandatory_filters': 'Date, Organization',
        'description': 'Date and Organization filters are mandatory for Return Rate',
        'is_active': True,
        'created_by': 'system'
    },
    {
        'measure_name': 'Sales',
        'mandatory_filters': 'Date, Region',
        'description': 'Date and Region filters are mandatory for Sales',
        'is_active': True,
        'created_by': 'system'
    },
    {
        'measure_name': 'Orders',
        'mandatory_filters': 'Date, Status',
        'description': 'Date and Status filters are mandatory for Orders',
        'is_active': True,
        'created_by': 'system'
    },
    {
        'measure_name': 'Customer Count',
        'mandatory_filters': 'Date, Segment',
        'description': 'Date and Segment filters are mandatory for Customer Count',
        'is_active': True,
        'created_by': 'system'
    }
]


# ---------------------------------------------------------------------
# Guardrails Database Manager
# ---------------------------------------------------------------------
class GuardrailsDBManager:
    """
    Manages guardrails in the database.
    """
    
    def __init__(self):
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """Ensure the guardrails table exists."""
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS guardrails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        measure_name TEXT NOT NULL UNIQUE,
                        mandatory_filters TEXT,
                        description TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_by TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ Guardrails table verified/created")
        except Exception as e:
            print(f"⚠️ Error creating guardrails table: {e}")
    
    def get_all(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all guardrails from the database.
        
        Args:
            include_inactive: Whether to include inactive guardrails
        
        Returns:
            List of guardrail dictionaries
        """
        try:
            db = SessionLocal()
            query = db.query(Guardrail)
            if not include_inactive:
                query = query.filter(Guardrail.is_active == True)
            guardrails = query.all()
            db.close()
            
            return [
                {
                    'id': g.id,
                    'measure_name': g.measure_name,
                    'mandatory_filters': g.mandatory_filters,
                    'description': g.description,
                    'is_active': g.is_active,
                    'created_by': g.created_by,
                    'created_at': g.created_at.isoformat() if g.created_at else None,
                    'updated_at': g.updated_at.isoformat() if g.updated_at else None
                }
                for g in guardrails
            ]
        except Exception as e:
            print(f"⚠️ Error getting guardrails: {e}")
            return []
    
    def get_by_measure(self, measure_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a guardrail by measure name.
        
        Args:
            measure_name: Name of the measure
        
        Returns:
            Guardrail dictionary or None
        """
        try:
            db = SessionLocal()
            guardrail = db.query(Guardrail).filter(
                Guardrail.measure_name == measure_name
            ).first()
            db.close()
            
            if guardrail:
                return {
                    'id': guardrail.id,
                    'measure_name': guardrail.measure_name,
                    'mandatory_filters': guardrail.mandatory_filters,
                    'description': guardrail.description,
                    'is_active': guardrail.is_active,
                    'created_by': guardrail.created_by,
                    'created_at': guardrail.created_at.isoformat() if guardrail.created_at else None,
                    'updated_at': guardrail.updated_at.isoformat() if guardrail.updated_at else None
                }
            return None
        except Exception as e:
            print(f"⚠️ Error getting guardrail: {e}")
            return None
    
    def get_mandatory_filters(self, measure_name: str) -> List[str]:
        """
        Get mandatory filters for a measure.
        
        Args:
            measure_name: Name of the measure
        
        Returns:
            List of mandatory filter names
        """
        guardrail = self.get_by_measure(measure_name)
        if guardrail and guardrail.get('mandatory_filters'):
            filters = guardrail['mandatory_filters']
            if isinstance(filters, str):
                return [f.strip() for f in filters.split(',') if f.strip()]
            return filters
        return []
    
    def create(self, measure_name: str, mandatory_filters: str, 
               description: str = "", created_by: str = "system") -> Optional[Dict[str, Any]]:
        """
        Create a new guardrail.
        
        Args:
            measure_name: Name of the measure
            mandatory_filters: Comma-separated mandatory filters
            description: Description of the guardrail
            created_by: User who created the guardrail
        
        Returns:
            Created guardrail dictionary or None
        """
        try:
            db = SessionLocal()
            
            # Check if guardrail already exists
            existing = db.query(Guardrail).filter(
                Guardrail.measure_name == measure_name
            ).first()
            
            if existing:
                db.close()
                print(f"ℹ️ Guardrail for '{measure_name}' already exists")
                return None
            
            # Create new guardrail
            guardrail = Guardrail(
                measure_name=measure_name,
                mandatory_filters=mandatory_filters,
                description=description,
                is_active=True,
                created_by=created_by,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(guardrail)
            db.commit()
            db.refresh(guardrail)
            db.close()
            
            print(f"✅ Created guardrail for '{measure_name}'")
            
            return {
                'id': guardrail.id,
                'measure_name': guardrail.measure_name,
                'mandatory_filters': guardrail.mandatory_filters,
                'description': guardrail.description,
                'is_active': guardrail.is_active,
                'created_by': guardrail.created_by,
                'created_at': guardrail.created_at.isoformat() if guardrail.created_at else None,
                'updated_at': guardrail.updated_at.isoformat() if guardrail.updated_at else None
            }
        except Exception as e:
            print(f"❌ Error creating guardrail: {e}")
            return None
    
    def update(self, measure_name: str, mandatory_filters: str = None,
               description: str = None, is_active: bool = None) -> bool:
        """
        Update a guardrail.
        
        Args:
            measure_name: Name of the measure
            mandatory_filters: Updated mandatory filters
            description: Updated description
            is_active: Updated active status
        
        Returns:
            bool: True if successful
        """
        try:
            db = SessionLocal()
            guardrail = db.query(Guardrail).filter(
                Guardrail.measure_name == measure_name
            ).first()
            
            if not guardrail:
                db.close()
                print(f"❌ Guardrail for '{measure_name}' not found")
                return False
            
            if mandatory_filters is not None:
                guardrail.mandatory_filters = mandatory_filters
            if description is not None:
                guardrail.description = description
            if is_active is not None:
                guardrail.is_active = is_active
            
            guardrail.updated_at = datetime.now()
            db.commit()
            db.close()
            
            print(f"✅ Updated guardrail for '{measure_name}'")
            return True
        except Exception as e:
            print(f"❌ Error updating guardrail: {e}")
            return False
    
    def delete(self, measure_name: str, permanent: bool = False) -> bool:
        """
        Delete a guardrail.
        
        Args:
            measure_name: Name of the measure
            permanent: If True, permanently delete; if False, soft delete
        
        Returns:
            bool: True if successful
        """
        if permanent:
            try:
                db = SessionLocal()
                guardrail = db.query(Guardrail).filter(
                    Guardrail.measure_name == measure_name
                ).first()
                
                if not guardrail:
                    db.close()
                    return False
                
                db.delete(guardrail)
                db.commit()
                db.close()
                print(f"🗑️ Permanently deleted guardrail for '{measure_name}'")
                return True
            except Exception as e:
                print(f"❌ Error deleting guardrail: {e}")
                return False
        else:
            return self.update(measure_name, is_active=False)
    
    def init_defaults(self, force: bool = False) -> Dict[str, Any]:
        """
        Initialize default guardrails if none exist.
        
        Args:
            force: Force re-initialization even if guardrails exist
        
        Returns:
            Dict with initialization results
        """
        results = {'created': 0, 'skipped': 0, 'errors': [], 'updated': 0}
        
        existing = self.get_all(include_inactive=True)
        
        if existing and not force:
            print(f"ℹ️ Guardrails already exist ({len(existing)} found). Use --force to re-initialize.")
            results['skipped'] = len(existing)
            return results
        
        if existing and force:
            print(f"🔄 Force re-initializing guardrails (clearing existing)...")
            # Clear existing
            for g in existing:
                self.delete(g['measure_name'], permanent=True)
        
        print("📝 Initializing default guardrails...")
        
        for default in DEFAULT_GUARDRAILS:
            try:
                result = self.create(
                    measure_name=default['measure_name'],
                    mandatory_filters=default['mandatory_filters'],
                    description=default['description'],
                    created_by=default.get('created_by', 'system')
                )
                if result:
                    results['created'] += 1
                    print(f"  ✅ Created: {default['measure_name']}")
                else:
                    results['skipped'] += 1
            except Exception as e:
                results['errors'].append(f"{default['measure_name']}: {str(e)}")
                print(f"  ❌ Failed: {default['measure_name']}")
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about guardrails.
        
        Returns:
            Dict with statistics
        """
        try:
            db = SessionLocal()
            total = db.query(Guardrail).count()
            active = db.query(Guardrail).filter(Guardrail.is_active == True).count()
            inactive = total - active
            
            # Get by category/measure
            measures = db.query(Guardrail.measure_name).filter(
                Guardrail.is_active == True
            ).all()
            
            db.close()
            
            return {
                'total': total,
                'active': active,
                'inactive': inactive,
                'measures': [m[0] for m in measures]
            }
        except Exception as e:
            print(f"⚠️ Error getting statistics: {e}")
            return {'total': 0, 'active': 0, 'inactive': 0, 'measures': []}
    
    def get_all_measures_with_filters(self) -> Dict[str, List[str]]:
        """
        Get all measures with their mandatory filters.
        
        Returns:
            Dict mapping measure names to list of mandatory filters
        """
        guardrails = self.get_all()
        result = {}
        for g in guardrails:
            filters = g.get('mandatory_filters', '')
            if isinstance(filters, str):
                result[g['measure_name']] = [f.strip() for f in filters.split(',') if f.strip()]
            else:
                result[g['measure_name']] = filters or []
        return result
    
    def export_to_json(self) -> List[Dict[str, Any]]:
        """
        Export all guardrails to JSON format.
        
        Returns:
            List of guardrail dictionaries
        """
        return self.get_all(include_inactive=True)
    
    def import_from_json(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Import guardrails from JSON data.
        
        Args:
            data: List of guardrail dictionaries
        
        Returns:
            Dict with import results
        """
        results = {'created': 0, 'updated': 0, 'errors': []}
        
        for item in data:
            try:
                measure_name = item.get('measure_name')
                if not measure_name:
                    continue
                
                existing = self.get_by_measure(measure_name)
                if existing:
                    # Update
                    self.update(
                        measure_name=measure_name,
                        mandatory_filters=item.get('mandatory_filters', ''),
                        description=item.get('description', ''),
                        is_active=item.get('is_active', True)
                    )
                    results['updated'] += 1
                else:
                    # Create
                    self.create(
                        measure_name=measure_name,
                        mandatory_filters=item.get('mandatory_filters', ''),
                        description=item.get('description', ''),
                        created_by=item.get('created_by', 'system')
                    )
                    results['created'] += 1
            except Exception as e:
                results['errors'].append(str(e))
        
        return results


# ---------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------
_db_manager = GuardrailsDBManager()


# ---------------------------------------------------------------------
# Public API Functions
# ---------------------------------------------------------------------
def get_guardrails(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Get all guardrails."""
    return _db_manager.get_all(include_inactive)


def get_guardrail(measure_name: str) -> Optional[Dict[str, Any]]:
    """Get a guardrail by measure name."""
    return _db_manager.get_by_measure(measure_name)


def get_mandatory_filters(measure_name: str) -> List[str]:
    """Get mandatory filters for a measure."""
    return _db_manager.get_mandatory_filters(measure_name)


def create_guardrail(measure_name: str, mandatory_filters: str,
                     description: str = "", created_by: str = "system") -> Optional[Dict[str, Any]]:
    """Create a new guardrail."""
    return _db_manager.create(measure_name, mandatory_filters, description, created_by)


def update_guardrail(measure_name: str, mandatory_filters: str = None,
                     description: str = None, is_active: bool = None) -> bool:
    """Update a guardrail."""
    return _db_manager.update(measure_name, mandatory_filters, description, is_active)


def delete_guardrail(measure_name: str, permanent: bool = False) -> bool:
    """Delete a guardrail."""
    return _db_manager.delete(measure_name, permanent)


def init_guardrails(force: bool = False) -> Dict[str, Any]:
    """Initialize default guardrails."""
    return _db_manager.init_defaults(force)


def get_guardrail_statistics() -> Dict[str, Any]:
    """Get guardrail statistics."""
    return _db_manager.get_statistics()


def get_all_measures_with_filters() -> Dict[str, List[str]]:
    """Get all measures with their mandatory filters."""
    return _db_manager.get_all_measures_with_filters()


def export_guardrails() -> List[Dict[str, Any]]:
    """Export all guardrails to JSON format."""
    return _db_manager.export_to_json()


def import_guardrails(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Import guardrails from JSON data."""
    return _db_manager.import_from_json(data)


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Manage guardrails in database')
    parser.add_argument('--init', action='store_true', help='Initialize default guardrails')
    parser.add_argument('--force', action='store_true', help='Force re-initialization')
    parser.add_argument('--list', action='store_true', help='List all guardrails')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--measure', help='Get guardrail for specific measure')
    parser.add_argument('--filters', help='Get mandatory filters for a measure')
    parser.add_argument('--create', action='store_true', help='Create a new guardrail')
    parser.add_argument('--name', help='Measure name for create/update')
    parser.add_argument('--filters-list', help='Mandatory filters (comma-separated)')
    parser.add_argument('--desc', help='Description')
    parser.add_argument('--delete', help='Delete a guardrail')
    parser.add_argument('--permanent', action='store_true', help='Permanently delete')
    parser.add_argument('--export', help='Export guardrails to JSON file')
    parser.add_argument('--import', dest='import_file', help='Import guardrails from JSON file')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('GUARDRAILS DATABASE MANAGER')
    print('=' * 60)
    
    if args.init:
        print('\n📝 Initializing default guardrails...')
        results = init_guardrails(force=args.force)
        print(f"\n✅ Created: {results['created']}")
        print(f"⏭️ Skipped: {results['skipped']}")
        if results.get('updated'):
            print(f"🔄 Updated: {results['updated']}")
        if results['errors']:
            print(f"❌ Errors: {results['errors']}")
    
    elif args.export:
        print(f'\n📤 Exporting guardrails to: {args.export}')
        data = export_guardrails()
        with open(args.export, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Exported {len(data)} guardrails")
    
    elif args.import_file:
        print(f'\n📥 Importing guardrails from: {args.import_file}')
        with open(args.import_file, 'r') as f:
            data = json.load(f)
        results = import_guardrails(data)
        print(f"✅ Created: {results['created']}")
        print(f"🔄 Updated: {results['updated']}")
        if results['errors']:
            print(f"❌ Errors: {results['errors']}")
    
    elif args.delete:
        print(f'\n🗑️ Deleting guardrail: {args.delete}')
        result = delete_guardrail(args.delete, permanent=args.permanent)
        if result:
            print(f"✅ Deleted guardrail for '{args.delete}'")
        else:
            print(f"❌ Failed to delete guardrail for '{args.delete}'")
    
    elif args.list:
        print('\n📋 Guardrails:')
        print('-' * 60)
        guardrails = get_guardrails(include_inactive=True)
        if not guardrails:
            print("No guardrails found. Run --init to create default guardrails.")
        else:
            for g in guardrails:
                status = "✅ Active" if g['is_active'] else "❌ Inactive"
                print(f"\n🔹 {g['measure_name']} ({status})")
                print(f"   Filters: {g['mandatory_filters']}")
                print(f"   Description: {g['description'] or 'N/A'}")
                print(f"   Created: {g['created_at']}")
    
    elif args.stats:
        print('\n📊 Statistics:')
        print('-' * 60)
        stats = get_guardrail_statistics()
        print(f"Total: {stats.get('total', 0)}")
        print(f"Active: {stats.get('active', 0)}")
        print(f"Inactive: {stats.get('inactive', 0)}")
        if stats.get('measures'):
            print(f"\nMeasures ({len(stats['measures'])}):")
            for m in stats['measures']:
                print(f"  - {m}")
    
    elif args.measure:
        print(f'\n🔍 Guardrail for: {args.measure}')
        print('-' * 60)
        g = get_guardrail(args.measure)
        if g:
            print(f"Measure: {g['measure_name']}")
            print(f"Filters: {g['mandatory_filters']}")
            print(f"Description: {g['description'] or 'N/A'}")
            print(f"Active: {g['is_active']}")
            print(f"Created By: {g['created_by']}")
            print(f"Created At: {g['created_at']}")
            print(f"Updated At: {g['updated_at']}")
        else:
            print("❌ Guardrail not found")
    
    elif args.filters:
        filters = get_mandatory_filters(args.filters)
        print(f'\n🔍 Mandatory filters for {args.filters}:')
        print('-' * 60)
        if filters:
            for f in filters:
                print(f"  - {f}")
        else:
            print("  No mandatory filters defined")
    
    elif args.create:
        if not args.name:
            print("❌ --name is required for --create")
        else:
            print(f'\n➕ Creating guardrail: {args.name}')
            result = create_guardrail(
                measure_name=args.name,
                mandatory_filters=args.filters_list or '',
                description=args.desc or '',
                created_by='cli'
            )
            if result:
                print(f"✅ Created guardrail for {args.name}")
                print(f"   Filters: {result['mandatory_filters']}")
                print(f"   Description: {result['description'] or 'N/A'}")
            else:
                print(f"❌ Failed to create guardrail (might already exist)")
    
    else:
        print("\n💡 Available commands:")
        print("  --init              Initialize default guardrails")
        print("  --force             Force re-initialization")
        print("  --list              List all guardrails")
        print("  --stats             Show statistics")
        print("  --measure NAME      Get guardrail for specific measure")
        print("  --filters NAME      Get mandatory filters for a measure")
        print("  --create            Create a new guardrail")
        print("  --delete NAME       Delete a guardrail")
        print("  --permanent         Permanently delete (with --delete)")
        print("  --name NAME         Measure name")
        print("  --filters-list      Mandatory filters (comma-separated)")
        print("  --desc TEXT         Description")
        print("  --export FILE       Export guardrails to JSON file")
        print("  --import FILE       Import guardrails from JSON file")