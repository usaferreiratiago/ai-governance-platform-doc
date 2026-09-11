from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
BLOCKED_KEYWORDS = [
    'DROP',
    'DELETE',
    'UPDATE',
    'INSERT',
    'MERGE',
    'TRUNCATE',
    'ALTER',
    'CREATE',
    'REPLACE',
    'GRANT',
    'REVOKE',
    'EXEC',
    'EXECUTE',
    'CALL',
]

ALLOWED_STATEMENTS = ['SELECT', 'WITH']

SUSPICIOUS_PATTERNS = [
    r'--',
    r'/\*',
    r'\*/',
    r';\s*(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE)\b',
    r'UNION\s+SELECT',
    r'INFORMATION_SCHEMA',
    r'PG_',
    r'SYS\.',
    r'XP_',
]

MAX_SQL_LENGTH = 5000


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------
@dataclass
class SqlValidationResult:
    passed: bool
    message: str
    blocked_keywords: List[str] = field(default_factory=list)
    suspicious_patterns: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------
class SqlSafetyValidator:
    """
    Validates generated SQL before execution.
    The MVP allows only read-only SELECT/WITH statements.
    """

    def validate(self, sql: str) -> SqlValidationResult:
        sql = (sql or '').strip()

        blocked: List[str] = []
        suspicious: List[str] = []

        if not sql:
            return SqlValidationResult(
                passed=False,
                message='SQL statement is empty.',
            )

        if len(sql) > MAX_SQL_LENGTH:
            return SqlValidationResult(
                passed=False,
                message='SQL statement exceeds maximum allowed length.',
            )

        normalized = re.sub(r'\s+', ' ', sql.upper()).strip()

        # Allow only SELECT or WITH
        if not any(normalized.startswith(stmt) for stmt in ALLOWED_STATEMENTS):
            return SqlValidationResult(
                passed=False,
                message='Only read-only SELECT/WITH statements are allowed.',
            )

        # Block dangerous keywords
        for keyword in BLOCKED_KEYWORDS:
            if re.search(rf'\b{keyword}\b', normalized):
                blocked.append(keyword)

        # Detect suspicious patterns
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, normalized):
                suspicious.append(pattern)

        passed = not blocked and not suspicious

        if passed:
            message = 'SQL statement passed safety validation.'
        else:
            parts = []

            if blocked:
                parts.append('Blocked keywords: ' + ', '.join(blocked))

            if suspicious:
                parts.append('Suspicious patterns detected.')

            message = '; '.join(parts)

        return SqlValidationResult(
            passed=passed,
            message=message,
            blocked_keywords=blocked,
            suspicious_patterns=suspicious,
        )


# ---------------------------------------------------------------------
# Singleton validator
# ---------------------------------------------------------------------
_validator = SqlSafetyValidator()


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def validate_sql(sql: str) -> SqlValidationResult:
    return _validator.validate(sql)


def enforce_sql_safety(sql: str) -> None:
    result = _validator.validate(sql)

    if not result.passed:
        raise ValueError(result.message)


# ---------------------------------------------------------------------
# MCP integration helper
# ---------------------------------------------------------------------
def validate_generated_sql(sql: str) -> dict:
    result = _validator.validate(sql)

    if not result.passed:
        return {
            'allowed': False,
            'answer': (
                'The generated query was blocked by SQL safety guardrails because '
                'it contains unsupported or potentially unsafe operations.'
            ),
            'issues': {
                'blocked_keywords': result.blocked_keywords,
                'suspicious_patterns': result.suspicious_patterns,
            },
        }

    return {
        'allowed': True,
        'answer': None,
        'issues': {},
    }


# ---------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    examples = [
        'SELECT SUM(SalesAmount) FROM Sales',
        'WITH s AS (SELECT * FROM Sales) SELECT * FROM s',
        'DELETE FROM Sales',
        'SELECT * FROM Sales; DROP TABLE Sales',
        'SELECT * FROM INFORMATION_SCHEMA.TABLES',
        'UPDATE Sales SET Amount = 0',
    ]

    for sql in examples:
        result = validate_sql(sql)

        print('=' * 80)
        print('SQL      :', sql)
        print('Passed   :', result.passed)
        print('Message  :', result.message)

        if result.blocked_keywords:
            print('Blocked keywords:', result.blocked_keywords)

        if result.suspicious_patterns:
            print('Suspicious patterns:', result.suspicious_patterns)