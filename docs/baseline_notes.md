# Baseline reproduction notes (Hager et al., 2024)

Baseline to reproduce: Hager, P., et al. (2024). Evaluation and mitigation of the limitations of large language models in clinical decision-making. *Nature Medicine*, 30, 2613-2622. https://doi.org/10.1038/s41591-024-03097-1

## What is reported (verified in the paper)

| Setting | Llama 2 Chat 70B | OASST 70B | WizardLM 70B |
|---|---|---|---|
| Autonomous task, mean diagnostic accuracy (**Fig. 3**) | 45.5% | **54.9%** | 53.9% |
| Full-information task (MIMIC-CDM-FI) | 58.8% | 67.8% | 65.1% |

The number to reproduce is **54.9%** (OASST 70B, autonomous setting, 2,400 cases). It measures diagnosis, not plan validity.

## Code (public, MIT)

| Repository | Role |
|---|---|
| https://github.com/paulhager/MIMIC-Clinical-Decision-Making-Framework | runs the task (`run.py`, `run_full_info.py`); **pinned commit `e1b4a52`** (2025-02-07), cloned locally |
| https://github.com/paulhager/MIMIC-Clinical-Decision-Making-Analysis | statistics and plots |
| https://github.com/paulhager/MIMIC-Clinical-Decision-Making-Dataset | builds the dataset from MIMIC-IV |

The cloned framework is not committed here.

## Requirements to run it

- NVIDIA GPU and CUDA (the repository pins CUDA 11-era packages: `torch 2.0.1`, `exllamav2`, `auto-gptq`, `autoawq`; Python 3.10).
- 70B-class models (quantized inference still needs tens of GB of GPU memory).
- Data: MIMIC-IV-Ext-CDM and MIMIC-IV. The paper used MIMIC-IV v2.2 and Ext-CDM v1.0; this project has v3.1 and v1.1, so compatibility has to be checked.
- MIMIC text must not be sent to hosted LLM APIs (data use agreement), which is why the authors could not test GPT-4 or Med-PaLM.

## Status

Run on the local machine (RTX 5060 Ti, 16 GB, WSL2). A reduced-scale reproduction, not a like-for-like one: the 70B models do not fit in 16 GB, so the framework was run with a smaller model on a sample of cases. Result files contain MIMIC text and stay outside this repository; only the aggregate numbers are recorded here.

## What was run, and how it differs from the paper

| Item | Paper | This run | Why |
|---|---|---|---|
| Model | OASST / Llama 2 Chat / WizardLM 70B | Llama 3.1 8B Instruct, 4-bit (bitsandbytes) | 70B does not fit in 16 GB |
| Cases | 2,400 (600 per pathology) | 400 (100 per pathology, sampled with seed 298) | time; one case takes about 30 s |
| Task | Autonomous | Autonomous (same framework, same prompts, `ZeroShot`) | unchanged |
| Metric | Diagnosis accuracy per pathology, then the mean | Same evaluator (`load_evaluator(...)._evaluate_agent_trajectory`) | unchanged |
| MIMIC-IV / Ext-CDM | v2.2 / v1.0 | v3.1 / v1.1 | what the project has access to |
| Framework | public repository | pinned commit `e1b4a52`, with the edits below | modern GPU needs a newer stack |
| Context length | model default | 16,384 tokens | fits memory with the 8B model |

Edits to the framework (all local, none change the task, prompts or scoring):
- `configs/model/Llama3.1Instruct8B.yaml`: new config copied from the 70B Llama 3.1 one, with the 8B model name.
- `models/models.py`: the 8B model name is routed through the existing Llama 3 code path; the `auto_gptq` and `exllamav2` imports are wrapped in try/except because they do not install on this GPU.
- `utils/nlp.py`: the ExLlamaV2 tokenizer import falls back to a placeholder class.
- `run.py`: an optional `patient_list_path` restricts a run to a list of case IDs (used for the 100-case sample).
- `ConvertPhysionet.py` (dataset repo): output path set to the local folder. It leaves out the procedure keys for patients with no procedures, so the scorer defaults them to empty lists.

Environment: Python 3.12, torch 2.11 with CUDA 12.8 (the RTX 5060 Ti is a Blackwell card, which the paper's torch 2.0.1 stack does not support), spacy 3.7.5, pandas < 2.3, numpy < 2.

Operational notes: the first long run was stopped by a 4-hour timeout I had set, and a WSL restart at about 15:52 on 11/1 killed another run. `resume_subset.sh` reruns only the cases without a result, so each pathology's 100 cases come from one or more result files that `score_hager.py` merges.

## Results

| Pathology | Paper OASST 70B | This run (Llama 3.1 8B 4-bit, n=100) |
|---|---|---|
| Appendicitis | 82.0 | 74.7 (99 scored, 1 skipped, see below) |
| Cholecystitis | 48.0 | 30.0 |
| Diverticulitis | 45.5 | 37.0 |
| Pancreatitis | 44.1 | 48.0 |
| Mean | 54.9 | 47.4 |

All four pathologies finished on 11/1 (400 cases, scored with the framework's own evaluator). The mean is 7.5 points below the paper's. Appendicitis is the easiest pathology in both; the order of the other three differs (in the paper pancreatitis is lowest at 44.1, in this run it is second highest at 48.0, above diverticulitis and cholecystitis).

Read the comparison with care. With 100 cases per pathology the 95% interval on one accuracy is about plus or minus 10 points, and the model, data version and quantization all differ from the paper. A gap does not by itself show that the framework was reproduced wrongly or rightly.

## Overlap with the test split

14 of the 400 baseline cases are also among the 100 test cases of split v2 (2 appendicitis, 0 cholecystitis, 9 diverticulitis, 3 pancreatitis), so all 14 are among the 73 covered cases. The baseline outputs for them come from Llama 3.1 8B in the Hager framework, not from Model A, and stay outside the repository because they contain MIMIC text. The 400 cases were drawn per pathology with seed 298 on 2026-11-01, after split v2 was fixed (2026-10-21). Only accuracy per pathology was computed. Nothing was tuned, selected or decided from these cases, and the blind eligibility reviewer has not seen the outputs. State this overlap in the report.

## Open checks (optional, before the numbers go into the report)

- [x] Skipped appendicitis case (99 of 100 scored): the model's run finished normally and its answer is well formed. The evaluator failed on the reference side: for that case the converted record's `Procedures Discharge` list holds a missing value (a float NaN), and the evaluator's text step (spaCy) rejects it. It is a data gap in the converted reference, not a model failure, so the case is left unscored rather than counted wrong. Counting it as wrong would lower appendicitis from 74.7% to 74.0%, which does not change any conclusion.
- [ ] Confirm the prototype (`app/demo_app.py`) starts on a fresh clone. The saved Model A plans are in the gitignored `results/model_runs/`, so they have to be regenerated first.
