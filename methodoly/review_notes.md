# Methodology Review Notes

## Sprint 0 Technical Review

### Reviewer

Tiago Ferreira

### Date

2026-07-29

---

## Level 1 Review

* Naming convention aligned with enterprise BI standards.
* Display folder taxonomy approved.
* Annotation schema approved.
* Additional recommendation: enforce description completeness through automated validation.

---

## Level 2 Review

* XMLA extraction approach technically feasible.
* REST API extraction approach technically feasible.
* Recommend storing raw extracts immutable for audit purposes.
* Recommend daily scheduled extraction job.

---

## Level 3 Review

* DAX-to-LLM enrichment pipeline technically feasible.
* Confidence scoring should be stored per generated artifact.
* Human approval workflow mandatory before production publication.
* Recommend prompt versioning.

---

## Risks

| Risk                               | Mitigation                           |
| ---------------------------------- | ------------------------------------ |
| Incomplete model descriptions      | Automated validation                 |
| Ambiguous business terminology     | Central glossary governance          |
| LLM inconsistent wording           | Prompt standardization               |
| Metadata drift after model changes | Scheduled extraction and diff checks |

---

## Immediate Sprint 0 Actions

* [ ] Obtain production `.pbip` files.
* [ ] Obtain Power BI service principal credentials.
* [ ] Validate XMLA endpoint connectivity.
* [ ] Execute first metadata extraction.
* [ ] Generate first enrichment batch.
* [ ] Review with Finance business owner.
