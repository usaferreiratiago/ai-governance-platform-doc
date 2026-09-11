"""
Glossary Builder - Loads glossary terms from YAML and saves them to the database.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import yaml
import json
from typing import Dict, List, Any, Optional

# Import database modules
try:
    from streamlit_app.db import SessionLocal, GlossaryTerm, engine
    from sqlalchemy import text
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ Database module not available")
    DB_AVAILABLE = False


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
GLOSSARY_DIR = ROOT_DIR / 'metadata' / 'glossary'
GLOSSARY_FILE = GLOSSARY_DIR / 'business_glossary.yaml'


# ---------------------------------------------------------------------
# Default Glossary Data
# ---------------------------------------------------------------------
DEFAULT_GLOSSARY = {
    'version': '1.0.0',
    'domain': 'Retail & E-commerce',
    'terms': [
        {
            'business_term': 'Net Revenue',
            'description': 'Revenue after discounts, returns, and allowances',
            'synonyms': ['revenue', 'sales', 'turnover', 'net sales'],
            'category': 'Financial',
            'table_name': 'sales',
            'field_name': 'net_revenue',
            'is_certified': True
        },
        {
            'business_term': 'Gross Margin %',
            'description': 'Gross profit divided by net revenue, expressed as a percentage',
            'synonyms': ['margin', 'gross margin', 'profitability', 'gross profit %'],
            'category': 'Financial',
            'table_name': 'sales',
            'field_name': 'gross_margin_percent',
            'is_certified': True
        },
        {
            'business_term': 'Average Unit Price',
            'description': 'Average selling price per unit sold',
            'synonyms': ['unit price', 'average price', 'average receipt', 'avg price per unit'],
            'category': 'Commercial',
            'table_name': 'sales',
            'field_name': 'avg_unit_price',
            'is_certified': True
        },
        {
            'business_term': 'Inventory Value',
            'description': 'Monetary value of inventory on hand, calculated at standard cost',
            'synonyms': ['stock value', 'inventory', 'stock', 'inventory amount'],
            'category': 'Inventory',
            'table_name': 'product',
            'field_name': 'inventory_value',
            'is_certified': True
        },
        {
            'business_term': 'Return Rate',
            'description': 'Percentage of sold units that were returned by customers',
            'synonyms': ['returns', 'refund rate', 'return percentage', 'return ratio'],
            'category': 'Operational',
            'table_name': 'sales',
            'field_name': 'return_rate',
            'is_certified': True
        },
        {
            'business_term': 'Sales Total',
            'description': 'Total gross sales revenue before discounts and returns',
            'synonyms': ['gross sales', 'total sales', 'gross revenue'],
            'category': 'Commercial',
            'table_name': 'sales',
            'field_name': 'sales_total',
            'is_certified': True
        },
        {
            'business_term': 'Customer Count',
            'description': 'Total number of active customers',
            'synonyms': ['customers', 'active customers', 'customer base', 'client count'],
            'category': 'CRM',
            'table_name': 'customers',
            'field_name': 'customer_count',
            'is_certified': True
        },
        {
            'business_term': 'Order Count',
            'description': 'Total number of orders placed',
            'synonyms': ['orders', 'order volume', 'order total'],
            'category': 'Operational',
            'table_name': 'orders',
            'field_name': 'order_count',
            'is_certified': True
        },
        {
            'business_term': 'Average Order Value',
            'description': 'Average value of orders placed',
            'synonyms': ['AOV', 'order value', 'average basket', 'avg order amount'],
            'category': 'Commercial',
            'table_name': 'orders',
            'field_name': 'avg_order_value',
            'is_certified': True
        },
        {
            'business_term': 'Customer Lifetime Value',
            'description': 'Total predicted revenue from a customer over their lifetime',
            'synonyms': ['CLV', 'lifetime value', 'customer value', 'LTV'],
            'category': 'CRM',
            'table_name': 'customers',
            'field_name': 'lifetime_value',
            'is_certified': False
        }
    ]
}


# ---------------------------------------------------------------------
# Glossary Builder Class
# ---------------------------------------------------------------------
class GlossaryBuilder:
    """
    Builds and manages glossary terms in the database.
    """
    
    def __init__(self):
        self.glossary_file = GLOSSARY_FILE
        self.glossary_dir = GLOSSARY_DIR
        self.glossary_dir.mkdir(parents=True, exist_ok=True)
    
    def load_glossary_yaml(self) -> Dict[str, Any]:
        """
        Load glossary from YAML file.
        
        Returns:
            Dict with glossary data
        """
        if self.glossary_file.exists():
            try:
                with open(self.glossary_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"⚠️ Error loading glossary YAML: {e}")
                return {}
        return {}
    
    def save_glossary_yaml(self, data: Dict[str, Any]) -> bool:
        """
        Save glossary to YAML file.
        
        Args:
            data: Glossary data to save
        
        Returns:
            bool: True if successful
        """
        try:
            with open(self.glossary_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, indent=2)
            print(f"✅ Glossary saved to: {self.glossary_file}")
            return True
        except Exception as e:
            print(f"❌ Error saving glossary YAML: {e}")
            return False
    
    def save_to_database(self, glossary_data: Dict[str, Any], created_by: str = 'system') -> Dict[str, Any]:
        """
        Save glossary terms to the database.
        
        Args:
            glossary_data: Glossary data from YAML
            created_by: User who created the terms
        
        Returns:
            Dict with results
        """
        if not DB_AVAILABLE:
            print("❌ Database not available")
            return {'success': False, 'error': 'Database not available'}
        
        results = {
            'success': 0,
            'failed': 0,
            'errors': [],
            'terms': []
        }
        
        try:
            db = SessionLocal()
            
            # Get terms from data
            terms = glossary_data.get('terms', [])
            if not terms:
                print("⚠️ No terms found in glossary data")
                db.close()
                return results
            
            for term_data in terms:
                try:
                    # Check if term already exists
                    existing = db.query(GlossaryTerm).filter(
                        GlossaryTerm.business_term == term_data.get('business_term')
                    ).first()
                    
                    # Prepare synonyms as comma-separated string
                    synonyms = term_data.get('synonyms', [])
                    if isinstance(synonyms, list):
                        synonyms_str = ', '.join(synonyms)
                    else:
                        synonyms_str = str(synonyms) if synonyms else ''
                    
                    if existing:
                        # Update existing term
                        existing.description = term_data.get('description', '')
                        existing.synonyms = synonyms_str
                        existing.category = term_data.get('category', '')
                        existing.table_name = term_data.get('table_name', '')
                        existing.field_name = term_data.get('field_name', '')
                        existing.is_certified = term_data.get('is_certified', False)
                        existing.updated_at = datetime.now()
                        
                        results['terms'].append({
                            'business_term': term_data.get('business_term'),
                            'action': 'updated'
                        })
                        print(f"🔄 Updated term: {term_data.get('business_term')}")
                    else:
                        # Create new term
                        new_term = GlossaryTerm(
                            business_term=term_data.get('business_term'),
                            description=term_data.get('description', ''),
                            synonyms=synonyms_str,
                            category=term_data.get('category', ''),
                            table_name=term_data.get('table_name', ''),
                            field_name=term_data.get('field_name', ''),
                            is_certified=term_data.get('is_certified', False),
                            created_by=created_by,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        db.add(new_term)
                        
                        results['terms'].append({
                            'business_term': term_data.get('business_term'),
                            'action': 'created'
                        })
                        print(f"✅ Created term: {term_data.get('business_term')}")
                    
                    results['success'] += 1
                    
                except Exception as e:
                    results['failed'] += 1
                    error_msg = f"Error with term '{term_data.get('business_term')}': {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"❌ {error_msg}")
            
            db.commit()
            db.close()
            
            print(f"\n📊 Summary:")
            print(f"   ✅ Success: {results['success']} terms")
            print(f"   ❌ Failed: {results['failed']} terms")
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            results['errors'].append(str(e))
        
        return results
    
    def build_glossary(self, created_by: str = 'system') -> Dict[str, Any]:
        """
        Main method to build glossary from default data or YAML file.
        
        Args:
            created_by: User who created the terms
        
        Returns:
            Dict with results
        """
        print("📚 Building Business Glossary...")
        print("=" * 60)
        
        # Try to load from YAML file first
        yaml_data = self.load_glossary_yaml()
        
        if yaml_data and yaml_data.get('terms'):
            print(f"📂 Loading glossary from YAML file: {self.glossary_file}")
            glossary_data = yaml_data
        else:
            print("📝 Using default glossary data")
            glossary_data = DEFAULT_GLOSSARY
            
            # Save default to YAML for future use
            self.save_glossary_yaml(glossary_data)
        
        # Save to database
        print(f"\n💾 Saving to database (table: glossary_terms)...")
        results = self.save_to_database(glossary_data, created_by)
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 Glossary Build Complete!")
        print(f"✅ Successfully processed: {results['success']} terms")
        
        if results['errors']:
            print(f"⚠️ Errors encountered: {len(results['errors'])}")
            for error in results['errors']:
                print(f"   - {error}")
        
        return results
    
    def export_to_yaml(self) -> bool:
        """
        Export database glossary to YAML file.
        
        Returns:
            bool: True if successful
        """
        if not DB_AVAILABLE:
            print("❌ Database not available")
            return False
        
        try:
            db = SessionLocal()
            terms = db.query(GlossaryTerm).all()
            db.close()
            
            if not terms:
                print("⚠️ No terms found in database")
                return False
            
            export_data = {
                'version': '1.0.0',
                'domain': 'Retail & E-commerce',
                'terms': []
            }
            
            for term in terms:
                export_data['terms'].append({
                    'business_term': term.business_term,
                    'description': term.description or '',
                    'synonyms': [s.strip() for s in (term.synonyms or '').split(',') if s.strip()],
                    'category': term.category or '',
                    'table_name': term.table_name or '',
                    'field_name': term.field_name or '',
                    'is_certified': term.is_certified or False
                })
            
            self.save_glossary_yaml(export_data)
            print(f"✅ Exported {len(terms)} terms to YAML")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting to YAML: {e}")
            return False
    
    def clear_database(self) -> bool:
        """
        Clear all glossary terms from the database.
        
        Returns:
            bool: True if successful
        """
        if not DB_AVAILABLE:
            print("❌ Database not available")
            return False
        
        try:
            db = SessionLocal()
            deleted = db.query(GlossaryTerm).delete()
            db.commit()
            db.close()
            print(f"🗑️ Deleted {deleted} terms from database")
            return True
        except Exception as e:
            print(f"❌ Error clearing database: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about glossary terms.
        
        Returns:
            Dict with statistics
        """
        if not DB_AVAILABLE:
            return {'total': 0, 'certified': 0, 'categories': {}}
        
        try:
            db = SessionLocal()
            total = db.query(GlossaryTerm).count()
            certified = db.query(GlossaryTerm).filter(GlossaryTerm.is_certified == True).count()
            
            # Count by category
            categories = db.execute(
                text("SELECT category, COUNT(*) FROM glossary_terms GROUP BY category")
            ).fetchall()
            
            db.close()
            
            return {
                'total': total,
                'certified': certified,
                'uncertified': total - certified,
                'categories': {cat[0]: cat[1] for cat in categories if cat[0]}
            }
        except Exception as e:
            print(f"⚠️ Error getting stats: {e}")
            return {'total': 0, 'certified': 0, 'categories': {}}


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build and manage glossary terms')
    parser.add_argument('--build', action='store_true', help='Build glossary from default data')
    parser.add_argument('--export', action='store_true', help='Export database to YAML')
    parser.add_argument('--clear', action='store_true', help='Clear all terms from database')
    parser.add_argument('--stats', action='store_true', help='Show glossary statistics')
    parser.add_argument('--user', default='system', help='User who created the terms')
    
    args = parser.parse_args()
    
    builder = GlossaryBuilder()
    
    if args.clear:
        builder.clear_database()
    elif args.export:
        builder.export_to_yaml()
    elif args.stats:
        stats = builder.get_stats()
        print("\n📊 Glossary Statistics:")
        print("=" * 40)
        print(f"Total Terms: {stats.get('total', 0)}")
        print(f"Certified: {stats.get('certified', 0)}")
        print(f"Uncertified: {stats.get('uncertified', 0)}")
        print("\nBy Category:")
        for category, count in stats.get('categories', {}).items():
            print(f"  - {category}: {count}")
    else:
        # Default: build glossary
        builder.build_glossary(created_by=args.user)
        print("\n💡 To see statistics, run: python glossary_builder.py --stats")


if __name__ == '__main__':
    main()