# Neurosymbolic Verification of LLM-Generated Clinical Discharge and Treatment Plans

DATA 298A (MSDA Project I) · Team 6 · Section 22 · Topic 12

Language models now draft discharge and treatment plans, and the plans read well even when they are unsafe: a plan can discharge a patient before required labs return, or order a contraindicated medication, and still look reasonable. This project builds a **checker that verifies an LLM-generated care plan against rules written by the team (not by the model) before anyone acts on it.** The checker turns each plan into logic, tests it with an SMT solver (Z3), and, when a plan fails, names the broken rule.

> **Scope:** a single hospital-encounter setting. This is an experimental verification framework, not a clinical decision support product. "Valid" means a plan complies with our formal rules; it does not prove the plan is clinically correct.

## Approach

```
clinical case  ->  LLM drafts a plan  ->  plan parsed into a structured form
                                              |
                       team-written rule set -+-> Z3 verifier -> valid / invalid + violated rule ID
                                                                      |
                                                  (298B) counterexample fed back to the LLM for repair
```

Four models are built and compared on the same benchmark and splits:

| Model | Idea | Phase |
|---|---|---|
| **A** | LLM generates discharge/treatment plans directly | 298A |
| **B** | LLM translates goals and clinical notes into formal specifications | 298B |
| **C** | LLM generation with a solver in the loop: the solver names the broken rule and returns it for repair | 298B |
| **D** | LLM paired with a classical PDDL planner | 298B |

**Baseline (separate from the four models):** we reproduce Hager et al. (2024), Fig. 3, where the best open LLM (OASST 70B) reaches 54.9% mean diagnostic accuracy on the autonomous MIMIC-CDM task (2,400 cases). That number measures *diagnosis*, so it is **not directly comparable** with our plan-validity metric.

## Evaluation

| Metric | Role |
|---|---|
| Plan validity rate | Primary: share of plans that satisfy the rule set |
| Constraint-violation escape rate | Secondary: invalid plans that the verifier lets through |
| Repair success rate, translation fidelity, solver cost | Secondary (targets set before the metrics are frozen) |

**Target:** validity ≥ 0.85 and escape rate ≤ 0.05 on a fixed 100-case held-out split.

## Data and access

| Dataset | Version | Role |
|---|---|---|
| [MIMIC-IV](https://physionet.org/content/mimiciv/3.1/) | v3.1 | admissions, diagnoses, labs, medications, source records |
| [MIMIC-IV-Ext-CDM](https://physionet.org/content/mimic-iv-ext-cdm/) | v1.1 | 2,400 curated cases across four abdominal pathologies (Hager et al.) |

Both are **credentialed PhysioNet data** (PhysioNet Credentialed Health Data License 1.5.0). **No patient data is stored in this repository.**

- Each person needs their own PhysioNet credentialing and signed data use agreement; data is never shared between people.
- Data lives outside the repo (default `~/data/mimic`, override with the `MIMIC_DIR` environment variable). `.gitignore` blocks data files.
- MIMIC text must not be sent to hosted LLM APIs (see PhysioNet's [LLM guidance](https://physionet.org/news/post/llm-responsible-use/)); use local models or synthetic examples.
- The repo contains only code, configuration, dataset manifests, case-ID split lists, synthetic examples and aggregate results.

## Project status

**DATA 298A (this semester):** verifier, team-written rule set, evaluation harness, benchmark, Model A, and the reproduced Hager et al. baseline.
**DATA 298B (next semester):** Models B, C and D, the full four-model comparison, expanded ablation and failure study, and a secondary case study on software deployment pipelines (which rules transfer, which do not).

| Workstream | State |
|---|---|
| Data access, manifests, integrity checks (SHA256) | done |
| Data cleaning, validation checks, EDA, fixed stratified splits (1,840 / 460 / 100, seed 298) | done, being merged into this repo |
| Rule catalog and synthetic valid/invalid cases | in progress |
| Verifier (Z3), evaluation harness | in progress |
| Model A, baseline reproduction | planned (needs GPU access) |

## Planned repository layout

```
configs/            run configurations, seeds, rule-set versions
data/               see data/README.md (data is gitignored); data/splits holds case IDs only
docs/               design notes, data collection steps, decisions
notebooks/          data pipeline demo (extraction, cleaning, EDA, splits)
results/            logged runs and figures
scripts/            one-command entry points (e.g. data_demo.py)
src/clinverify/
    data/           loading, cleaning, validation, splits and leakage checks
    rules/          team-authored clinical rule catalog
    verifier/       plan -> logic -> Z3 check, names the violated rule
    models/         Model A (298A); Models B, C, D (298B)
    baseline/       Hager et al. 2024 reproduction
    eval/           evaluation harness and metrics
tests/              unit tests on synthetic data
```

## Reproducibility

- Python 3.10+ with a pinned environment (in progress).
- Fixed, versioned splits; every reported run records its configuration and random seed.
- The data pipeline runs end to end with `python scripts/data_demo.py all` once the data is downloaded to `MIMIC_DIR`.
- Goal: another person can clone the repo and reproduce each reported result without help.

## Team

| Member | Current focus |
|---|---|
| Akash Senthilkumar | data access, manifest, ingestion |
| Ritika Mukesh Neema | Model A specification |
| Rajesh Paruchuri | metrics, splits, baseline protocol |
| Sneha Singh | rule catalog and synthetic cases |
| Shruthi Thirukumaran | environment, CI, reproducibility |

Task tracking: [Linear board](https://linear.app/298a-team-6-neurosymbolic/team/T6/overview) (two-week cycles, one assignee per issue, linked artifacts on closed issues).

## Key references

- Hager, P., et al. (2024). Evaluation and mitigation of the limitations of large language models in clinical decision-making. *Nature Medicine*, 30, 2613–2622. https://doi.org/10.1038/s41591-024-03097-1
- Valmeekam, K., et al. (2023). PlanBench: An extensible benchmark for evaluating large language models on planning and reasoning about change. *NeurIPS 36*. https://arxiv.org/abs/2206.10498
- Kambhampati, S., et al. (2024). Position: LLMs can't plan, but can help planning in LLM-Modulo frameworks. *ICML*, PMLR 235. https://proceedings.mlr.press/v235/kambhampati24a.html
- de Moura, L., & Bjørner, N. (2008). Z3: An efficient SMT solver. https://doi.org/10.1007/978-3-540-78800-3_24
- Johnson, A. E. W., et al. (2023). MIMIC-IV, a freely accessible electronic health record dataset. *Scientific Data*, 10, 1. https://doi.org/10.1038/s41597-022-01899-x
