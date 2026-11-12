# Team 6, Section 22, Topic 12 · Checkpoint memo: Team Meeting 2

**Project:** Neurosymbolic Verification of LLM-Generated Clinical Discharge and Treatment Plans
**Repository at the memo commit:** [`04acfc4`](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/tree/04acfc407aed26d92af30297ddbcd4c1c3f1956f) (`main`, 2026-11-04). Replace with the presentation-day commit before submitting.
**Linear board:** https://linear.app/298a-team-6-neurosymbolic/team/T6/all
**Template:** 8. Drafted from `docs/team_meeting_2_prep.md` section 4 · Linear: T6-186.

## 1. What we said we would do (Team Meeting 1, October 8)

| Commitment (TM1 deck, slides 8 and 10) | Target | Status now |
|---|---|---|
| Rule set v1, high-severity rules first | Oct 22 | Catalog v2.1, 12 rules; first review done, second review assigned ([PR #9](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/9)) |
| Z3 verifier and evaluation harness | Nov 5 | Done; protocol v1.1 frozen Oct 23 (`docs/metrics.md`) |
| Model A plans on validation cases | Nov 5 | Done: 460 validation plans, seed 298 ([PR #6](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/6)) |
| Team Meeting 2 demo: Model A through the harness | Nov 12 | Ready; rehearsal pending |
| Reproduce the Hager et al. baseline | late Nov | Reduced-scale run done (section 2) |
| 100-case test run and failure study | Nov – early Dec | Not started, on purpose (section 5) |
| Open item: GPU or HPC for the 70B baseline | — | Local RTX 5060 Ti 16 GB; 70B does not fit, so the baseline ran at reduced scale |
| Open item: which local model runs Model A | — | Qwen2.5-14B through a local Ollama server |
| Validity ≥ 0.85 on 100 test cases (TM1 slide 2) | — | Changed in protocol v1.1: kept only as a research goal for independently adjudicated plans, because the automatic ceiling is 47/73 (`docs/evaluation_feasibility.md`) |

## 2. What we actually did

- **Baseline:** ran the Hager et al. autonomous framework with Llama 3.1 8B (4-bit) on 400 cases. Mean diagnostic accuracy 47.4% against 54.9% published. All deviations are in `docs/baseline_notes.md`. [PR #1](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/1)
- **Model A:** Qwen2.5-14B plans for all 460 validation cases (2,268 ms per case, measured at generation time; the per-case timing file is local, not committed), verified with the Z3 catalog v2.1 (12 rules). [PR #6](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/6), generation CLI [PR #12](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/12)
- **Live prototype:** Streamlit app (`app/demo_app.py`), validation cases only, editable plans, fault injection. [PR #1](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/1)
- **Pipeline and warehouse:** DuckDB warehouse (raw, staging, mart, ops) with a data-quality gate; scheduled every 6 hours from 2026-11-02 (UTC) with a retry and an alert log. Every run that started was `ok`; two scheduled runs did not start (section 3). Evidence: `docs/scheduler_run_history.csv`, `python scripts/run_pipeline.py --history`, `scripts/scheduled_pipeline.sh` ([commit `32d19ef`](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/commit/32d19ef), PR #1), synthetic-data fix [PR #8](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/8).
- **Workbook 2 additions:** strict against sensitivity facts, population and coverage gaps, rule check. [PR #2](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/2), [PR #3](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/3), [PR #4](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/4)
- **Presentation material:** architecture figure [PR #10](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/10), slides 1–4 text [PR #11](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/11), slide 5 and the deck [PR #14](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/14) (T6-185).
- **Independent clone-and-run check:** README Quickstart run from a fresh clone on macOS 15.7.3, Python 3.12.2 and 3.13.7: every command exits 0, 159 tests pass. It found one bug: the two back-to-back `run_eval.py` runs wrote the same log file, so the first log was lost (fixed in [PR #13](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/13), T6-184).

## 3. What did not work

- **The scheduled pipeline silently stopped for about 13 hours on 2026-11-03.** `scripts/scheduled_pipeline.sh` was committed without the executable bit, and a branch switch removed it from the working copy, so Windows Task Scheduler got "Permission denied" and the script logged nothing. Found while collecting evidence; fixed with `git update-index --chmod=+x` (PR #6). Lesson: the alert log only catches failures inside the script, not a script that never starts.
- **Baseline runs were interrupted.** The first run stopped at a 4-hour timeout we had set by mistake [team to confirm: no preserved log line exists for the timeout, see `docs/baseline_notes.md`]; a WSL restart killed a second run partway. We added a resume script that reruns only unfinished cases.
- **The framework's pinned CUDA 11 stack does not run on the RTX 5060 Ti (Blackwell),** so we ran a newer stack with the GPU-specific loaders stubbed out; the run is not exactly the authors' setup.
- **70B models do not fit in 16 GB,** so the published 54.9% could not be reproduced exactly. One appendicitis case could not be scored because its reference data holds a missing value.
- **Model A is prompted, not trained.** We did not fine-tune it in this period.

## 4. What we will show today

The seven ISA rows in `docs/team_meeting_2_prep.md` section 2, in order: transformations; pipeline on a schedule; warehouse contents (Shruthi); monitoring; live prototype; clone-and-run (Ritika); each member's Linear issues and PRs. Presenters for the other rows: [team to fill].

## 5. Anything mocked or incomplete

- **Not mocked:** the pipeline, the warehouse, the verifier and live generation all run on real data on our own machines.
- **Incomplete:** no trained model yet (slide 6); no formal test-split results, on purpose: the 100 test cases are used once, after decoding settings are recorded, and greedy decoding would make seeds 298–300 identical unless the temperature changes; second rule review and clinical review pending, so the catalog is implemented and tested but not clinically validated; the baseline is a reduced-scale reproduction; independent adjudication of plans has not started, so the escape rate and the 0.85 research goal cannot be measured yet.

## 6. Individual contribution this period

Each member fills their own row (issue IDs from Linear, PR links from GitHub). Rows are not filled on anyone else's behalf.

| Member | Issues closed | Labels | Artifact links |
|---|---|---|---|
| Akashkumar Senthilkumar | [to be filled by Akash] | | |
| Rajesh Paruchuri | [T6-172](https://linear.app/298a-team-6-neurosymbolic/issue/T6-172), [T6-192](https://linear.app/298a-team-6-neurosymbolic/issue/T6-192) | data | Synthetic-data fix for `run_pipeline.py` and `--tables` for the warehouse demo row [PR #8](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/8). Workbook 2: checked the numbers in sections 3 and 4.1–4.4 against the repository sources ([T6-192](https://linear.app/298a-team-6-neurosymbolic/issue/T6-192)). Reviews: clone-and-run fix [PR #13](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/13), deck and slide 5 [PR #14](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/14), this memo [PR #15](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/15), case-facts second-reviewer assignment [PR #7](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/7). Case-facts second review accepted; pending until done on the authorised machine (`docs/case_facts_mapping.md`). |
| Ritika Mukesh Neema | [to be filled by Ritika] | | |
| Shruthi Thirukumaran | [T6-181](https://linear.app/298a-team-6-neurosymbolic/issue/T6-181), [T6-182](https://linear.app/298a-team-6-neurosymbolic/issue/T6-182), [T6-183](https://linear.app/298a-team-6-neurosymbolic/issue/T6-183) | — | Architecture figure [PR #10](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/10); slides 1–4 and notes [PR #11](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/11); guarded generation CLI and tests [PR #12](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/12). Adapter-training package [T6-187](https://linear.app/298a-team-6-neurosymbolic/issue/T6-187) / [PR #16](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/16) is in review; synthetic CPU checks passed, real training is not run. |
| Sneha Singh | T6-17, T6-22, T6-28, T6-96, T6-97, T6-98, T6-173, T6-174, T6-175, T6-177, T6-179, T6-180 | model, eval, data | PRs [#2](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/2), [#3](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/3), [#4](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/4), [#9](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/pull/9); [`docs/rule_catalog.md`](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/blob/main/docs/rule_catalog.md), [`docs/validation_summary.json`](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/blob/main/docs/validation_summary.json), [`docs/case_facts_mapping.md`](https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification/blob/main/docs/case_facts_mapping.md) |
