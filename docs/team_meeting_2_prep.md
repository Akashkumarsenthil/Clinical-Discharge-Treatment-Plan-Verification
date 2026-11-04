# Team Meeting 2: prep (demo script, deck notes, memo draft, Linear list)

Drafted 2026-11-03 from the repository and the 298A templates (Template 7, Template 8). Names, Linear links and the commit SHA are left for the team. Every number below was read from a file or a run in this repository; the source is named next to it.

## 1. Where we stand against the template

| Template item | State | Evidence |
|---|---|---|
| Slide 1 data summary | ready | `docs/data_engineering.md`, `docs/split_leakage_check.md` |
| Slides 2 to 4 models, architecture, comparison | ready (draft, team to confirm "where each model loses") | `docs/workbook2_model_development.md` 4.1 to 4.3 |
| Slide 5 evaluation | ready | `docs/metrics.md` (protocol v1.1) |
| **Slide 6 first model trained** | **gap**: Model A is prompted (Qwen2.5-14B through a local Ollama server), not trained. No learning curves exist | see section 5 |
| Slide 7 baseline reproduction | ready (reduced scale) | `docs/baseline_notes.md` |
| Slide 7 "model against the baseline, seeds, spread" | partly: Model A has validation-split plans from one seed. No test-split run (deliberately, see section 5) | `results/model_runs/` (gitignored) |
| ISA rows 1 to 7 | ready, rehearsal pending | section 2 |
| Checkpoint memo | draft below | section 4 |

## 2. ISA demonstration: run script

Run everything from the repository root in WSL, with `MIMIC_DIR` pointing at the real data (default `~/data/mimic`). Fill the "who" column.

| # | Show | Command or place | What to point at | Who |
|---|---|---|---|---|
| 1 | Transformations, before/after | `MIMIC_DIR=~/synthetic_mimic python scripts/data_demo.py all` (synthetic stand-in, safe on a shared screen) or notebook 3.4 | a raw row beside its transformed row, and the stated reason | [name] |
| 2 | Pipeline on a schedule | Windows Task Scheduler entry `ClinVerify-Pipeline`; `tail ~/data/mimic/warehouse/scheduler.log` | 9 runs recorded with trigger `scheduler` (`docs/scheduler_run_history.csv`, times in UTC): the first at 2026-11-01 22:33, then every 6 hours from 2026-11-02 04:00 to 2026-11-03 16:00, all `ok`; two runs after that failed (see section 4, "What did not work") and the last row (2026-11-04 05:41) is a manual test of the task command after the fix | [name] |
| 3 | Warehouse contents | `python -c` or DuckDB CLI on `~/data/mimic/warehouse/clinverify.duckdb`; `python scripts/run_pipeline.py --history` | schemas (raw, staging, mart, ops), row counts (2,400 cases) and the layer counts table | [name] |
| 4 | Monitoring: logs, status, retries, alerts | `scheduler.log`, `alerts.log`, `python scripts/run_pipeline.py --inject-fault --trigger demo-fault` | the fault run is rejected by the gate, exit 1, nothing published; the next normal run is `ok` | [name] |
| 5 | Prototype, live, audience picks the input | `streamlit run app/demo_app.py` | pick any validation case; saved plan or "Generate live with Model A" (1 to 3 s per case); edit the plan; "Inject a fault" | [name] |
| 6 | Clone-and-run | the README Quickstart in a fresh folder, with `python3.12 -m venv .venv` (Python 3.14 crashes pandas 2.2.3; checked 2026-11-03: on 3.12 all 142 tests pass and the synthetic demo and both `run_eval.py` runs exit 0) | tests pass; synthetic demo and `run_eval.py` run | [name] |
| 7 | Each member's Linear issues and PRs | Linear board, GitHub PRs #1 and #2 and others | each issue has an assignee and a linked artifact | all |

**Say before row 5:** the saved plans come from Qwen2.5-14B run locally; live generation calls the same local model (nothing leaves the machine); only validation cases are offered; the 100 test cases are held out. "Valid" means the plan complies with our formal rules, not that it is clinically correct. Rule review: first reviewer done, second reviewer and clinical review pending.

