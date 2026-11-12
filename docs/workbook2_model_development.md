# Workbook 2 material: model development (sections 4.1 to 4.4)

Workbook 2 is report sections 3 and 4. The code that produces every table and figure is in [`notebooks/workbook2.ipynb`](../notebooks/workbook2.ipynb). The data-cleaning walk-through is in `notebooks/data_pipeline_demo.ipynb`. This page holds the model-development text and tables.

This page is a working draft built from what the repository says (README, `docs/baseline_notes.md`, `docs/metrics.md`) and from the papers in `papers/`. Owners are filled in where they are known (Models B, C and D are 298B and not assigned yet); dates are for the team to fill in. The strengths and limitations are our reading of the papers and the data so far. Nothing here is a test result: Model A has only been run on the validation split, and the formal test runs have not happened.

## 4.1 Model proposals

We build four models, one in 298A and three in 298B. The reproduced baseline is listed separately and is not one of the four.

| # | Model | Concept / architecture | Built in | Owner |
|---|---|---|---|---|
| 1 | A | An LLM generates the discharge and treatment plan directly. The plan is parsed into the structured form and checked by the Z3 verifier. The LLM is prompted, with no project fine-tuning | 298A | |
| 2 | B | Proposed for 298B. Input: the admission record text (history, examination, labs, microbiology, radiology) and no record-derived facts. Architecture: an LLM turns the record and the clinical goals into a formal specification, a JSON list of constraints on the plan (diagnosis, allowed treatment concepts, required durations) that maps to Z3 terms. Algorithm: a Z3 solver finds a treatment set that satisfies the specification and the rule catalog; the LLM then writes the plan text from the solved set. The result is checked by the same verifier as Model A. | 298B | Rajesh (proposed; to confirm) |
| 3 | C | Proposed for 298B. Input: the same record as Model A. Architecture: Model A's generator plus a repair loop around the Z3 verifier. Algorithm: generate a plan, verify it, return the names and messages of the violated rules to the LLM, and regenerate; stop when no rule is violated or after a fixed number of rounds (proposed: 3). Unknown rule outcomes are not fed back as violations. The final plan is scored by the same verifier as Model A. | 298B | Shruthi (proposed; to confirm) |
| 4 | D | Proposed for 298B. Input: the same record as Model A. Architecture: an LLM writes the initial state and the goal in PDDL from the record, and a classical planner (for example Fast Downward) searches for an action sequence. Algorithm: the actions are the treatment concepts of the plan schema, with preconditions taken from the rule catalog; the found action sequence is rendered back to the structured plan and checked by Z3. It is the hardest to build, because lab-dependent and conditional rules are hard to write as preconditions. | 298B | Ritika (proposed; to confirm) |
| — | Reproduced baseline | Hager et al. (2024), autonomous task, 2,400 cases in the paper. The best open model, OASST 70B, reaches 54.9% mean diagnostic accuracy (Fig. 3 of the paper). It measures diagnosis, not plan validity. Our reproduction is reduced-scale (see the carry-forward table) | 298A | |

## 4.2 Model supports: platform and architecture

