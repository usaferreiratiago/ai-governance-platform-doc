import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
GLOSSARY_DIR = ROOT_DIR / 'metadata' / 'gloassary'
GLOSSARY_FILE = GLOSSARY_DIR / 'business_glossary.json'


# ---------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------
@dataclass
class GlossaryTerm:
    """Represents a glossary term."""
    business_term: str
    synonyms: List[str] = field(default_factory=list)
    related_measures: List[str] = field(default_factory=list)
    description: Optional[str] = None
    category: Optional[str] = None
    table: Optional[str] = None
    field: Optional[str] = None
    
    @property
    def name(self) -> str:
        """Alias for business_term."""
        return self.business_term
    
    @property
    def aliases(self) -> List[str]:
        """Alias for synonyms."""
        return self.synonyms


@dataclass
class Glossary:
    """Collection of glossary terms."""
    version: str = "1.0.0"
    domain: str = "Retail & E-commerce"
    terms: Dict[str, GlossaryTerm] = field(default_factory=dict)
    
    def get_term(self, name: str) -> Optional[GlossaryTerm]:
        """Gets a term by name."""
        return self.terms.get(name)
    
    def find_term(self, text: str) -> List[GlossaryTerm]:
        """Finds terms that match the text (by name or synonyms)."""
        text_lower = text.lower()
        found = []
        
        for term in self.terms.values():
            if term.business_term.lower() in text_lower:
                found.append(term)
            else:
                for synonym in term.synonyms:
                    if synonym.lower() in text_lower:
                        found.append(term)
                        break
        
        return found
    
    def get_context(self) -> str:
        """Returns the glossary context as a string."""
        lines = []
        lines.append(f"Domain: {self.domain}")
        lines.append(f"Version: {self.version}")
        lines.append("")
        lines.append("Business Terms:")
        
        for term in self.terms.values():
            lines.append(f"\n- {term.business_term}")
            if term.synonyms:
                lines.append(f"  Synonyms: {', '.join(term.synonyms)}")
            if term.related_measures:
                lines.append(f"  Related Measures: {', '.join(term.related_measures)}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts the glossary to a dictionary."""
        return {
            "version": self.version,
            "domain": self.domain,
            "terms": [
                {
                    "business_term": term.business_term,
                    "synonyms": term.synonyms,
                    "related_measures": term.related_measures
                }
                for term in self.terms.values()
            ]
        }


# ---------------------------------------------------------------------
# Glossary Loader
# ---------------------------------------------------------------------
class GlossaryLoader:
    """Loads and manages the glossary."""
    
    def __init__(self, file_path: Path = GLOSSARY_FILE):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._glossary = None
    
    def load(self) -> Glossary:
        """Loads the glossary from the JSON file."""
        if self._glossary is None:
            try:
                if not self.file_path.exists():
                    print(f"⚠️ Glossary file not found: {self.file_path}")
                    self._glossary = self._create_default_glossary()
                else:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    terms = {}
                    for term_data in data.get('terms', []):
                        term = GlossaryTerm(
                            business_term=term_data.get('business_term', ''),
                            synonyms=term_data.get('synonyms', []),
                            related_measures=term_data.get('related_measures', [])
                        )
                        terms[term.business_term] = term
                    
                    self._glossary = Glossary(
                        version=data.get('version', '1.0.0'),
                        domain=data.get('domain', 'Retail & E-commerce'),
                        terms=terms
                    )
            except Exception as e:
                print(f"⚠️ Error loading glossary: {e}")
                self._glossary = self._create_default_glossary()
        
        return self._glossary
    
    def _create_default_glossary(self) -> Glossary:
        """Creates the default glossary in memory."""
        terms = {
            "Net Revenue": GlossaryTerm(
                business_term="Net Revenue",
                synonyms=["revenue", "sales", "turnover"],
                related_measures=["Net Revenue"]
            ),
            "Gross Margin %": GlossaryTerm(
                business_term="Gross Margin %",
                synonyms=["gross margin", "margin", "profitability"],
                related_measures=["Gross Margin %"]
            ),
            "Average Unit Price": GlossaryTerm(
                business_term="Average Unit Price",
                synonyms=["unit price", "average price"],
                related_measures=["Average Unit Price"]
            )
        }
        return Glossary(version="1.0.0", domain="Retail & E-commerce", terms=terms)
    
    def reload(self) -> Glossary:
        """Reloads the glossary from the file."""
        self._glossary = None
        return self.load()


# ---------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------
_loader = GlossaryLoader()


def load_glossary_json(file_path: Optional[Path] = None) -> Glossary:
    """
    Loads the glossary from a JSON file.
    
    Args:
        file_path: Path to the JSON file (optional)
    
    Returns:
        Glossary: Glossary instance
    """
    if file_path:
        loader = GlossaryLoader(file_path)
        return loader.load()
    return _loader.load()


# Maintain compatibility with existing code
def load_glossary_yaml(file_path: Optional[Path] = None) -> Glossary:
    """
    Compatibility function for code expecting load_glossary_yaml.
    """
    return load_glossary_json(file_path)


def get_glossary_context() -> str:
    """
    Returns the glossary context as a string for use in prompts.
    """
    glossary = _loader.load()
    return glossary.get_context()


def find_terms_in_text(text: str) -> List[GlossaryTerm]:
    """
    Finds glossary terms in a text.
    """
    glossary = _loader.load()
    return glossary.find_term(text)


def get_all_terms() -> List[Dict[str, Any]]:
    """
    Returns all terms as a list of dictionaries.
    """
    glossary = _loader.load()
    return [
        {
            "business_term": term.business_term,
            "synonyms": term.synonyms,
            "related_measures": term.related_measures
        }
        for term in glossary.terms.values()
    ]


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    print('📚 Semantic Model Glossary')
    print('=' * 60)
    
    glossary = load_glossary_json()
    
    print(f"\n📄 File: {GLOSSARY_FILE}")
    print(f"📊 Version: {glossary.version}")
    print(f"📊 Domain: {glossary.domain}")
    print(f"\n📋 Loaded Terms: {len(glossary.terms)}")
    print("\n📋 Terms:")
    print("-" * 60)
    
    for term in glossary.terms.values():
        print(f"\n🔹 {term.business_term}")
        if term.synonyms:
            print(f"   Synonyms: {', '.join(term.synonyms)}")
        if term.related_measures:
            print(f"   Related Measures: {', '.join(term.related_measures)}")
    
    # Search test
    print("\n" + "=" * 60)
    print("🔍 Search Test:")
    test_text = "I want to see revenue and margin"
    print(f"Text: {test_text}")
    
    found = find_terms_in_text(test_text)
    print(f"Found terms: {[t.business_term for t in found]}")
    
    # Context test
    print("\n" + "=" * 60)
    print("📝 Glossary Context:")
    print(get_glossary_context())