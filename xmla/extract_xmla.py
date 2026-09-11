import json
from pathlib import Path
from datetime import datetime

# Optional dependency:
# pip install pyadomd
#
# This script demonstrates a production-style XMLA metadata extraction.
# In environments without XMLA access, it falls back to sample metadata.

OUTPUT_DIR = Path('metadata/raw')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_METADATA = {
    'dataset': 'Enterprise Sales Model',
    'extracted_at': datetime.utcnow().isoformat(),
    'tables': [
        {
            'name': 'Sales',
            'description': 'Sales fact table',
            'columns': [
                'DateKey',
                'RegionKey',
                'CountryKey',
                'Net Revenue Amount',
                'Units Sold',
            ],
            'measures': [
                'Net Revenue',
                'Gross Margin',
                'Growth %',
            ],
        },
        {
            'name': 'Calendar',
            'description': 'Date dimension',
            'columns': ['Date', 'Year', 'Quarter', 'Month'],
            'measures': [],
        },
    ],
    'relationships': [
        {
            'from_table': 'Sales',
            'from_column': 'DateKey',
            'to_table': 'Calendar',
            'to_column': 'Date',
        }
    ],
}

def save_json(name: str, data):
    path = OUTPUT_DIR / name
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'Wrote {path}')

def main():
    # Replace this block with real XMLA extraction when credentials are available.
    save_json('xmla_model.json', SAMPLE_METADATA)
    save_json('tables.json', SAMPLE_METADATA['tables'])
    save_json('relationships.json', SAMPLE_METADATA['relationships'])

    print('XMLA extraction completed (sample mode).')

if __name__ == '__main__':
    main()