The patient data, the models and the verifier all run on a local machine. Only code, documents, case IDs and aggregate counts go to GitHub. MIMIC text is never sent to a hosted LLM, which PhysioNet's data-use rules require.

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Arial","fontSize":"20px","clusterBkg":"#f8fafc","clusterBorder":"#91a1b3","lineColor":"#536477"},"flowchart":{"htmlLabels":true,"curve":"linear","nodeSpacing":30,"rankSpacing":45}}}%%
flowchart LR
    subgraph LOCAL["Local machine — credentialed data stays here"]
        D["MIMIC-IV v3.1<br/>Ext-CDM v1.1"] --> P["Pipeline + DuckDB<br/>clean, transform,<br/>patient-grouped split v2"]
        P --> M["Model A — 298A<br/>local Ollama<br/>Qwen2.5:14b"]
        P --> F["Record-derived facts<br/>ICD + discharge text"]
        M --> Q["Plan parser<br/>attach record facts"]
        F -->|"judging only;<br/>not model input"| Q
        Q --> Z["Z3 verifier<br/>violations + unknowns<br/>advisory findings"]
        R["Rule catalog v2.1<br/>12 team-written rules<br/>second review pending"] --> Z
        Z --> E["Evaluation harness<br/>protocol v1.1<br/>fixed cohorts"]
        N["Proposed — 298B<br/>B: translation + solver<br/>C: verifier-guided repair<br/>D: PDDL planner"]
        P -. "case input" .-> N
        N -. "plan output" .-> Q
        Z -. "broken rule + message<br/>Model C only" .-> N
    end
    E -. "aggregate results" .-> G["GitHub<br/>code, docs, IDs,<br/>counts and rates"]
    classDef current fill:#eaf2fb,stroke:#315a85,color:#142b45,stroke-width:1.5px;
    classDef evidence fill:#edf6ef,stroke:#47785b,color:#183c24,stroke-width:1.5px;
    classDef proposed fill:#fff5e6,stroke:#a77730,color:#583d17,stroke-width:1.5px;
    class D,P,M,Q,Z,E current;
    class F,R evidence;
    class N proposed;
