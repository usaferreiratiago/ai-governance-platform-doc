from __future__ import annotations

import json
import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
METADATA_DIR = ROOT_DIR / 'metadata'
FILTERS_FILE = METADATA_DIR / 'mandatory_filters.json'
METADATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Import database guardrails
# ---------------------------------------------------------------------
try:
    from guardrails.db_guardrails import (
        get_mandatory_filters,
        get_guardrails,
        get_all_measures_with_filters,
        create_guardrail,
        update_guardrail,
        get_guardrail_statistics,
        init_guardrails
    )
    DB_AVAILABLE = True
    logger.info("Database guardrails module loaded")
except ImportError as e:
    DB_AVAILABLE = False
    logger.warning(f"Database guardrails module not available: {e}. Using file storage only.")


# ---------------------------------------------------------------------
# Default mandatory filter configuration
# ---------------------------------------------------------------------
DEFAULT_FILTERS = {
    'Net Revenue': ['Date', 'Organization'],
    'Gross Margin %': ['Date', 'Organization'],
    'Average Unit Price': ['Date', 'Organization'],
    'Return Rate': ['Date', 'Organization'],
    'Inventory Value': ['Date', 'Warehouse', 'Organization'],
    'Sales': ['Date', 'Region'],
    'Orders': ['Date', 'Status'],
    'Customer Count': ['Date', 'Segment'],
}


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------
@dataclass
class ValidationResult:
    passed: bool
    message: str
    missing_filters: List[str] = field(default_factory=list)
    suggestion: str = ""


