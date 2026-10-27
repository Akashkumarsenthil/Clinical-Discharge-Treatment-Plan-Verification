# Second human review of rule catalog v2.1

**Status: still open.** A different team member from the first reviewer (SS) must complete this. The assistant must not tick **Second team member** in [rule_signoff.md](rule_signoff.md).

## Why this is still open

First-reviewer ticks already exist. Second review is an independent human check against the cited guideline statements. Filling those boxes without that person would falsify the sign-off record.

## What the second reviewer does

1. Open [rule_signoff.md](rule_signoff.md) and [rule_catalog.md](rule_catalog.md).
2. For each rule, open the cited source (full text when claimed; say so if only the abstract was available).
3. Confirm condition, threshold, advisory vs blocking, and violation message match the source.
4. Pay special attention to: R-APP-003 (appendectomy required; upper bound only); advisory findings do not block validity; missing facts ≠ negative facts.
5. Run: `python -m pytest tests/test_catalog.py tests/test_evaluation_protocol.py`
6. Tick **Second team member**, add your own initials and date in Notes, and fill Reviewer name/date at the top of `rule_signoff.md`.
7. When every Second team member box is ticked, tag `rules-v2.1-signed-off` (do not retag if the catalog changes without a version bump).

Clinical / domain reviewer stays blank if no clinician participates; say so in the report.

## Packet (ready for a human)

| Item | Location |
|---|---|
| Sign-off table | [rule_signoff.md](rule_signoff.md) |
| Rule text and sources | [rule_catalog.md](rule_catalog.md) |
| Code | `src/clinverify/rules/catalog.py` |
| Authoring notes | [rule_authoring.md](rule_authoring.md) |