**Known facts about the prototype to be ready for:**
- Of the 460 saved validation plans, the verdicts are: valid and correct diagnosis 55; violated and correct 115 (mostly the cholecystitis scope guard R-GEN-001); insufficient information and correct 238; insufficient and wrong 42; valid but wrong diagnosis 2; violated and wrong 8. So the diagnosis is correct in 408 of 460 (88.7%), and only 55 plans (12.0%) end up fully accepted. That is the point of the project: the checker refuses to call a plan valid when the record cannot establish what a rule needs.
- Fresh-clone caveat: `results/model_runs/` is gitignored, so a fresh clone has no saved plans. The app says so and live generation still works if Ollama and `qwen2.5:14b` are installed. For row 6, run on the synthetic data, which does not need them.

## 3. Deck notes (8 slides, 17 + 3 minutes)

1. **Data summary.** 2,400 cases (Hager et al. Ext-CDM, four pathologies). Split v2, grouped by patient: 1,840 train, 460 validation, 100 test (40 appendicitis, 27 cholecystitis, 22 pancreatitis, 11 diverticulitis). Leakage story to tell: the first split (by admission) passed the admission check but failed the patient check (5 patients crossed splits), so v2 groups by patient. Source: `docs/split_leakage_check.md`.
2. **Model proposals.** A: LLM prompting. B: LLM translation plus a Z3 solver. C: LLM plus verifier feedback loop. D: LLM plus a classical planner. Baseline (Hager et al.) is separate from the four. Source: `docs/workbook2_model_development.md` 4.1.
3. **Supports and architecture.** Local only: WSL2, RTX 5060 Ti 16 GB, Ollama, Z3, DuckDB warehouse, Streamlit prototype, Windows Task Scheduler. The model architecture diagram is Mermaid in `docs/workbook2_model_development.md` (export it as an image for the slide); `docs/images/data_pipeline.png` covers the data side.
4. **Comparison and justification.** The table in 4.3, plus where each model would lose (draft; team confirms).
5. **Evaluation.** Metrics protocol v1.1 frozen 2026-10-23 (`docs/metrics.md`): diagnosis accuracy on all 100; checked acceptance on the 73 covered cases (the 27 cholecystitis cases have no treatment rules); joint success; seeds 298, 299, 300; no numeric target on the automatic acceptance rates.
6. **First model trained.** See section 5. Do not present a prompted model as a trained one.
7. **Baseline reproduction and first benchmark.**
   - Published: OASST 70B, autonomous task, mean diagnostic accuracy 54.9%.
   - Ours: Llama 3.1 8B Instruct, 4-bit, 400 cases (100 per pathology, seed 298), same framework at pinned commit `e1b4a52`, same evaluator. Mean 47.4% (appendicitis 74.7, cholecystitis 30.0, diverticulitis 37.0, pancreatitis 48.0).
   - Gap 7.5 points. Explanation: 8B 4-bit instead of 70B, one-sixth of the cases (about plus or minus 10 points per pathology), newer MIMIC versions. Appendicitis is easiest in both; the order of the other three differs.
   - Say what was changed in the framework and why (`docs/baseline_notes.md`).
   - First benchmark (validation split, 460 cases, seed 298, `docs/validation_summary.json`, produced by notebook 4.4.5): majority class accuracy 0.400, joint success 0.104; Model E (a reference model; the team has not decided its status, it is not one of the four models; TF-IDF + logistic regression) accuracy 0.887, macro F1 0.853, checked acceptance 0.1875 (63 of 336), joint success 0.163; Model A (Qwen2.5-14B) accuracy 0.887, macro F1 0.855, checked acceptance 0.1458 (49 of 336), joint success 0.120. Model A's plan verdicts: 57 valid, 123 violated, 280 insufficient information. Say it plainly: the prompted LLM does not beat the cheap text classifier on diagnosis, and does worse on checked acceptance. Only one seed so far (temperature 0), so there is no spread to report. Read validity_rate (0.124 = 57 valid plans of 460) with care: it is not a failure rate, because 280 of the 460 plans are "insufficient information" (the record cannot establish a fact a rule needs) and 106 of the 169 rule violations are the cholecystitis scope guard R-GEN-001. R-APP-003 is advisory; its 46 flags do not make a plan invalid. Checked acceptance (0.146) and joint success (0.120) are the numbers to quote, with the 280 stated.
   - Model A against the baseline: not comparable yet (different task: plan validity, not only diagnosis). On validation, Model A's diagnosis is correct in 88.7% of 460 cases, but those cases are not the baseline's cases, so do not put the two numbers in one chart without saying so.
