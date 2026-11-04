# Team Meeting 2 — Professor track, slide 5

Author: Ritika Mukesh Neema (`RitikaMNeema`). Reviewer: Rajesh Paruchuri.
Work item: [T6-185](https://linear.app/298a-team-6-neurosymbolic/issue/T6-185).

Text and speaker notes for slide 5 of Template 7A (evaluation methods). Slides 1–4
are in `slide_text_1-4.md` (Shruthi); slides 6–8 come from Akash. Suggested time:
2 minutes 15 seconds of the 9 minutes 30 seconds left for slides 5–8. Timing is a
rehearsal allocation, not a measured result. This slide describes methods only;
Model A's validation results belong on slide 7.

## Slide 5 — Evaluation methods

### On-slide text

**Since Team Meeting 1 (October 8)**

| Unchanged | Changed in protocol v1.1 (frozen October 23, before any Model A run) |
|---|---|
| Split sizes and seed: 1,840 / 460 / **100 test**, seed 298 (v2 now groups by patient, slide 1) | **0.85 is no longer an automatic target**: even a perfect diagnosis can get at most **47 of 73** covered test cases accepted (64.4%) |
| Escape rate **≤ 0.05**, on independently labelled plans | 0.85 kept as a **research goal** for independently human-adjudicated plans (not measurable yet) |
| Results reported per pathology, next to the overall number | New primary automatic metric: **checked acceptance**, descriptive, no target (ceiling 18 / 73) |

**Validation strategy**

1. Develop on the 460 validation cases only; the 100 test cases are used once.
2. Before the test run, record model digest, prompt hash, decoding settings and Git revision.
3. Three generation seeds (298, 299, 300): each run, plus mean and standard deviation.
4. Missing or unparseable plans stay in the denominator as failures.
5. Diagnosis scored on all 100; treatment on the 73 covered cases (27 cholecystitis have no rules).

**Error-analysis plan:** sort every plan that is not accepted into one bucket and report the counts:
wrong diagnosis · missing or malformed output · blocking rule violated (rule ID) · insufficient information (missing fact) · unsupported scope (cholecystitis).

Footer: Definitions: `docs/metrics.md`, protocol v1.1 (commit `84c3ca5`). Acceptance means compliance with our rules, not clinical correctness.

### Speaker notes — approximately 2 minutes 15 seconds

At Team Meeting 1 we promised plan validity of at least 0.85 and an escape rate
of at most 0.05 on 100 held-out cases. Here is what stayed and what changed.

Unchanged: the split sizes and seed, the escape-rate target and per-pathology
reporting. The split itself is now version 2, which keeps each patient in one
split, as on slide 1. Escape rate needs independently labelled plans, which we do
not have yet.

Changed: on October 23, before Model A produced a single plan, a feasibility check
showed that 0.85 cannot be reached automatically. Even with a perfect diagnosis and
the most favourable plan, only 47 of the 73 covered test cases can be accepted.
Protocol v1.1 keeps 0.85 only as a research goal for plans that independent human
reviewers adjudicate. The primary automatic metric is now checked acceptance: a
correct diagnosis and a plan accepted by at least one decided clinical rule, so
passing only the scope guard or an advisory rule earns no credit. Its ceiling is 18
of 73, and it has no target.

Validation strategy: we tune only on the 460 validation cases and use the 100 test
cases once, after recording the model digest, prompt hash, decoding settings and Git
revision. Formal runs use seeds 298, 299 and 300, reported per run with mean and
standard deviation. Missing or unparseable plans count as failures. Diagnosis is
scored on all 100 cases, treatment on the 73 covered ones, because cholecystitis has
no treatment rules.

Error analysis: every plan that is not accepted goes into one bucket: wrong
diagnosis, missing or malformed output, a blocking violation with its rule ID,
insufficient information with the missing fact, or unsupported scope. Counted per
bucket and per pathology, this separates model errors from gaps in the rules or the
record. The full failure study is 298B work.

Acceptance means compliance with our rules, not clinical correctness.

### Repository sources

- [Evaluation metrics v1.1](../docs/metrics.md): unchanged items, the v1.1 revision, exact definitions, repeat runs, unknown and advisory policy, escape rate.
- [Evaluation feasibility check](../docs/evaluation_feasibility.md): the 47/73 and 18/73 ceilings and why 0.85 was removed as an automatic target.
- [Meeting preparation, §3 slide 5](../docs/team_meeting_2_prep.md#3-deck-notes-8-slides-17--3-minutes): what the slide covers.
- [Workbook 2, §4.4](../docs/workbook2_model_development.md#44-evaluation-methods): metric table and carry-forward from Workbook 1.
- Team Meeting 1 deck, slide 2 (`Team6_Professor_Presentation.pptx`): the targets presented on October 8.

## Handoff checks

- Numbers on the slide come from the linked files; no new run was made for this text.
- One open decision affects the seeds line: decoding is greedy (temperature 0), so seeds 298–300 give identical output unless the temperature changes (`team_meeting_2_prep.md` §5, decision 2). If the team changes this before the meeting, update the notes.
- Do not move Model A validation numbers onto this slide; they are slide 7.
