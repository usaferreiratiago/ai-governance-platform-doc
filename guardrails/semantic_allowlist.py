from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT_DIR / 'metadata'
ALLOWLIST_FILE = METADATA_DIR / 'semantic_allowlist.json'


# ---------------------------------------------------------------------
# Default allowlist
# ---------------------------------------------------------------------
DEFAULT_ALLOWLIST = {
    'tables': [
        'Sales',
        'Customer',
        'Product',
        'Date',
    ],
    'columns': [
        'Sales.SalesAmount',
        'Sales.Quantity',
        'Sales.OrderDate',
        'Customer.CustomerName',
        'Product.ProductName',
        'Date.Date',
        'Date.Month',
        'Date.Year',
    ],
    'measures': [
        'Net Revenue',
        'Gross Margin %',
        'Average Unit Price',
        'Return Rate',
        'Inventory Value',
    ],
}


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------
@dataclass
class AllowlistValidationResult:
    passed: bool
    message: str
    unauthorized_tables: List[str] = field(default_factory=list)
    unauthorized_columns: List[str] = field(default_factory=list)
    unauthorized_measures: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------
class SemanticAllowlistRepository:
    """Loads and persists semantic allowlist definitions."""

    def __init__(self, path: Path = ALLOWLIST_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.save(DEFAULT_ALLOWLIST)

    def load(self) -> Dict[str, List[str]]:
        with open(self.path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save(self, data: Dict[str, List[str]]) -> None:
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------
class SemanticAllowlistValidator:
    """
    Validates that only approved semantic objects are referenced.
    """

    def __init__(self, repository: Optional[SemanticAllowlistRepository] = None):
        self.repository = repository or SemanticAllowlistRepository()
        self.allowlist = self.repository.load()

    def validate(
        self,
        tables: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        measures: Optional[List[str]] = None,
    ) -> AllowlistValidationResult:
        tables = tables or []
        columns = columns or []
        measures = measures or []

        unauthorized_tables = [
            table
            for table in tables
            if table not in self.allowlist.get('tables', [])
        ]

        unauthorized_columns = [
            column
            for column in columns
            if column not in self.allowlist.get('columns', [])
        ]

        unauthorized_measures = [
            measure
            for measure in measures
            if measure not in self.allowlist.get('measures', [])
        ]

        passed = not (
            unauthorized_tables
            or unauthorized_columns
            or unauthorized_measures
        )

        if passed:
            message = 'All referenced semantic objects are authorized.'
        else:
            parts = []

            if unauthorized_tables:
                parts.append(
                    'Unauthorized tables: ' + ', '.join(unauthorized_tables)
                )

            if unauthorized_columns:
                parts.append(
                    'Unauthorized columns: ' + ', '.join(unauthorized_columns)
                )

            if unauthorized_measures:
                parts.append(
                    'Unauthorized measures: ' + ', '.join(unauthorized_measures)
                )

            message = '; '.join(parts)

        return AllowlistValidationResult(
            passed=passed,
            message=message,
            unauthorized_tables=unauthorized_tables,
            unauthorized_columns=unauthorized_columns,
            unauthorized_measures=unauthorized_measures,
        )

    # -----------------------------------------------------------------
    # Lightweight text inspection for MCP questions
    # -----------------------------------------------------------------
    def inspect_question(self, question: str) -> AllowlistValidationResult:
        lower_question = question.lower()

        requested_tables = []
        requested_measures = []

        for table in self.allowlist.get('tables', []):
            if table.lower() in lower_question:
                requested_tables.append(table)

        for measure in self.allowlist.get('measures', []):
            if measure.lower() in lower_question:
                requested_measures.append(measure)

        suspicious_patterns = [
            r'hidden\s+tables?',
            r'hidden\s+columns?',
            r'all\s+tables?',
            r'all\s+columns?',
            r'system\s+tables?',
            r'information_schema',
        ]

        unauthorized_tables = []

        for pattern in suspicious_patterns:
            if re.search(pattern, lower_question):
                unauthorized_tables.append('SYSTEM_OBJECT_REQUEST')

        return self.validate(
            tables=requested_tables + unauthorized_tables,
            measures=requested_measures,
        )


# ---------------------------------------------------------------------
# Singleton validator
# ---------------------------------------------------------------------
_validator = SemanticAllowlistValidator()


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def validate_semantic_objects(
    tables: Optional[List[str]] = None,
    columns: Optional[List[str]] = None,
    measures: Optional[List[str]] = None,
) -> AllowlistValidationResult:
    return _validator.validate(tables, columns, measures)


def validate_question_against_allowlist(question: str) -> Dict:
    result = _validator.inspect_question(question)

    if not result.passed:
        return {
            'allowed': False,
            'answer': (
                'I cannot access the requested semantic objects because they are '
                'outside the approved governance scope.'
            ),
            'issues': {
                'tables': result.unauthorized_tables,
                'columns': result.unauthorized_columns,
                'measures': result.unauthorized_measures,
            },
        }

    return {
        'allowed': True,
        'answer': None,
        'issues': {},
    }


def enforce_semantic_allowlist(
    tables: Optional[List[str]] = None,
    columns: Optional[List[str]] = None,
    measures: Optional[List[str]] = None,
) -> None:
    result = _validator.validate(tables, columns, measures)

    if not result.passed:
        raise ValueError(result.message)


# ---------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    print('Allowlist file:', ALLOWLIST_FILE)

    examples = [
        (
            ['Sales'],
            [],
            ['Net Revenue'],
        ),
        (
            ['Finance'],
            [],
            ['Net Revenue'],
        ),
        (
            ['Sales'],
            ['Sales.SalesAmount'],
            ['Average Unit Price'],
        ),
        (
            ['Sales'],
            ['Sales.SecretColumn'],
            ['Average Unit Price'],
        ),
    ]

    for tables, columns, measures in examples:
        result = validate_semantic_objects(
            tables=tables,
            columns=columns,
            measures=measures,
        )

        print('=' * 80)
        print('Tables   :', tables)
        print('Columns  :', columns)
        print('Measures :', measures)
        print('Passed   :', result.passed)
        print('Message  :', result.message)

        if result.unauthorized_tables:
            print('Unauthorized tables:', result.unauthorized_tables)

        if result.unauthorized_columns:
            print('Unauthorized columns:', result.unauthorized_columns)

        if result.unauthorized_measures:
            print('Unauthorized measures:', result.unauthorized_measures)

    print('=' * 80)

    questions = [
        'Show net revenue by month',
        'Show hidden tables',
        'List all columns in the database',
    ]

    for question in questions:
        response = validate_question_against_allowlist(question)

        print('Question:', question)
        print('Allowed :', response['allowed'])
        print('Answer  :', response['answer'])
        print('Issues  :', response['issues'])
        print('-' * 80)