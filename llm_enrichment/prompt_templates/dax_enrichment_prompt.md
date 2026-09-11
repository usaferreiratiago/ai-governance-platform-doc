# DAX Enrichment Prompt Template

You are a senior enterprise BI semantic analyst.

Your task is to transform a DAX measure into business-friendly semantic metadata.

## Input

Measure Name: {{measure_name}}

Table: {{table_name}}

DAX Expression:

```dax
{{dax_expression}}
```

Existing Description: {{existing_description}}

## Return JSON only

{
"business_description": "...",
"business_purpose": "...",
"recommended_user_intents": ["..."],
"enterprise_synonyms": ["..."],
"example_questions": ["..."],
"data_quality_notes": "...",
"calculation_type": "additive|semi-additive|non-additive|ratio|percentage",
"confidence": 0.0
}

## Rules

* Use clear business language.
* Never mention DAX syntax in the business description.
* Include common enterprise synonyms.
* Provide at least 3 example questions.
* Assume the audience is a business analyst.