```

![Model architecture: implemented Model A data flow and proposed Models B–D](images/model_architecture.png)

| Part | What it is |
|---|---|
| Language and libraries | Python (runs verified on 3.13.5, GitHub Actions uses 3.12), pandas, numpy, matplotlib, z3-solver 5.3.1, pytest (`requirements.txt`) |
| Where code is checked | unit tests with `pytest`, run in GitHub Actions on every push |
| Where data lives | outside the repo, in `~/data/mimic`, and `.gitignore` blocks data files |
| Where the models run | local only: one team machine with an NVIDIA RTX 5060 Ti (16 GB) under WSL2. Model A is served by Ollama 0.40.12 as qwen2.5:14b (Q4_K_M, 4-bit weights), with output constrained to a JSON schema. Decoding is greedy (temperature 0, seed 298, 8,192-token context) |

Solid arrows show the implemented Model A path; dashed arrows show proposed 298B extensions or the export of aggregate results. The model receives the allowed clinical input tables, never the record-derived case facts. Rule acceptance is not a clinical safety or completeness guarantee. Platform details: [`team_meeting_2_prep.md`, section 3](team_meeting_2_prep.md#3-deck-notes-8-slides-17--3-minutes).

To reproduce the PNG locally after editing the Mermaid block, extract it to a `.mmd` file and run `mmdc -i architecture.mmd -o docs/images/model_architecture.png --size 3200 -b white` (Mermaid CLI 12.2.0). Alternatively, use Mermaid Live Editor with the same source and a PNG width of 3200 pixels. No patient data is needed.

## 4.3 Comparison and justification

| | Model A | Model B | Model C | Model D |
|---|---|---|---|---|
| Targeted problem | plain plan generation, the reference for the rest | plans that are faithful to a formal reading of the case | plans that are corrected until they pass the rules | plans that are valid by construction for a planning domain |
| Input | the whole record in one prompt: history, exam, labs, microbiology and radiology, trimmed to an 8,192-token context (the full-information setting of Hager et al.); no discharge diagnosis, ICD codes or case facts | case text | case text plus verifier feedback | case text plus a domain model |
| Approach | LLM prompting (deep learning) | LLM translation plus a deterministic solver (Logic-LM, SatLM, Faithful-CoT) | LLM plus an external critic in a loop (LLM-Modulo, Logic-LM self-refine) | LLM translation plus a classical planner (LLM+P) |
| Strength | simplest; closest to the baseline paper; no translation step | the solver does the reasoning, so the explanation matches the answer | uses the rule catalog directly and names the broken rule | the planner's output follows the domain model |
| Limitation | no correction step; Hager et al. report that LLMs often skip guideline-recommended treatment | translation errors (counted as translation fidelity); the formal language has to cover each diagnosis | can only repair what the rules cover; an unknown fact gives no feedback; costs extra solver calls and generations | needs a clinical planning domain written in PDDL, which does not exist yet and is hard to write |
| Phase | 298A | 298B | 298B | 298B |

**Justification.** All four models are scored on the same 100 test cases with the same verifier, so the only thing that changes is the method. The baseline sits outside the four as the published reference point.

**Where a model would lose.** We haven't chosen a preferred model yet. These are draft conditions for the team to confirm:

- Model A loses to B, C and D whenever correction matters, because it never sees why a plan failed.
- Model B loses when the notes are too long or messy to translate correctly. Pancreatitis notes have a median of 248 words against 95 for appendicitis (notebook section 3).
- Model C loses when most facts are unknown. Six of 12 rules can be checked on at most one case from the facts alone (`notebooks/workbook2.ipynb`, figure 3.6e), so there is little to feed back.
- Model D loses when the care step cannot be written as an action with a precondition, as with the lab-dependent and conditional guideline rules.

## 4.4 Evaluation methods

The definitions are in [`metrics.md`](metrics.md) (protocol v1.1, committed to the repository on October 23, 2026, commit `84c3ca5`) and [`evaluation_protocol.json`](evaluation_protocol.json). If this page and `metrics.md` ever differ, `metrics.md` is right. Model A has validation-split output only (aggregate results in [`validation_summary.json`](validation_summary.json) and `notebooks/workbook2.ipynb`); no test-split output exists. The table below is the same content in the shape the template asks for.

| Metric | Why this metric | Measured on | Committed on |
|---|---|---|---|
| `diagnosis_accuracy` | the baseline paper's headline number; reproduces a published reference | all 100 test cases | Oct 23, 2026 |
| `supported_checked_acceptance_rate` (primary, descriptive, no numeric target) | share of covered cases with a correct diagnosis and a plan accepted after at least one decided blocking clinical rule; scope-only or advisory-only acceptance earns no credit | the 73 covered test cases | Oct 23, 2026 |
| `joint_success_rate` | correct diagnosis and an accepted plan together | all 100 test cases | Oct 23, 2026 |
| Escape rate, target <= 0.05 | bad plans that the verifier lets through, measured on independently labelled plans | independently labelled plans (scorer ready; human labels not yet done) | Oct 23, 2026; scorer 2026-10-27 |
| `adjudicated_treatment_validity_rate`, research goal 0.85 | independent human judgement of treatment validity | record-evaluable covered cases (scorer ready; human eligibility/labels not yet done) | Oct 23, 2026; scorer 2026-10-27 |

Runs use seeds 298, 299 and 300. Missing or unparseable plans count as failures. Results are reported per pathology next to the overall number.

Runs use seeds 298, 299 and 300. Missing or unparseable plans count as failures. Results are reported per pathology next to the overall number.

## Carry-forward from Workbook 1 and the abstract

| Item | Why it did not land, or what changed | New target |
|---|---|---|
| Plan validity >= 0.85 (abstract) | With the facts the record supports, no model can reach 0.85 automatically. The ceiling on the 73 covered test cases is 47 (64.4%) for the legacy acceptance diagnostic and 18 (24.7%) for checked acceptance, even with a perfect diagnosis (`docs/evaluation_feasibility.md`). Protocol v1.1 removes 0.85 as an automatic target | 0.85 kept only as a research goal on independently human-adjudicated plans. No numeric target on the automatic rates |
| Escape rate <= 0.05 (abstract) | unchanged | unchanged, measured on independently labelled plans |
| Human check of the derived case facts (116 cases) | done on 2026-10-27 by one team member: 116 of 116 reviewed, 100% agreement with the extraction. It is a consistency check against the mapping, not an independent clinician review | an independent reviewer, if the team wants a stronger validation |
| Second review of the rule catalog | still pending (needs a different human from SS) | second reviewer follows `docs/rule_second_review.md` and signs `docs/rule_signoff.md` |
| Baseline reproduction (Hager et al., 54.9%) | reduced-scale run done (Llama 3.1 8B 4-bit, 400 cases, 47.4% against 54.9%; not like-for-like, see `baseline_notes.md`). The 70B reproduction is not done | Workbook 2 keeps 4.5 and 4.6 as headings, per the template. The skipped appendicitis case is explained (a missing value in the reference's procedures field, left unscored). 14 of the 400 baseline cases (2 appendicitis, 9 diverticulitis, 3 pancreatitis) are among the 100 test cases; they were not used to choose cases or tune anything (`baseline_notes.md`) |
| Three generation seeds (298, 299, 300) | Model A decodes greedily (temperature 0), so the three seeds give identical output and the standard deviation is 0. The metric definitions are unchanged | the team decides before the test run whether to raise the temperature and records it in `docs/model_a_freeze_checklist.md` |

## Self-assessment and gap register

Ratings are our first guess from the evidence in the notebook and on this page. The team should confirm or change them.

| Report section | Our rating | If below good: what is missing | Owner | Lands by |
|---|---|---|---|---|
| 3.1–3.6 Data engineering | good | none known. Notes and labs are not shown, only case IDs and counts, because the data is credentialed | | |
| 4.1 Model proposals | poor | owners of B, C and D are proposed, not yet confirmed by Rajesh, Shruthi and Ritika; designs are proposals with no implementation or results | Akash | Nov 19, 2026 |
| 4.2 Model supports | good | none known. Figure 3 is the architecture figure in `docs/images/model_architecture.png` (PR #10) | Akash | Nov 11, 2026 |
| 4.3 Comparison | good | the team has not yet reviewed the strengths and limitations in 10.2 | | |
| 4.4 Evaluation methods | good | label scorer is built (`docs/adjudication_labels.md`); human eligibility/labels still missing, so the escape rate and the 0.85 research goal can't be measured yet | | |
| References | good | the list is in section 12; add any source the team introduces later | | |

## References

- Hager, P., et al. (2024). Evaluation and mitigation of the limitations of large language models in clinical decision-making. *Nature Medicine*, 30, 2613–2622. https://doi.org/10.1038/s41591-024-03097-1
- Johnson, A., et al. (2023). MIMIC-IV, a freely accessible electronic health record dataset. *Scientific Data*. PhysioNet, v3.1.
- Kambhampati, S., et al. (2024). Position: LLMs can't plan, but can help planning in LLM-Modulo frameworks. *Proceedings of ICML*, PMLR 235.
- Pan, L., Albalak, A., Wang, X., & Wang, W. Y. (2023). Logic-LM: Empowering large language models with symbolic solvers for faithful logical reasoning.
- Ye, X., Chen, Q., Dillig, I., & Durrett, G. (2023). SatLM: Satisfiability-aided language models using declarative prompting.
- Lyu, Q., et al. (2023). Faithful chain-of-thought reasoning.
- Liu, B., et al. (2023). LLM+P: Empowering large language models with optimal planning proficiency.
- Hekmatnejad, M., Simms, A. M., & Fainekos, G. (2019). Model checking clinical decision support systems using SMT. arXiv:1901.04545.
- Oniani, D., et al. (2024). Enhancing large language models for clinical decision support by incorporating clinical practice guidelines.
- de Moura, L., & Bjørner, N. (2008). Z3: An efficient SMT solver. *TACAS*.
- Rule sources (catalog v2.1): the 2025 WSES Jerusalem guidelines for acute appendicitis (Podda et al., JAMA Surg 2026;161:283-295, abstract only); the Ibero-Latin American guidelines on acute pancreatitis (Cardenas-Jaen et al., UEG J 2026;14:e70190); the ACG clinical guideline on colonic diverticulitis (Peery et al., Am J Gastroenterol 2026;121:1549-1561, abstract only); the Korean guidelines for acute colonic diverticulitis (Lee et al., Intest Res 2026;24:428-463).

## Still open

- The owners of Models B, C and D (built in 298B) in the table in 4.1.
- 4.5 and 4.6, which stay as headings, as the template says.