# ---------------------------------------------------------------------
# Repository - Database-first with file fallback
# ---------------------------------------------------------------------
class MandatoryFilterRepository:
    """Loads and persists mandatory filter definitions using database-first strategy."""

    def __init__(self, path: Path = FILTERS_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db_cache = {}

        if DB_AVAILABLE:
            self._init_database()

    def _init_database(self) -> None:
        try:
            existing = get_guardrails()
            if not existing:
                logger.info("Initializing default guardrails in database...")
                result = init_guardrails()
                logger.info(f"Created {result['created']} default guardrails")
        except Exception as e:
            logger.warning(f"Error initializing database guardrails: {e}")

    def _get_from_db(self, measure: str) -> List[str]:
        if not DB_AVAILABLE:
            return []
        try:
            return get_mandatory_filters(measure)
        except Exception as e:
            logger.warning(f"Error getting filters from database: {e}")
            return []

    def _get_all_from_db(self) -> Dict[str, List[str]]:
        if not DB_AVAILABLE:
            return {}
        try:
            return get_all_measures_with_filters()
        except Exception as e:
            logger.warning(f"Error getting all filters from database: {e}")
            return {}

    def _save_to_db(self, measure: str, filters: List[str]) -> bool:
        if not DB_AVAILABLE:
            return False
        try:
            existing = self._get_from_db(measure)
            if existing:
                return update_guardrail(
                    measure_name=measure,
                    mandatory_filters=', '.join(filters)
                )
            else:
                result = create_guardrail(
                    measure_name=measure,
                    mandatory_filters=', '.join(filters),
                    description=f"Mandatory filters for {measure}",
                    created_by='system'
                )
                return result is not None
        except Exception as e:
            logger.warning(f"Error saving filters to database: {e}")
            return False

    def load(self) -> Dict[str, List[str]]:
        # Try database first
        if DB_AVAILABLE:
            try:
                db_data = self._get_all_from_db()
                if db_data:
                    return {k: v for k, v in db_data.items() if v}
            except Exception:
                pass

        # Fallback to file
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data:
                    return data
        except (json.JSONDecodeError, FileNotFoundError):
            logger.info(f"Filter file not found. Creating default at {self.path}")
            self.save(DEFAULT_FILTERS)
            return DEFAULT_FILTERS

        logger.info("Using default filters (file empty or not found)")
        return DEFAULT_FILTERS

    def save(self, data: Dict[str, List[str]]) -> None:
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        if DB_AVAILABLE:
            for measure, filters in data.items():
                self._save_to_db(measure, filters)

    def get_filters(self, measure: str) -> List[str]:
        if DB_AVAILABLE:
            db_filters = self._get_from_db(measure)
            if db_filters:
                return db_filters

        file_data = self.load()
        if measure in file_data and file_data[measure]:
            return file_data[measure]

        if measure in DEFAULT_FILTERS:
            logger.info(f"Using default filters for '{measure}'")
            return DEFAULT_FILTERS[measure]

        return []

    def get_all_measures(self) -> List[str]:
        if DB_AVAILABLE:
            db_data = self._get_all_from_db()
            if db_data:
                return list(db_data.keys())
        return list(self.load().keys())

    def add_measure(self, measure: str, filters: List[str]) -> None:
        data = self.load()
        data[measure] = filters
        self.save(data)

    def remove_measure(self, measure: str) -> None:
        data = self.load()
        if measure in data:
            del data[measure]
            self.save(data)


# ---------------------------------------------------------------------
# Validation service
# ---------------------------------------------------------------------
class MandatoryFilterValidator:
    def __init__(self, repository: Optional[MandatoryFilterRepository] = None):
        self.repository = repository or MandatoryFilterRepository()

    def validate(
        self,
        measure: str,
        provided_filters: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        provided_filters = provided_filters or {}

        # Get required filters for this measure
        required_filters = self.repository.get_filters(measure)

        # Debug logging
        logger.info(f"🔍 Validating measure: '{measure}'")
        logger.info(f"📋 Provided filters: {provided_filters}")
        logger.info(f"📌 Required filters: {required_filters}")

        if not required_filters:
            logger.info(f"No mandatory filters defined for '{measure}'")
            return ValidationResult(
                passed=True,
                message=f"No mandatory filters defined for '{measure}'",
                missing_filters=[],
                suggestion="Consider adding filters for this measure"
            )

        # Normalise provided keys to lower case for case-insensitive matching
        normalized_provided = {k.lower(): v for k, v in provided_filters.items() if v}
        logger.info(f"🔄 Normalized provided: {normalized_provided}")

        missing = []
        for required in required_filters:
            req_lower = required.lower()
            if req_lower not in normalized_provided:
                missing.append(required)

        if missing:
            suggestion = f"Add the following filters: {', '.join(missing)}"
            logger.warning(f"❌ Missing filters for '{measure}': {missing}")
            return ValidationResult(
                passed=False,
                message=(
                    f"Mandatory filters missing for '{measure}': "
                    + ', '.join(missing)
                ),
                missing_filters=missing,
                suggestion=suggestion,
            )

        logger.info(f"✅ All mandatory filters for '{measure}' are present.")
        return ValidationResult(
            passed=True,
            message=f"All mandatory filters for '{measure}' are present.",
            missing_filters=[],
        )

    def validate_query_context(
        self,
        measure: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        context = context or {}
        provided_filters = context.get('filters', {})
        return self.validate(measure, provided_filters)


# ---------------------------------------------------------------------
# Convenience functions (compatibility with your code)
# ---------------------------------------------------------------------
_validator = MandatoryFilterValidator()


def validate_filters(
    measure: str,
    provided_filters: Optional[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    if context:
        provided_filters = context.get('filters', provided_filters or {})

    result = _validator.validate(measure, provided_filters)

    return {
        "valid": result.passed,
        "message": result.message,
        "missing_filters": result.missing_filters,
        "suggestion": result.suggestion,
        "measure": measure
    }


def validate_mandatory_filters(
    measure: str,
    provided_filters: Optional[Dict[str, str]] = None,
) -> Tuple[bool, str]:
    result = _validator.validate(measure, provided_filters)
    return result.passed, result.message


def validate_required_filters(
    query: str,
    required_filters: Optional[List[str]] = None
) -> bool:
    if required_filters is None:
        required_filters = ["date", "organization_id", "tenant_id"]
    query_lower = query.lower()
    for filter_required in required_filters:
        if filter_required.lower() not in query_lower:
            return False
    return True


def get_missing_filters(
    query: str,
    required_filters: Optional[List[str]] = None
) -> List[str]:
    if required_filters is None:
        required_filters = ["date", "organization_id", "tenant_id"]
    query_lower = query.lower()
    missing = []
    for filter_required in required_filters:
        if filter_required.lower() not in query_lower:
            missing.append(filter_required)
    return missing


def enforce_before_execution(
    measure: str,
    provided_filters: Optional[Dict[str, Any]] = None,
) -> None:
    result = _validator.validate(measure, provided_filters)
    if not result.passed:
        raise ValueError(f"❌ {result.message}\n💡 {result.suggestion}")


def check_and_warn(
    measure: str,
    provided_filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    result = _validator.validate(measure, provided_filters)
    return {
        "valid": result.passed,
        "warnings": result.missing_filters,
        "message": result.message,
        "suggestion": result.suggestion
    }


# ---------------------------------------------------------------------
# Database management functions
# ---------------------------------------------------------------------
def sync_to_database() -> Dict[str, Any]:
    if not DB_AVAILABLE:
        return {"error": "Database not available"}

    results = {"synced": 0, "failed": 0, "errors": []}
    try:
        filters = _validator.repository.load()
        for measure, filter_list in filters.items():
            try:
                success = _validator.repository._save_to_db(measure, filter_list)
                if success:
                    results["synced"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to sync {measure}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{measure}: {str(e)}")
        return results
    except Exception as e:
        return {"error": str(e)}


def get_statistics() -> Dict[str, Any]:
    if DB_AVAILABLE:
        try:
            return get_guardrail_statistics()
        except Exception:
            pass
    filters = _validator.repository.load()
    return {
        "total": len(filters),
        "measures": list(filters.keys()),
        "source": "file"
    }


# ---------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Mandatory Filter Validator')
    parser.add_argument('--sync', action='store_true', help='Sync filters to database')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--list', action='store_true', help='List all filters')
    parser.add_argument('--init-db', action='store_true', help='Initialize database with default filters')

    args = parser.parse_args()

    print('🔍 Mandatory Filter Validator')
    print('=' * 60)
    print(f'📁 Configuration file: {FILTERS_FILE}')
    print(f'💾 Database available: {DB_AVAILABLE}')
    print()

    if args.init_db:
        if not DB_AVAILABLE:
            print('❌ Database not available. Please ensure database is configured.')
        else:
            print('📝 Initializing database with default filters...')
            result = init_guardrails()
            print(f'✅ Created {result["created"]} default guardrails')
            if result.get('errors'):
                print(f'⚠️ Errors: {result["errors"]}')

    elif args.sync:
        print('🔄 Syncing filters to database...')
        result = sync_to_database()
        if result.get('error'):
            print(f'❌ Error: {result["error"]}')
        else:
            print(f'✅ Synced: {result["synced"]} filters')
            if result["failed"] > 0:
                print(f'⚠️ Failed: {result["failed"]}')
                for err in result.get("errors", []):
                    print(f'   - {err}')

    elif args.stats:
        print('📊 Statistics:')
        print('-' * 60)
        stats = get_statistics()
        print(f"Total Measures: {stats.get('total', 0)}")
        if 'source' in stats:
            print(f"Source: {stats.get('source', 'unknown')}")
        if 'active' in stats:
            print(f"Active: {stats.get('active', 0)}")
            print(f"Inactive: {stats.get('inactive', 0)}")
        if 'measures' in stats:
            print("\nMeasures:")
            for m in stats.get('measures', []):
                print(f"  - {m}")

    elif args.list:
        print('📋 Available measures and filters:')
        print('-' * 60)
        validator = MandatoryFilterValidator()
        measures = validator.repository.get_all_measures()
        for measure in sorted(measures):
            filters = validator.repository.get_filters(measure)
            print(f"\n🔹 {measure}:")
            if filters:
                for f in filters:
                    print(f"   - {f}")
            else:
                print("   No filters defined")

    else:
        validator = MandatoryFilterValidator()

        measures = validator.repository.get_all_measures()
        print(f'📊 Available measures: {", ".join(measures) if measures else "None"}')
        print()

        examples = [
            ('Net Revenue', {}),
            ('Net Revenue', {'Date': '2026-Q2'}),
            ('Gross Margin %', {'Date': '2026-07'}),
            ('Inventory Value', {'Date': '2026-01-01'}),
            ('Inventory Value', {'Date': '2026-01-01', 'Warehouse': 'MIL01'}),
            ('Sales', {'Date': '2026-01-01'}),
        ]

        print('🧪 Tests:')
        print('-' * 60)

        for measure, filters in examples:
            result = validator.validate(measure, filters)
            status = '✅ PASSED' if result.passed else '❌ FAILED'
            print(f'\n📌 Measure: {measure}')
            print(f'   Filters: {filters}')
            print(f'   Status : {status}')
            print(f'   Message: {result.message}')
            if result.suggestion:
                print(f'   💡 Suggestion: {result.suggestion}')
            if result.missing_filters:
                print(f'   Missing: {", ".join(result.missing_filters)}')
            print('-' * 60)