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

Not run yet. Blockers: GPU access, environment setup, and agreeing the fallback (smaller model or subset, with the gap documented). Record every attempt and its result here, including failures.
