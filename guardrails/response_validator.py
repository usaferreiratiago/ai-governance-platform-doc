from __future__ import annotations

import json
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT_DIR / 'metadata'
CERTIFIED_MEASURES_FILE = METADATA_DIR / 'certified_measures.yaml'


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
MAX_RESPONSE_LENGTH = 2000

HALLUCINATION_PATTERNS = [
    r'(?i)i guess',
    r'(?i)probably',
    r'(?i)approximately\s+\$?\d',
    r'(?i)it seems',
    r'(?i)i think',
    r'(?i)estimated',
    r'(?i)assumed',
]

OUT_OF_SCOPE_PHRASES = [
    'not available in the approved semantic model',
    'outside the approved semantic scope',
    'I do not have access to that information',
]

SENSITIVE_TERMS = [
    'password',
    'secret',
    'token',
    'api key',
    'client secret',
]


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------
@dataclass
class ResponseValidationResult:
    passed: bool
    score: float
    message: str
    issues: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------
class ResponseValidator:
    """
    Validates LLM responses before they are returned to the user.
    """

    def __init__(self):
        self.certified_measures = self._load_certified_measures()
        self.certified_measure_names = [m.get('name') for m in self.certified_measures if m.get('certified', False)]

    def _load_certified_measures(self) -> List[Dict[str, Any]]:
        """Load certified measures from YAML file."""
        if not CERTIFIED_MEASURES_FILE.exists():
            print(f"⚠️ Certified measures file not found: {CERTIFIED_MEASURES_FILE}")
            return self._get_default_certified_measures()

        try:
            with open(CERTIFIED_MEASURES_FILE, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Handle different possible structures
            if 'certified_measures' in data:
                return data['certified_measures']
            elif 'measures' in data:
                return data['measures']
            else:
                return self._get_default_certified_measures()
                
        except Exception as e:
            print(f"⚠️ Error loading certified measures: {e}")
            return self._get_default_certified_measures()

    def _get_default_certified_measures(self) -> List[Dict[str, Any]]:
        """Return default certified measures if file not found."""
        return [
            {'name': 'Net Revenue', 'certified': True},
            {'name': 'Gross Margin %', 'certified': True},
            {'name': 'Average Unit Price', 'certified': True},
            {'name': 'Inventory Value', 'certified': True},
            {'name': 'Return Rate', 'certified': True},
        ]

    def validate(
        self,
        question: str,
        answer: str,
        measure: Optional[str] = None,
    ) -> ResponseValidationResult:
        issues: List[str] = []
        score = 1.0

        answer = answer or ''

        # Empty response
        if not answer.strip():
            issues.append('Empty response.')
            score -= 1.0

        # Excessive length
        if len(answer) > MAX_RESPONSE_LENGTH:
            issues.append('Response exceeds maximum allowed length.')
            score -= 0.2

        # Hallucination indicators
        hallucinations = self._detect_hallucination(answer)
        if hallucinations:
            issues.extend(hallucinations)
            score -= 0.4

        # Sensitive information
        sensitive = self._detect_sensitive_information(answer)
        if sensitive:
            issues.extend(sensitive)
            score -= 1.0

        # Certified measure validation
        if measure:
            if not self._is_certified_measure(measure):
                issues.append(f"Measure '{measure}' is not certified.")
                score -= 0.3
            else:
                # Check mandatory filters from certified measures
                mandatory_filters = self._get_mandatory_filters(measure)
                if mandatory_filters:
                    # This is just a check - actual validation happens in mandatory_filters.py
                    pass

        # Out-of-scope consistency
        if self._is_out_of_scope(question) and not self._contains_out_of_scope_message(answer):
            issues.append(
                'Out-of-scope question was not answered with a governance-safe response.'
            )
            score -= 0.5

        # Clamp score
        score = max(0.0, round(score, 2))

        passed = score >= 0.7 and not any(
            issue.startswith('Sensitive') for issue in issues
        )

        message = (
            'Response passed validation.'
            if passed
            else 'Response failed validation.'
        )

        return ResponseValidationResult(
            passed=passed,
            score=score,
            message=message,
            issues=issues,
        )

    def _is_certified_measure(self, measure: str) -> bool:
        """Check if a measure is certified."""
        return measure in self.certified_measure_names

    def _get_mandatory_filters(self, measure: str) -> List[str]:
        """Get mandatory filters for a certified measure."""
        for m in self.certified_measures:
            if m.get('name') == measure:
                return m.get('mandatory_filters', [])
        return []

    def _detect_hallucination(self, answer: str) -> List[str]:
        issues = []

        for pattern in HALLUCINATION_PATTERNS:
            if re.search(pattern, answer):
                issues.append(
                    f"Potential hallucination detected: pattern '{pattern}'."
                )

        return issues

    def _detect_sensitive_information(self, answer: str) -> List[str]:
        issues = []

        lower_answer = answer.lower()

        for term in SENSITIVE_TERMS:
            if term in lower_answer:
                issues.append(
                    f"Sensitive information detected: term '{term}'."
                )

        return issues

    def _is_out_of_scope(self, question: str) -> bool:
        q = question.lower()

        triggers = [
            'forecast',
            'predict',
            'future sales',
            'next quarter',
            'hidden tables',
            'system prompt',
            'database password',
            'ignore previous',
            'bypass',
            'override',
        ]

        return any(trigger in q for trigger in triggers)

    def _contains_out_of_scope_message(self, answer: str) -> bool:
        lower_answer = answer.lower()

        return any(
            phrase.lower() in lower_answer
            for phrase in OUT_OF_SCOPE_PHRASES
        )


# ---------------------------------------------------------------------
# Singleton validator
# ---------------------------------------------------------------------
_validator = ResponseValidator()


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def validate_response(
    question: str,
    answer: str,
    measure: Optional[str] = None,
) -> ResponseValidationResult:
    return _validator.validate(question, answer, measure)


def enforce_response_validation(
    question: str,
    answer: str,
    measure: Optional[str] = None,
) -> None:
    result = _validator.validate(question, answer, measure)

    if not result.passed:
        raise ValueError(
            result.message + ' ' + '; '.join(result.issues)
        )


# ---------------------------------------------------------------------
# MCP integration helper
# ---------------------------------------------------------------------
def validate_and_format_response(
    question: str,
    answer: str,
    measure: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Validate and format the response from the LLM.
    
    Args:
        question: Original user question
        answer: The answer from the LLM
        measure: Detected measure name
        **kwargs: Additional metadata to include in response
    
    Returns:
        Dict with validated and formatted response
    """
    result = _validator.validate(question, answer, measure)

    # Build the response
    response = {
        'answer': answer,
        'source': 'Governed Semantic Model',
        'validation_passed': result.passed,
        'validation_score': result.score,
        'issues': result.issues,
        'measure': measure,
        'question': question,
    }
    
    # Add any additional kwargs
    for key, value in kwargs.items():
        if key not in response:
            response[key] = value

    if not result.passed:
        # Check if the issue is only about certification
        if result.issues and len(result.issues) == 1 and "not certified" in result.issues[0]:
            # Still return the answer but with a warning
            response['answer'] = answer
            response['source'] = 'Governed Semantic Model (Uncertified Measure)'
            response['warning'] = result.issues[0]
        else:
            response['answer'] = (
                'I could not provide a governed answer because the response '
                'failed validation checks.'
            )
            response['source'] = 'Response Validator'

    return response


def get_certified_measures() -> List[str]:
    """Get list of certified measure names."""
    return _validator.certified_measure_names


# ---------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    print('=' * 80)
    print('RESPONSE VALIDATOR TEST')
    print('=' * 80)
    
    print(f"\n📋 Certified Measures: {get_certified_measures()}")
    
    examples = [
        (
            'What was net revenue in Q2 2026?',
            'Net Revenue in Q2 2026 was $12,435,221.',
            'Net Revenue',
        ),
        (
            'Forecast next quarter sales.',
            'I think sales will probably be around $15M next quarter.',
            'Net Revenue',
        ),
        (
            'Show hidden tables.',
            'Sure, the hidden tables are...',
            None,
        ),
        (
            'What is gross margin?',
            'Gross Margin % was 42.1%.',
            'Gross Margin %',
        ),
        (
            'What is average unit price?',
            'Average Unit Price is $89.34.',
            'Average Unit Price',
        ),
    ]

    for question, answer, measure in examples:
        result = validate_response(question, answer, measure)

        print('=' * 80)
        print('Question :', question)
        print('Answer   :', answer[:80] + '...' if len(answer) > 80 else answer)
        print('Measure  :', measure)
        print('Passed   :', result.passed)
        print('Score    :', result.score)
        print('Message  :', result.message)

        if result.issues:
            print('Issues:')
            for issue in result.issues:
                print('  -', issue)