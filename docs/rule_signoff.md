# Rule catalog sign-off (v1.0)

Edit this page directly on GitHub. The rules and their sources are listed in [rule_catalog.md](rule_catalog.md); the code is `src/clinverify/rules/catalog.py`.

The column "Assistant's check" records that the AI assistant that drafted the rules located each cited statement in the open-access guideline text and compared the rule with it. It is **not** a human sign-off and does not replace the next columns.

**How to sign off a rule**
1. Open the guideline cited for the rule (the source and statement number are in the rule table) and read that statement, not only the summary.
2. Check that the rule's condition, threshold and wording match the statement. Read the rule's violation message too.
3. Tick `[x]` and add your initials and date in the Notes column.
4. If you **cannot** tick it, leave the box empty and write the reason in Notes (for example: "statement not found", "threshold differs", "needs clinician", "condition unclear"), then tell the rule owner.

| Rule | Name | Assistant's check of the guideline text | Owner (Sneha) read against source | Second team member | Clinical / domain reviewer | Notes (initials, date, reasons) |
|---|---|---|---|---|---|---|
| `R-GEN-001` | Diagnosis is in scope | n/a (scope guard, no guideline) | [x] | [ ] | [ ] | SS, 2026-10-21 (scope guard, no guideline) |
| `R-APP-001` | Preoperative antibiotic dose before appendectomy | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-APP-002` | No postoperative antibiotics when uncomplicated | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-APP-003` | Postoperative antibiotics not longer than 5 days (complicated) | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-APP-004` | Appendectomy within 24 hours (adults) | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-CHO-001` | No routine postoperative antibiotics when uncomplicated | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-CHO-002` | Cholecystectomy first-line; drainage if unsuitable for surgery | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-001` | No routine prophylactic antibiotics | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-002` | Antibiotics for infected severe pancreatitis | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-003` | Index-admission cholecystectomy (mild gallstone pancreatitis) | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-004` | No routine ERCP in gallstone pancreatitis | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-005` | Enteral nutrition in severe pancreatitis | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-DIV-001` | No antibiotics for uncomplicated diverticulitis | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-DIV-002` | Postoperative antibiotics about 4 days (complicated) | statement located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |

**When every box in the first two columns is ticked:** tag the commit `rules-v1.0-signed-off` and do not edit the catalog afterwards without bumping `CATALOG_VERSION`. The clinical reviewer column stays empty if no clinician is available; say so in the report.