8. **Next, risks, asks.** 298B: Models B, C, D; ablation; failure study; independent plan adjudication (the 0.85 goal stays unassessed without labels); demographic breakdown of results. Risks: second rule review and clinical review pending; test-set discipline; fine-tuning compute. Asks: reviewer for rules, decision on slide 6.

## 4. Checkpoint memo draft (Template 8, 1 to 2 pages)

**[Team 6, Section 22, Topic 12] · Checkpoint: Team Meeting 2**
**Repository at the presentation commit:** [URL with commit SHA] · **Linear board:** [URL]

**1. What we said we would do.** [Copy the Team Meeting 1 commitments here.] Our working list from the cycle plan: reproduce the baseline (at reduced scale if needed), run Model A, show a live prototype, run the pipeline on a schedule with monitoring, and have rule review under way.

**2. What we actually did.**
- Baseline: ran the Hager et al. autonomous framework with Llama 3.1 8B (4-bit) on 400 cases. Mean diagnostic accuracy 47.4% against 54.9% published. All deviations are listed in `docs/baseline_notes.md`. [PR link]
- Model A: Qwen2.5-14B plans for all 460 validation cases (2,268 ms per case, measured when the plans were generated and recorded in results/workbook2/4_4_model_comparison.csv, which is not committed; the validation_summary.json speed fields are empty because the notebook reused the saved plans), verified with the Z3 catalog v2.1 (12 rules). [link]
- Live prototype: Streamlit app, validation cases only, editable plans, fault injection. [PR #1 link]
- Pipeline: scheduled every 6 hours from 2026-11-02 (UTC), with a retry and an alert log; every run that started was `ok`, but two scheduled runs did not start (see "What did not work"). Evidence: `docs/scheduler_run_history.csv` (counts and timestamps only, exported from the warehouse run log), `python scripts/run_pipeline.py --history`, `scheduler.log` and `alerts.log` in the warehouse folder next to the database, the wrapper is `scripts/scheduled_pipeline.sh`, and the Windows task is `ClinVerify-Pipeline` (screenshot of Task Scheduler to attach). [commit link]
- Workbook 2 additions: strict against sensitivity facts, population and coverage gaps, rule check. [PR #2 link]

**3. What did not work.**
- The scheduled pipeline silently stopped for about 13 hours on 2026-11-03: `scripts/scheduled_pipeline.sh` was committed without the executable bit, and a git branch switch removed it from the working copy, so Windows Task Scheduler got "Permission denied" (task result 1) and nothing was logged by the script. We found it while collecting evidence, restored the bit (`git update-index --chmod=+x`, so the file is mode 755 in the repository) and the task command now exits 0. Lesson: the alert log only catches failures inside the script, not a script that never starts.
- (Evidence for the baseline points below: `docs/baseline_notes.md`, "Operational notes" and "Environment". The baseline run logs are on Akash's machine under `~/baseline` and contain MIMIC text, so they are not committed. What survives without patient text: the resume logs' timestamps, 16:15, 16:33 and 18:19 on 2026-11-01, which show the runs were restarted, and `~/baseline/subset_status.txt` with exit 0 for all four pathologies. The 4-hour timeout (exit 124) was in a log that was overwritten when the job was relaunched, so there is no preserved line for it; keep the claim only if the team accepts that.) The first baseline run stopped at a 4-hour timeout we had set by mistake; a WSL restart killed a second run partway. We added a resume script that reruns only unfinished cases.
- The framework's pinned CUDA 11 stack does not run on the RTX 5060 Ti (Blackwell), so we ran a newer stack with the GPU-specific loaders stubbed out, which is why the run is not exactly the authors' setup.
- The 70B models do not fit in 16 GB, so we could not reproduce the published 54.9% exactly. One appendicitis case could not be scored because its reference data holds a missing value.
- Model A is prompted, not trained. We did not fine-tune it in this period.

**4. What we will show today.** The seven ISA rows in section 2 above, in order, with the names filled in.

**5. Anything mocked or incomplete.**
- Not mocked: the pipeline, the warehouse, the verifier and the live generation all run on real data on our machine.
- Incomplete: no trained model yet (slide 6); no formal test-split results; second rule review and clinical review pending, so the catalog is implemented and tested but not clinically validated; baseline is a reduced-scale reproduction; independent adjudication of plans has not started.

**6. Individual contribution this period.**

| Member | Issues closed | Labels | Artifact links |
|---|---|---|---|
| [name] | [n] | [ ] | [ ] |
| [name] | [n] | [ ] | [ ] |
| [name] | [n] | [ ] | [ ] |
| [name] | [n] | [ ] | [ ] |

## 5. Decisions that are the team's, not mine

1. **Slide 6 and Model A.** The template wants a first trained model with learning curves and compute, and says a hosted API call is not one of the four models. Model A runs a local open model by prompting, with no training. Options: (a) say so on slide 6 and show the compute actually used (generation time, GPU, tokens) and the validation run as the first benchmark, then ask the instructor in advance whether that is acceptable; (b) fine-tune Model A with a small adapter (QLoRA) on the 1,840 training cases. (b) was ruled out earlier when the team was aiming for November 4. With Team Meeting 2 on November 12 it needs re-estimating (adapter training on a 16 GB GPU, then a validation run to check it), and the training target (verifier-accepted plans or diagnosis only) is itself a design decision. Decide by about November 6 whether to attempt it; otherwise take option (a).
2. **The formal test run.** `docs/metrics.md` says to commit the frozen record before formal held-out runs, that decoding settings are chosen and recorded before the first formal test, and that an eligibility manifest for the 73 covered cases should be frozen before Model A generation. Decoding is greedy (temperature 0), so seeds 298, 299 and 300 would give identical output and a standard deviation of zero unless temperature is raised. That needs deciding first, because the 100 test cases can only be used once. Recommendation: do not run the test split for the meeting; show validation results and the plan for the formal run.
3. **Naming.** The team has been calling the baseline "Model A". The template has the baseline outside the four models. Use "baseline" for Hager et al. and "Model A" for the plain LLM plan generator, as in the report.

## 6. Linear issues to enter (draft)

One team, one named assignee per issue, a linked artifact on every closed issue. Labels and estimates are suggestions; match your board's labels.

| Title | Suggested label | Estimate | Cycle | Assignee | Artifact |
|---|---|---|---|---|---|
| Reproduce Hager et al. autonomous baseline at reduced scale (Llama 3.1 8B, 400 cases) | Baseline | 5 | 5 | [name] | `docs/baseline_notes.md`, PR #1 |
| Convert MIMIC-IV-Ext-CDM for the Hager framework and fix environment for Blackwell GPU | Baseline | 3 | 5 | [name] | `docs/baseline_notes.md` |
| Write resume script and scorer for the baseline run | Baseline | 2 | 5 | [name] | `docs/baseline_notes.md` |
| Explain the skipped appendicitis case in the baseline scoring | Baseline | 1 | 5 | [name] | `docs/baseline_notes.md` |
| Live prototype: verify Model A plans, edit plan, inject fault | Prototype | 5 | 5 | [name] | PR #1, `app/demo_app.py` |
| Scheduled pipeline wrapper with retry and alert log; create the Windows task | Pipeline | 3 | 5 | [name] | PR #1, `scripts/scheduled_pipeline.sh` |
| Workbook 2 notebook: strict vs sensitivity, population gaps, rule catalog check | Report | 3 | 5 | [name] | PR #2 |
| Second reviewer for the rule catalog | Rules | 3 | 5 | [name] | `docs/rule_second_review.md` |
| Rehearse the seven ISA demo rows | Demo | 2 | 5 | all | rehearsal notes |
| Decide slide 6 approach and fine-tune scope for Model A | Model A | 2 | 5 | [name] | decision note |
| Formal Model A test run (seeds 298 to 300) after protocol checks | Model A | 3 | 6 | [name] | `results/` (gitignored), notebook |
