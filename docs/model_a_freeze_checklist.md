# Model A freeze checklist (before the formal test)

**Status:** not signed off. Nothing here is ticked. Each line needs a named person and a date from the team.

The test split (100 cases, 73 covered) stays untouched until every box below is ticked. Seeds are 298, 299 and 300. See [metrics.md](metrics.md) and [evaluation_protocol.json](evaluation_protocol.json).

## Decide and record

| # | Decision | Value to record | Who | Done |
|---|---|---|---|---|
| 1 | Model and quantisation | name and the Ollama digest the run prints (currently validation used qwen2.5:14b, 4-bit) | team | [ ] |
| 2 | Prompt | the `prompt_sha256` printed by `model_a.prompt_sha256()` | team | [ ] |
| 3 | Decoding | temperature 0, top_p 1, max_new_tokens 256, num_ctx 8192 (the validation settings). Chosen now, not after seeing test results | team | [ ] |
| 4 | Seeds and temperature | Seeds 298, 299, 300 are frozen. With temperature 0 the three seeds give identical output, so the seed summary will show SD = 0. Decide now: raise the temperature (then record it in item 3), or keep 0 and say in the report why SD is 0. Decide before the first formal test | team | [ ] |
| 5 | Protocol v1.1 confirmed by the team | commit that holds `docs/evaluation_protocol.json` | team | [ ] |
| 6 | Is Model E the fifth model? | yes or no; changes the report wording only | team | [ ] |

## Before any test generation

- [ ] Eligibility manifest frozen and its hash recorded ([eligibility_review_guide.md](eligibility_review_guide.md)).
- [ ] Second rule reviewer finished ([rule_second_review.md](rule_second_review.md)), or the report says it is pending.
- [ ] This checklist committed, so the settings are fixed in git history before the run.
- [ ] Clean working tree on the machine that runs generation. The runner records `working_tree_dirty`, and the seed summary refuses a dirty run.

## The run (the machine with the GPU)

1. Generate plans for the 100 test cases once per seed, same model, prompt and decoding.
2. Verify each seed: `python scripts/verify_model_plans.py --plans <plans_for_seed> --cohort test --generation-metadata <metadata_for_seed.json>`.
3. Combine the three results, each run plus mean and standard deviation: `clinverify.eval.seed_summary.summarize_seed_runs(runs, load_protocol())`. It refuses runs that differ in anything but the seed.
4. Do not rerun a seed because the result looks bad. A failed or partial run is reported, not replaced.

## Tested without a model

The test path was exercised end to end on dummy plans (the covered cohort resolves to 73 cases, the metadata check passes for all three seeds, and the adjudicated rate stays null without human labels). Those dummy results are not model results and were not saved.
