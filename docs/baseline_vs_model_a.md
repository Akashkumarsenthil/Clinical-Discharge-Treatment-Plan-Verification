# Baseline vs Model A — percentage comparison

Figure: [`images/baseline_vs_model_a.png`](images/baseline_vs_model_a.png)  
Rebuild: `python scripts/make_baseline_model_comparison_figure.py`  
Sources: [`baseline_notes.md`](baseline_notes.md), [`validation_summary.json`](validation_summary.json) (seed 298).

**Needed for:** TA ask (baseline vs model as %), Template 10.1 benchmark shape, final Slide 5.  
**Not needed for:** new GPU runs. Numbers are already frozen aggregates.

## Diagnosis accuracy (%)

| Row | Setting | % | Notes |
|---|---|---:|---|
| Published Hager | OASST 70B, autonomous, 2,400 cases | **54.9** | Diagnosis only (Fig. 3) |
| Our baseline | Llama 3.1 8B 4-bit, 400 cases | **47.4** | Reduced-scale; not like-for-like |
| Majority class | Validation 460 | **40.0** | Always predict appendicitis |
| Model E | TF-IDF + LR, validation 460 | **88.7** | Diagnosis on our split |
| Model A | Qwen2.5:14b, validation 460 | **88.7** | Diagnosis on our split |

Panel A mixes **different cohorts and setups**. Do not claim Model A “beats Hager 54.9” on the same task.

## Plan metrics on our validation split (%)

Hager does not report Z3 plan validity. These are **our** rates only.

| Metric | Model E | Model A |
|---|---:|---:|
| Checked acceptance (336 covered) | **18.8** | **14.6** |
| Joint success (460) | **16.3** | **12.0** |

Model A plan statuses: valid 57, violated 123, insufficient information 280. Of rule hits, R-GEN-001 = 106 (cholecystitis scope).

## One-line takeaway

On diagnosis, prompted Model A ties the cheap classifier (~89%) and sits far above majority class; it is **not** comparable to the published 54.9% Hager number. On **plan** checked acceptance, Model A (**14.6%**) is below Model E (**18.8%**) — the verifier is where the LLM loses.
