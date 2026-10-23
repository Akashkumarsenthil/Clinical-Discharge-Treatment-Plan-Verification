# Rule catalog sign-off (v2.1)

Edit this page directly on GitHub. The rules and their sources are listed in [rule_catalog.md](rule_catalog.md); the code is `src/clinverify/rules/catalog.py`.

The column "Assistant's check" records that the AI assistant that drafted the rules located each cited statement in the open-access guideline text and compared the rule with it. It is **not** a human sign-off and does not replace the next columns.

**How to sign off a rule**
1. Open the guideline cited for the rule (the source and statement number are in the rule table) and read that statement, not only the summary.
2. Check that the rule's condition, threshold and wording match the statement. Read the rule's violation message too.
3. Tick `[x]` and add your initials and date in the Notes column.
4. If you **cannot** tick it, leave the box empty and write the reason in Notes (for example: "statement not found", "threshold differs", "needs clinician", "condition unclear"), then tell the rule author.

**Second-reviewer record (human input only)**

- Reviewer name/initials: _pending_
- Review date: _pending_
- Catalog version: **2.1**
- Independently check the cited recommendation, its conditions/exceptions, code and examples. Do not copy the assistant's check or the first reviewer's ticks.
- Check especially: R-APP-003 requires appendectomy and only checks an upper bound (zero days passes); advisory findings do not block validity; missing facts are not negative facts; scope-only acceptance is not a clinical check.
- Record exactly what was accessible for abstract-only sources. Do not claim full-text review when only the abstract was read. Resolve material uncertainty or record the limitation.
- Run `python -m pytest tests/test_catalog.py tests/test_evaluation_protocol.py`. Tests do not replace human source review or clinical validation.
- For accepted rows, tick **Second team member** and add your own initials/date to Notes. Clinical/domain review stays separate and blank if no such reviewer participated.

The assistant has not filled second-reviewer or clinical-reviewer boxes. The metric-definition freeze in [metrics.md](metrics.md) is separate from rule approval and the deferred fact audit.

| Rule | Name | Assistant's check of the source | First reviewer read against source | Second team member | Clinical / domain reviewer | Notes (initials, date, reasons) |
|---|---|---|---|---|---|---|
| `R-GEN-001` | Diagnosis is covered by the rules | n/a (scope guard, no guideline) | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-APP-001` | Antibiotic prophylaxis for appendectomy | full text located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-APP-002` | No postoperative antibiotics when uncomplicated | full text located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-APP-003` | Postoperative antibiotic course of at most 3 days (complicated) | abstract only, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-23 (re-read for v2.1: applies only with an appendectomy, upper bound only) |
| `R-PAN-001` | No prophylactic antibiotics | full text located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-002` | Empiric antibiotics for infected necrotizing pancreatitis | full text located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-003` | Cholecystectomy during the index admission (mild biliary pancreatitis) | full text located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-004` | ERCP only for cholangitis or biliary obstruction | full text located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-PAN-005` | Parenteral nutrition only as a last resort | full text located and compared, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-DIV-001` | No routine antibiotics when uncomplicated and low risk | abstract only, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-DIV-002` | Colonoscopy after complicated diverticulitis | abstract only, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |
| `R-DIV-003` | Colonoscopy suggested after uncomplicated diverticulitis in selected patients | abstract only, 2026-10-21 | [x] | [ ] | [ ] | SS, 2026-10-21 |

**Version 2.0 replaced 1.0 (2019-2020 sources). Earlier ticks applied to the old rules and were reset.**

**Version 2.1** changes how rules are applied, not what the other rules say: a rule whose condition fact is known to be false is "not applicable" instead of passing, R-DIV-003 no longer waits for screening history when alarm symptoms are known, and R-APP-003 now applies only with an appendectomy (its row was reset above).

**When every rule's First reviewer and Second team member boxes are ticked, with human initials/dates recorded:** tag the commit `rules-v2.1-signed-off` and do not edit the catalog afterwards without bumping `CATALOG_VERSION`. The clinical reviewer column stays empty if no clinician is available; say so in the report. Do not create a signed-off tag while required human review is pending.
