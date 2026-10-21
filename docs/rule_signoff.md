# Rule catalog sign-off (v2.0)

Edit this page directly on GitHub. The rules and their sources are listed in [rule_catalog.md](rule_catalog.md); the code is `src/clinverify/rules/catalog.py`.

The column "Assistant's check" records that the AI assistant that drafted the rules located each cited statement in the open-access guideline text and compared the rule with it. It is **not** a human sign-off and does not replace the next columns.

**How to sign off a rule**
1. Open the guideline cited for the rule (the source and statement number are in the rule table) and read that statement, not only the summary.
2. Check that the rule's condition, threshold and wording match the statement. Read the rule's violation message too.
3. Tick `[x]` and add your initials and date in the Notes column.
4. If you **cannot** tick it, leave the box empty and write the reason in Notes (for example: "statement not found", "threshold differs", "needs clinician", "condition unclear"), then tell the rule owner.

| Rule | Name | Assistant's check of the source | Owner (Sneha) read against source | Second team member | Clinical / domain reviewer | Notes (initials, date, reasons) |
|---|---|---|---|---|---|---|
| `R-GEN-001` | Diagnosis is covered by the rules | n/a (scope guard, no guideline) | [ ] | [ ] | [ ] | |
| `R-APP-001` | Antibiotic prophylaxis for appendectomy | full text located and compared, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-APP-002` | No postoperative antibiotics when uncomplicated | full text located and compared, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-APP-003` | Short postoperative antibiotic course (complicated) | abstract only, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-PAN-001` | No prophylactic antibiotics | full text located and compared, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-PAN-002` | Empiric antibiotics for infected necrotizing pancreatitis | full text located and compared, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-PAN-003` | Cholecystectomy during the index admission (mild biliary pancreatitis) | full text located and compared, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-PAN-004` | ERCP only for cholangitis or biliary obstruction | full text located and compared, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-PAN-005` | Parenteral nutrition only as a last resort | full text located and compared, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-DIV-001` | No routine antibiotics when uncomplicated and low risk | abstract only, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-DIV-002` | Colonoscopy after complicated diverticulitis | abstract only, 2026-10-21 | [ ] | [ ] | [ ] | |
| `R-DIV-003` | Colonoscopy suggested after uncomplicated diverticulitis in selected patients | abstract only, 2026-10-21 | [ ] | [ ] | [ ] | |

**Version 2.0 replaced 1.0 (2019-2020 sources). Earlier ticks applied to the old rules and were reset.**

**When every box in the first two columns is ticked:** tag the commit `rules-v2.0-signed-off` and do not edit the catalog afterwards without bumping `CATALOG_VERSION`. The clinical reviewer column stays empty if no clinician is available; say so in the report.
