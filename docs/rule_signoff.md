# Rule catalog sign-off (v1.0)

Edit this page directly on GitHub. The rules and their sources are listed in [rule_catalog.md](rule_catalog.md); the code is `src/clinverify/rules/catalog.py`.

**How to sign off a rule**
1. Open the guideline cited for the rule (the source and statement number are in the rule table) and read that statement, not only the summary.
2. Check that the rule's condition, threshold and wording match the statement. Read the rule's violation message too.
3. Tick `[x]` and add your initials and date in the Notes column.
4. If you **cannot** tick it, leave the box empty and write the reason in Notes (for example: "statement not found", "threshold differs", "needs clinician", "condition unclear"), then tell the rule owner.

| Rule | Name | Owner (Sneha) read against source | Second team member | Clinical / domain reviewer | Notes (initials, date, reasons) |
|---|---|---|---|---|---|
| `R-GEN-001` | Diagnosis is in scope | [ ] | [ ] | [ ] | |
| `R-APP-001` | Preoperative antibiotic dose before appendectomy | [ ] | [ ] | [ ] | |
| `R-APP-002` | No postoperative antibiotics when uncomplicated | [ ] | [ ] | [ ] | |
| `R-APP-003` | Postoperative antibiotics not longer than 5 days (complicated) | [ ] | [ ] | [ ] | |
| `R-APP-004` | Appendectomy within 24 hours (adults) | [ ] | [ ] | [ ] | |
| `R-CHO-001` | No routine postoperative antibiotics when uncomplicated | [ ] | [ ] | [ ] | |
| `R-CHO-002` | Cholecystectomy first-line; drainage if unsuitable for surgery | [ ] | [ ] | [ ] | |
| `R-PAN-001` | No routine prophylactic antibiotics | [ ] | [ ] | [ ] | |
| `R-PAN-002` | Antibiotics for infected severe pancreatitis | [ ] | [ ] | [ ] | |
| `R-PAN-003` | Index-admission cholecystectomy (mild gallstone pancreatitis) | [ ] | [ ] | [ ] | |
| `R-PAN-004` | No routine ERCP in gallstone pancreatitis | [ ] | [ ] | [ ] | |
| `R-PAN-005` | Enteral nutrition in severe pancreatitis | [ ] | [ ] | [ ] | |
| `R-DIV-001` | No antibiotics for uncomplicated diverticulitis | [ ] | [ ] | [ ] | |
| `R-DIV-002` | Postoperative antibiotics about 4 days (complicated) | [ ] | [ ] | [ ] | |

**When every box in the first two columns is ticked:** tag the commit `rules-v1.0-signed-off` and do not edit the catalog afterwards without bumping `CATALOG_VERSION`. The clinical reviewer column stays empty if no clinician is available; say so in the report.
