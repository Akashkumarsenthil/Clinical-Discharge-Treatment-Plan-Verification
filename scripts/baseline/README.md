# Hager baseline: run and scoring scripts

These are the scripts behind the reduced-scale reproduction in [docs/baseline_notes.md](../../docs/baseline_notes.md): Llama 3.1 8B Instruct (4-bit), 100 cases per pathology, sampling seed 298. They hold no patient text. The run logs and result files do, so they stay in `~/baseline`, outside the repository.

| File | What it does |
|---|---|
| `run_subset.sh` | runs the Hager framework for the four pathologies on the sampled case IDs (`cdm_work/subset100_<pathology>.txt`) |
| `resume_subset.sh` | after an interruption, reruns only the cases without a saved result; safe to repeat |
| `score_hager.py` | merges the result files of one pathology and scores them with the framework's own evaluator, as `evaluate_cdm.py` does; prints counts and accuracies only |
| `hager_framework_e1b4a52_local_edits.patch` | the local edits to the framework (pinned commit `e1b4a52`): an 8B model config, GPU-specific imports made optional, an optional case-ID list in `run.py`, and a paths config |
| `hager_dataset_4d33f98_local_edits.patch` | the one-line output path edit to the dataset converter (`ConvertPhysionet.py`, commit `4d33f98`) |

Paths are the ones used on the team GPU machine (`/home/akash/baseline`). Apply a patch with `git apply <patch>` inside the matching clone. The sampled case-ID files are not committed.
