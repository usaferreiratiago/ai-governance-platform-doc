from pathlib import Path
import json
import yaml

BASE_DIR = Path(__file__).resolve().parent


def load_glossary_yaml():
    path = BASE_DIR / 'business_glossary.yaml'
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_glossary_json():
    path = BASE_DIR / 'business_glossary.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)