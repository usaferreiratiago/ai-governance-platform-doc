# Methodology & Best Practices for Creating an LLM-Ready Semantic Model

## Version

0.9 – Draft for Client Review

## Objective

Transform an existing Power BI / BigQuery semantic model into a governed, explainable, and LLM-ready semantic layer suitable for natural language analytics.

---

## 1. Principles

* Business-first naming
* Explicit business definitions
* Governed metadata
* Machine-readable semantics
* Deterministic benchmark validation
* Continuous enrichment lifecycle

---

## 2. Architecture

Power BI Semantic Model → XMLA/REST Extraction → Metadata Repository → LLM Enrichment → MCP → Governance Dashboard

---

## 3. Level 1 – Structural Enrichment

## Naming standards

* Avoid abbreviations.
* Use singular business nouns.
* Prefix KPI measures consistently.

## Display folders

Examples:

* Finance/Revenue
* Finance/Margin
* Commercial/Customers
* Operations/Inventory

## Mandatory metadata

| Property        | Required |
| --------------- | -------- |
| Description     | Yes      |
| BusinessOwner   | Yes      |
| Certified       | Yes      |
| AllowedSynonyms | Yes      |
| LastReviewed    | Yes      |

---

## 4. Level 2 – Service & Governance Integration

## Required APIs

* Power BI REST API
* XMLA Endpoint

## Extracted assets

* Tables
* Columns
* Measures
* Relationships
* Refresh history
* Usage statistics
* Lineage

## Repository format

Use JSON for automation and YAML for human-governed glossary content.

---

## 5. Level 3 – LLM Semantic Enrichment

## Inputs

* Measure name
* DAX expression
* Existing description
* Table context

## Outputs

* Business description
* User intents
* Synonyms
* Example questions
* Calculation type
* Confidence score

## Human review

All generated descriptions must be approved by a domain owner before production publication.

---

## 6. Business Glossary

Maintain a centralized glossary with enterprise synonyms.

Example:

* Revenue = Sales, Turnover
* Customer = Client, Account
* Gross Margin = Margin, Profit Margin

---

## 7. Benchmark Methodology

Each benchmark must contain:

* Natural language question
* Expected answer
* Source report
* Validation owner
* Validation date

Minimum target accuracy: **85%**.

Critical hallucinations allowed: **0**.

---

## 8. Governance Controls

* Prompt versioning
* Audit logging
* Role-based access
* Metadata change history
* Benchmark approval workflow

---

## 9. Release Checklist

* [ ] Semantic model reviewed
* [ ] Metadata exported
* [ ] LLM enrichment reviewed
* [ ] Glossary approved
* [ ] Benchmarks validated
* [ ] Accuracy threshold achieved
* [ ] Security review completed

---

## 10. Deliverables

* Enriched semantic model (.pbip)
* Metadata repository
* Business glossary
* Enrichment pipeline
* Benchmark suite
* Governance dashboard
* Operations documentation
