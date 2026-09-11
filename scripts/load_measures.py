"""
Load measures from YAML into the database.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import yaml
from streamlit_app.db import SessionLocal, SemanticModel
import json
from datetime import datetime

def load_measures():
    """Load measures from YAML into the database."""
    measures_file = ROOT_DIR / 'metadata' / 'curated' / 'measures.yaml'
    
    if not measures_file.exists():
        print(f"❌ Measures file not found: {measures_file}")
        return
    
    with open(measures_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        measures = data.get('measures', [])
    
    print(f'📊 Loaded {len(measures)} measures')
    
    db = SessionLocal()
    loaded = 0
    updated = 0
    
    for measure in measures:
        # Generate a clean ID
        name_clean = measure.get('name', '').lower()
        name_clean = name_clean.replace(' ', '_').replace('%', 'pct').replace('__', '')
        model_id = f"sm-{name_clean}"
        
        # Check if exists
        existing = db.query(SemanticModel).filter(SemanticModel.id == model_id).first()
        
        content = {
            'name': measure.get('name'),
            'dax': measure.get('dax'),
            'table': measure.get('table'),
            'business_description': measure.get('business_description'),
            'usage_guidance': measure.get('usage_guidance'),
            'certified': measure.get('certified', False),
            'owner': measure.get('owner'),
            'mandatory_filters': measure.get('mandatory_filters', []),
            'is_hidden': measure.get('is_hidden', False)
        }
        
        if existing:
            existing.content = json.dumps(content)
            existing.updated_at = datetime.now()
            print(f'  🔄 Updated: {measure.get("name")}')
            updated += 1
        else:
            new_model = SemanticModel(
                id=model_id,
                name=f"Measure: {measure.get('name')}",
                description=measure.get('business_description', ''),
                content=json.dumps(content),
                version='1.0.0',
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_model)
            print(f'  ✅ Created: {measure.get("name")}')
            loaded += 1
    
    db.commit()
    db.close()
    
    print(f'\n✅ Measures loaded successfully!')
    print(f'   Created: {loaded}')
    print(f'   Updated: {updated}')

if __name__ == '__main__':
    load_measures()
