# Team Meeting 2 — Professor track, slides 6 to 8

Author: Akashkumar Senthilkumar. Reviewer: to be assigned (not Akash).

Text and speaker notes for slides 6 to 8 of Template 7A. Slides 1–4 are in `slide_text_1-4.md` (Shruthi) and slide 5 is in `slide_text_5.md` (Ritika). Suggested time: 7 minutes 15 seconds of the 9 minutes 30 seconds left for slides 5–8 (slide 6: 1:30, slide 7: 3:30, slide 8: 2:15). Timing is a rehearsal allocation, not a measured result. All numbers are from the validation split (460 cases); the 100 test cases have not been used.

## Slide 6 — First model trained

### On-slide text

**Model A is implemented and prompted. It is not trained.**

| Model A (298A) | |
|---|---|
| Model | Qwen2.5-14B, 4-bit (Q4_K_M), local Ollama on one RTX 5060 Ti (16 GB) |
| Task | Whole record in one prompt, one structured plan out (JSON schema), checked by the Z3 verifier |
| Decoding | Greedy: temperature 0, seed 298 |
| Run so far | 460 validation plans, 2,268 ms per case |
| Fine-tuning | None |

**What exists for training:** an adapter-training package (PR #16): data preparation, LoRA runner, profiling command. Tested on synthetic data only. No real training has been run.

**What it waits for:** agreement on the training target and labels, and the instructor's confirmation that the approach meets the requirement.

**The only trained model so far** is Model E, a TF-IDF + logistic regression reference (29 s to train). It is not one of the four models.

### Speaker notes — approximately 1 minute 30 seconds

The template asks for the first model trained. We want to be exact about where we are. Model A is built and has run on all 460 validation cases, but it is a prompted model: a pretrained Qwen2.5-14B reads the record and writes a plan in a fixed format, and we do not change its weights.

We did not fine-tune it in this period. Two things stand in the way. First, a fine-tuned plan model needs target plans, and the only labels we have are diagnoses; rule verdicts and unknown facts must not be turned into target plans, so a treatment-plan target needs human-approved labels. Second, we want the instructor to confirm that this approach counts. Shruthi built a training package that is ready for my GPU. It passed its tests on synthetic data, and the guards keep the 100 test cases out of training. We will profile it on the real GPU after the decision.

The one model we trained is Model E, a small text classifier that gives a cheap reference point. We have not decided its status; it is not one of the four.

**Ask:** does a prompted Model A, with the adapter training prepared but not run, meet the requirement for the first model in 298A?

## Slide 7 — Baseline reproduction and first benchmark

### On-slide text

**Baseline: Hager et al. (2024), autonomous task, mean diagnostic accuracy**

| | Published (OASST 70B) | Ours (Llama 3.1 8B, 4-bit, 400 cases) |
|---|---|---|
| Appendicitis | 82.0 | 74.7 |
| Cholecystitis | 48.0 | 30.0 |
| Diverticulitis | 45.5 | 37.0 |
| Pancreatitis | 44.1 | 48.0 |
| **Mean** | **54.9** | **47.4** |

Same framework (pinned commit `e1b4a52`) and evaluator. Reduced scale: 8B model instead of 70B, 100 cases per pathology (about ±10 points each), newer MIMIC versions. Appendicitis is easiest in both.

**First benchmark: validation split, 460 cases, seed 298, one run**

| | Majority class | Model E (reference) | Model A |
|---|---|---|---|
| Diagnosis accuracy | 0.400 | 0.887 | 0.887 |
| Macro F1 | 0.143 | 0.853 | 0.855 |
| Checked acceptance (336 covered) | 0.143 | 0.188 | 0.146 |
| Joint success | 0.104 | 0.163 | 0.120 |

Model A verdicts: 57 valid, 123 violated, 280 insufficient information.

**The prompted LLM ties the cheap classifier on diagnosis and does worse on checked acceptance.**

### Speaker notes — approximately 3 minutes 30 seconds

Baseline first. We reproduced the autonomous setting of Hager et al. with the authors' framework at a pinned commit and their own evaluator. We could not run the 70B models on a 16 GB card, so we ran Llama 3.1 8B in 4-bit on 400 cases, 100 per pathology. The mean is 47.4% against 54.9% published, a gap of 7.5 points. With 100 cases per pathology each number has an interval of about plus or minus 10 points, and the model, data version and quantization all differ, so the gap does not say the framework was reproduced right or wrong. Appendicitis is the easiest pathology in both; the order of the other three differs. One appendicitis case could not be scored because the reference record has a missing value, so it is left out rather than counted wrong. Every change we made to the framework is listed in `docs/baseline_notes.md`. Fourteen of the 400 baseline cases are also in our 100 test cases; nothing was tuned or selected on them, and we will disclose this in the report.

Now the first benchmark, on the validation split only. A majority-class guess gets 0.400 accuracy. A small text classifier, Model E, and the prompted Qwen2.5-14B both get 0.887. So the large language model does not beat a cheap classifier at diagnosis. Where the project matters is the plan check. Checked acceptance means a correct diagnosis and a plan accepted after at least one decided clinical rule. Model A reaches 0.146 and Model E 0.188.

Read Model A's verdicts with care. Of 460 plans, 57 are valid, 123 violate a rule, and 280 are insufficient information: the record cannot establish a fact a rule needs, so the verifier refuses to call the plan valid. Of the 169 rule violations, 106 are the scope guard for cholecystitis, which has no treatment rules. So 0.124 valid is not a failure rate. Quote checked acceptance and joint success, with the 280 stated.

Two cautions. This is one run at temperature 0, so there is no spread to report. And these validation cases are not the baseline's cases, so the baseline accuracy and Model A's accuracy are not a like-for-like comparison. Acceptance means compliance with our rules, not clinical correctness.

## Slide 8 — Next, risks, asks

### On-slide text

**Next (298A, before any test run)**
1. Blind eligibility review of the 73 covered test cases (Shruthi), then freeze the manifest.
2. Decide the temperature and sign the Model A freeze checklist. Greedy decoding makes the three seeds identical.
3. One test-split run of Model A, once.

**Next (298B)**
- Models B, C and D (proposed owners: Rajesh, Shruthi, Ritika; to confirm by Nov 19), then an ablation and a failure study.
- Independent plan labels, so the escape rate and the 0.85 research goal can be measured.
- Results by age, sex, race and language.

**Risks**
- Second rule review and clinical review are pending: the catalog is tested, not clinically validated.
- Test-set discipline: the 100 test cases are used once.
- Fine-tuning needs approved labels and GPU time.

**Asks**
- Instructor: does a prompted Model A with adapter training prepared meet the first-model requirement?
- A clinician or reviewer for the rule catalog.

### Speaker notes — approximately 2 minutes 15 seconds

Before the test split is touched, three things have to happen. Shruthi is doing the blind eligibility review of the 73 covered test cases with her own copy of the data; its result freezes the denominator. We then decide the decoding temperature and sign the freeze checklist, because greedy decoding makes our three seeds identical and would hide any variation. Only then do we run Model A on the test cases, once.

In 298B we build Models B, C and D, with proposed owners Rajesh, Shruthi and Ritika, to be confirmed by November 19, and compare them with Model A and the baseline. Independent plan labels from someone who did not write the rules or Model A are needed to measure the escape rate and the 0.85 research goal. We also owe a breakdown of results by group.

The main risks: the second rule review and any clinical review are still pending, so the rules are implemented and tested but not clinically validated; we must use the test set only once; and fine-tuning needs approved labels and GPU time.

Two asks. For the instructor: does a prompted Model A, with adapter training prepared, count as the first model for 298A? And we would welcome a clinician to review the rule catalog.

## Repository sources

- `docs/validation_summary.json`: every benchmark number and the Model A run settings.
- `docs/baseline_notes.md`: baseline table, deviations, interval, skipped case, test-split overlap.
- `docs/team_meeting_2_prep.md` §3 and §5: what each slide covers and the open decisions.
- `docs/model_a_freeze_checklist.md`: the temperature and freeze decisions.
- Pull request #16 (Shruthi): the adapter-training package.

## Handoff checks

- Slide 6 must not present a prompted model as a trained one. If the team decides otherwise before the meeting, rewrite slide 6 and its notes.
- Slide 7 numbers come from the linked files; no new run was made for this text. Keep Model A's validation numbers off slide 5.
- "Model E" is called a reference model because the team has not decided its status. If the team names it differently, use one name in the deck, the memo and the workbook.
- The 2,268 ms per case is recorded in `results/workbook2/4_4_model_comparison.csv`, which is not committed; `validation_summary.json` has no speed fields for Model A.
- The cholecystitis, diverticulitis and pancreatitis baseline values (48.0, 45.5, 44.1) are the paper's OASST 70B numbers as recorded in `docs/baseline_notes.md`.
