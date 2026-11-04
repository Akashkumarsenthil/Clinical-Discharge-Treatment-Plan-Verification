# Team Meeting 2 — Professor track, slides 1–4

Author: Shruthi Thirukumaran (ST). Reviewer: Rithika (`RitikaMNeema`).
Work item: [T6-182](https://linear.app/298a-team-6-neurosymbolic/issue/T6-182).

Text and speaker notes for Template 7A. These are the first four slides of the
eight-slide, 17-minute presentation, followed by 3 minutes of questions. Suggested
time for this contribution: 7 minutes 30 seconds; leave 9 minutes 30 seconds for
slides 5–8. Timing is a rehearsal allocation, not a measured result. Rithika owns
the deck assembly. This file does not supply slides 5–8, a deck, or the memo.

## Slide 1 — Data summary

### On-slide text

**Collection → preprocessing → transformation → patient-grouped splits**

- PhysioNet: MIMIC-IV v3.1 + Ext-CDM v1.1; **2,400 cases**, four abdominal pathologies.
- Remove exact duplicates; keep missing laboratory reference ranges as **unknown**.
- Normalize text; parse lab values/units and low/normal/high/unknown flags.
- Split v2, seed 298: **1,840 train / 460 validation / 100 test**.
- Class imbalance: appendicitis **957** versus diverticulitis **257** (about **3.7×**).
- Leakage check: **0 shared admissions; 0 patients across splits** in v2.

Small footer: Test mix = 40 appendicitis / 27 cholecystitis / 22 pancreatitis / 11 diverticulitis.

### Speaker notes — approximately 1 minute 45 seconds

We use the curated Ext-CDM cases alongside MIMIC-IV. The four conditions are
appendicitis, cholecystitis, pancreatitis and diverticulitis. Each member needs
their own credentialed access; the repository contains code, IDs and aggregate
results rather than clinical records.

The pipeline verifies file integrity and links encounter IDs before cleaning.
It removes exact duplicate rows—75 in the documented run. Missing lab reference
ranges remain unknown; we do not invent values to make the data complete. Text
normalization and numeric/unit parsing make the same inputs usable by the local
model and downstream checks.

The split is stratified by pathology and groups all admissions of the same
patient. Our original admission-only split had no duplicate admission IDs but
allowed five patients to cross splits, including one across train and test.
Version 2 fixes this: both admission and patient overlap are zero. The test set
contains 100 encounters, and five test encounters changed between v1 and v2.

Appendicitis is about 3.7 times as frequent as diverticulitis, so overall metrics
need per-pathology results beside them. The zero-overlap result establishes
separation between these splits; it is not a claim that every possible source
of leakage or bias has been ruled out.

### Repository sources

- [Data engineering, §§3.1–3.6](../docs/data_engineering.md): versions, size, cleaning, transforms, imbalance and split procedure.
- [Patient-level leakage check](../docs/split_leakage_check.md): v1 failure, v2 result, test mix and changed membership.
- [Meeting preparation, §3](../docs/team_meeting_2_prep.md#3-deck-notes-8-slides-17--3-minutes): deck scope and data summary.

## Slide 2 — Four model proposals

### On-slide text

| Model / phase | Concept and input features | Architecture / learning status |
|---|---|---|
| **A — 298A, implemented** | Generate a plan from history, exam, labs, microbiology and imaging | Local pretrained LLM → structured plan → Z3 check; prompting, **no project fine-tuning** |
| **B — 298B, proposed** | Translate clinical text and goals into a formal specification | LLM translator + deterministic solver; training procedure not specified yet |
| **C — 298B, proposed** | Use the case plus named rule violations as repair feedback | LLM generation ↔ verifier feedback; training procedure not specified yet |
| **D — 298B, proposed** | Translate the case using a clinical domain model | LLM + classical PDDL planner; domain and training procedure not specified yet |

**Hypotheses:** direct generation vs. formal reasoning vs. feedback repair vs. explicit action planning.

Footer: The reproduced Hager baseline is a separate reference, **not a fifth entry in A–D**.

### Speaker notes — approximately 2 minutes

The project proposes four methods. Only Model A belongs to the current 298A
implementation; Models B, C and D are later 298B work.

Model A uses local Qwen2.5:14b through Ollama. Its current implementation supplies
the allowed clinical information together, with fixed input limits, and requests
schema-constrained JSON. The verifier checks the output afterward; there is no
automatic repair loop in A. No model is fine-tuned by this implementation.

The hypotheses distinguish the methods, rather than four different diagnostic
labels or four trained classifiers. For A, we establish what direct prompting
can achieve before adding a reasoning mechanism. For B, we hypothesize that a
faithful formal translation lets a solver make the reasoning explicit. For C,
we hypothesize that returning named rule failures helps the LLM repair a plan.
For D, we hypothesize that explicit actions and preconditions let a planner
construct plans that satisfy the encoded domain.

These are hypotheses to test, not findings that B, C or D already outperform A.
Their translation, repair and planning procedures are proposed inference
mechanisms. The repository does not specify project training algorithms or
training results for them, so we should not invent any.

The Hager autonomous diagnostic baseline remains outside these four models.
In particular, its step-by-step information requests should not be presented
as Model A's current input procedure. Section 4.3 still contains that older
input description; the implemented full-information path is documented in
`src/clinverify/models/model_a.py`.

### Repository sources

- [Model proposals, §4.1](../docs/workbook2_model_development.md#41-model-proposals): A–D concepts and semester scope.
- [Model A implementation](../src/clinverify/models/model_a.py): full-information setting, input limits, local client, prompt and JSON schema.
- [Meeting preparation, §5](../docs/team_meeting_2_prep.md#5-decisions-that-are-the-teams-not-mine): prompted versus trained model and baseline naming.

## Slide 3 — Platform and architecture

### On-slide text

**Local execution:** WSL2 · RTX 5060 Ti, 16 GB · Ollama / Qwen2.5:14b.

**Tools:** Python 3.12/3.13 · pandas/NumPy · DuckDB · Z3 · Streamlit · pytest/GitHub Actions.

**Insert the architecture PNG from T6-181 / PR #10:**
[`docs/images/model_architecture.png`](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/blob/shruthi/t6-181-model-architecture/docs/images/model_architecture.png).
After PR #10 merges, use `docs/images/model_architecture.png` from `main`.

**Trust boundary:** case facts judge the plan; they are never supplied to the LLM.

Footer: Dashed model paths are proposed for 298B. Rule acceptance does not establish clinical safety or completeness.

### Speaker notes — approximately 1 minute 45 seconds

Follow the implemented path from left to right in the diagram. Credentialed data
stays outside the repository. The pipeline cleans and transforms the data; the
DuckDB warehouse provides raw, staging, mart and operations layers. The fixed
patient-grouped splits determine which cases are used.

The local LLM receives the permitted case inputs and generates a structured
diagnosis and treatment plan. A parser checks the plan's representation and
attaches independently derived record facts. The Z3 verifier applies the
team-written catalog, currently version 2.1 with 12 rules.

Case facts come from ICD titles and discharge evidence for judging only. Model
output cannot supply or override those facts. A missing required fact is an
unknown, rather than an automatic pass. Advisory findings are reported separately
from blocking violations.

The evaluation harness aggregates results under protocol v1.1. Only code,
documentation, case IDs and aggregate results go to GitHub. The dashed repair
path belongs to proposed Model C, not today's Model A. Model B's solver and
Model D's planner are also future extensions.

Streamlit is the current validation-case prototype. Windows Task Scheduler runs
the warehouse pipeline; pytest and GitHub Actions check the code. Rule review
and clinical validation must not be implied by successful software tests.

### Repository sources

- [Platform and architecture, §4.2](../docs/workbook2_model_development.md#42-model-supports-platform-and-architecture); image supplied by [PR #10](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/10).
- [Meeting preparation, §§2–3](../docs/team_meeting_2_prep.md): hardware, local tools, prototype and scheduling.
- [Warehouse implementation](../src/clinverify/warehouse.py): raw/staging/mart/ops layers.
- [Model-output contract](../docs/model_a_plan_format.md): trusted record facts versus model content.
- [Requirements](../requirements.txt) and [CI workflow](../.github/workflows/tests.yml): environment and test tooling.

## Slide 4 — Model comparison and justification

### On-slide text

| Model | Problem / features | Approach type | Strength / when to choose | Expected failure condition |
|---|---|---|---|---|
| **A** | Direct plans from clinical case inputs | LLM prompting | Simple reference method with no repair or formal-translation stage | A plan needs correction that one-shot generation does not provide |
| **B** | Formal reasoning from case text and goals | LLM + solver | Explicit reasoning when the translation faithfully represents the case | Incorrect translation or an inadequate formal language |
| **C** | Repair plans using case text and rule feedback | LLM + verifier loop | Useful when actionable rule failures can guide revisions | Unknown facts, uncovered errors, or costly repeated calls |
| **D** | Sequences of care actions from a case and domain | LLM + classical planner | Useful when actions and preconditions are expressible in a domain | Missing or inaccurate clinical PDDL domain |

**Current choice:** A as the implemented reference. **No preferred winner established** for A–D; B–D comparisons are proposed.

### Speaker notes — approximately 2 minutes

This comparison describes design tradeoffs. It is not a table of measured
performance for four completed models.

Model A is the simplest method and provides the reference implementation.
It could lose when a correctable plan error survives direct generation, because
the method does not receive feedback or revise its answer. That does not prove
that any of the proposed alternatives will perform better.

Model B moves reasoning into a formal solver. Its advantage depends on translation
fidelity: the solver can reason correctly about the wrong formal specification.
Long or messy notes are therefore a proposed stress condition.

Model C uses the existing rule catalog as feedback. It is most useful when the
verifier can identify a concrete problem that the model can change. Missing
record evidence remains unknown; a repair loop cannot create that evidence, and
the catalog cannot detect errors outside its coverage. Each revision also adds
generation and solver work.

Model D is attractive where care can be represented by actions, preconditions
and effects. The repository does not yet contain the required clinical PDDL
domain. Any validity claim would be relative to that domain, not a guarantee
of clinical correctness.

The intended comparison uses the same fixed cohort and verifier while changing
the method. We have not selected an overall winner. Translation fidelity for B
and repair success for C remain later-semester evaluation work. The Hager
baseline is a separate diagnostic reference, and its diagnostic accuracy must
not be equated with plan validity.

### Repository sources

- [Comparison and justification, §4.3](../docs/workbook2_model_development.md#43-comparison-and-justification): strengths, limitations and draft failure conditions.
- [Metric definitions](../docs/metrics.md): common cohort, coverage limits, and later-semester translation/repair metrics.
- [Model proposals, §4.1](../docs/workbook2_model_development.md#41-model-proposals): phase and architecture distinctions.

## Handoff checks

- Keep slides 1–4 in this order; do not add a title slide that shifts Template 7A numbering.
- Use the PNG from PR #10 only after checking that the image is the reviewed version.
- Preserve the implemented/proposed labels, local-data boundary and baseline distinction.
- The suggested speaking times sum to 7:30; rehearse them with Rithika before deck assembly.
- Numerical statements above come from the linked repository sources. No new benchmark was run for this text.
