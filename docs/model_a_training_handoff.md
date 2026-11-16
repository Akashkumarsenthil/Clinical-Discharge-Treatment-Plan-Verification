# Model A training package for Akash

Linear: [T6-187](https://linear.app/298a-team-6-neurosymbolic/issue/T6-187/build-model-a-adapter-training-package-and-synthetic-tests).

This is development software for a possible LoRA adaptation, not a trained clinical
model or professor approval. The task remains a team decision. The existing Ollama
Model A and its frozen evaluation protocol are unchanged. Work was prepared against
main `04acfc407aed26d92af30297ddbcd4c1c3f1956f`.

## What is included

- `scripts/prepare_model_a_training.py`: diagnosis or treatment-plan training bundles.
- `scripts/train_model_a_adapter.py`: offline local Hugging Face LoRA training,
  optional 4-bit loading on CUDA, tokenizer preflight, timing, loss logs, adapters
  and optional validation generation.
- `tests/test_training_package.py`: no credentialed data, GPU or downloaded weights.
- Separate optional dependencies; the inference environment stays as it is.
- Decision-record examples in `configs/`; placeholders intentionally fail validation.

Diagnosis training learns only the reference diagnosis. It is not treatment-plan
adaptation and is not automatically one of the agreed A–D configurations.
Treatment-plan training needs approved targets for every train and validation case.
The program does not turn rule verdicts, unknown facts or discharge summaries into
clinical target plans. A human approval record is a declaration, not proof of label
quality or professor acceptance. Obtain the actual agreement before filling it.

## Shruthi's Mac check

From the repository root, use Python 3.12 in a separate environment:

```bash
python3.12 -m venv .venv-train
source .venv-train/bin/activate
python -m pip install -r requirements-training-cpu.txt
python -m pytest tests/test_training_package.py -q

python scripts/prepare_model_a_training.py --task diagnosis --synthetic \
  --out "$HOME/clinverify_training/synthetic-diagnosis"
python scripts/train_model_a_adapter.py \
  --bundle "$HOME/clinverify_training/synthetic-diagnosis" \
  --cpu-smoke --max-steps 2 --gradient-accumulation 1 --lora-rank 2 \
  --max-length 1024 --max-new-tokens 32 \
  --out "$HOME/clinverify_training/smoke-diagnosis"
```

Repeat with `--task treatment_plan` and fresh bundle/output paths to exercise the
other mode. Synthetic completions are intentionally simple software fixtures, not
clinical examples. CPU smoke constructs a tiny random GPT-2 locally, performs real
optimizer updates, evaluates validation loss and saves a reloadable LoRA adapter.
No internet/model download is used during either command. This is software evidence,
not Qwen performance or evidence that the course model requirement is met.

## Team decisions before a real run

1. Record the owned Linear issue and agreed training task. Keep the contribution
   separate from Akash's GPU execution and do not mark training complete yet.
2. Confirm with the professor whether the proposed adaptation meets the requirement.
3. Choose the exact local Hugging Face base model and license. Start with a small
   model for feasibility; no claim is made that Qwen2.5-14B at 8K context fits 16 GB.
4. Agree and document the target source and validation policy. For plans, obtain
   human-approved targets; agreement with these targets is not independent clinical
   adjudication. If any target is missing, the full bundle is refused rather than
   silently changing the population.
5. Keep the 100 test cases sealed. Training and validation use only frozen split v2.
   Existing validation results can guide development; preserve the original runs and
   disclose subsequent changes. A new adapter requires its own evaluation identity.

No additional MIMIC-IV download is needed for this preparer. Akash needs his own
approved Ext-CDM 1.1 copy (five allowed tables, lab mapping and pathology IDs), the
committed patient-grouped split and local model weights. Hashing the source files
is for provenance; held-out rows are filtered before preprocessing or model input.
The preparer does not open discharge diagnosis, ICD or procedure CSVs or case facts.

## Prepare the private development bundle

Copy and fill the appropriate `configs/training_decision.*.example.json` in a private
directory. No file is pre-approved. Example diagnosis command after team agreement:

```bash
python scripts/prepare_model_a_training.py --task diagnosis \
  --data-dir "$MIMIC_DIR/mimic-iv-ext-cdm-1.1" \
  --decision "$HOME/clinverify_training/decision.json" \
  --out "$HOME/clinverify_training/diagnosis-bundle-v1"
```

For treatment plans, use `--task treatment_plan --targets /private/path/targets.jsonl`.
Each line must have exactly this shape (illustrative synthetic ID, not a real target):

```json
{"case_id": -1, "plan": {"diagnosis": "appendicitis", "treatments": [], "postop_antibiotic_days": null}}
```

Use actual train/validation IDs only in the private file. The `plan` must use the
existing Model A schema, exclude case facts/verdicts, and match the reference diagnosis.
The team decision must pin the SHA-256 of this file. The file must include all 1,840
train and 460 validation targets and no test IDs. Do not commit it.

## Akash's GPU setup and runtime estimate

Use WSL/Linux and a separate Python 3.12 environment. Install a CUDA PyTorch build
that supports the actual GPU and driver, then `requirements-training-cuda.txt`.
The Mac smoke check used PyTorch 2.9.1; it does not verify a CUDA build. The RTX 5060 Ti
requires a Blackwell-capable build. Check the official installation tables below,
run `python -m bitsandbytes`, and confirm CUDA kernels work before using real records.
Do not replace the working inference environment.

`--model-dir` must be an already-downloaded local Hugging Face checkpoint with weights
and tokenizer, not an Ollama model tag or GGUF file. The runner disables Hub downloads,
telemetry, external experiment trackers and uploads. It uses Transformers 4.57.3,
PEFT 0.18.0 and optional bitsandbytes 0.48.2. CUDA compatibility remains to be checked
on the target machine. Model acquisition is a separate step before loading records.

First tokenize only, with a fresh output directory:

```bash
python scripts/train_model_a_adapter.py \
  --bundle "$HOME/clinverify_training/diagnosis-bundle-v1" \
  --model-dir /private/models/AGREED_HF_MODEL \
  --preflight --i-confirm-team-decision --max-length 8192 \
  --out "$HOME/clinverify_training/preflight-v1"
```

The preflight records token counts and local model hashes without loading a GPU model.
Overlong examples are refused. No target or input text is silently truncated; change
an input policy only through an agreed, versioned change and prepare a new bundle.

Then profile ten optimizer updates on training data (default batch 1, accumulation 8):

```bash
python scripts/train_model_a_adapter.py \
  --bundle "$HOME/clinverify_training/diagnosis-bundle-v1" \
  --model-dir /private/models/AGREED_HF_MODEL \
  --load-in-4bit --i-confirm-team-decision --max-steps 10 \
  --out "$HOME/clinverify_training/profile-v1"
```

`run.json` records step timings, peak allocated GPU memory and an update-time estimate
for the requested full epoch schedule. The estimate excludes loading, hashing,
tokenization, evaluation, generation and saving. Include measured overhead and a
debugging margin in the time budget. A ten-step pilot is labeled `step_limited` and
must not be reported as a completed full-schedule experiment. If it fails with OOM,
record that and revisit model/context choices; no runtime is promised in advance.

For the agreed full run, use a fresh output path, omit `--max-steps`, specify agreed
epochs and optionally set `--validation-generations 460`. Save the decision/settings
before running. Only the `train` rows reach the optimizer; `val` is used for loss and
optional greedy generation. The preparer requires full fixed development coverage.

## What to send back

Keep all bundles, target plans, model checkpoints/adapters, raw logs and per-case
predictions local and outside Git, even when the data is deidentified.

Privately inspect:
- `run.json`: configuration, file hashes, packages, GPU, training/validation loss,
  duration, parameter counts, peak memory and timing estimate.
- `loss_history.json` and `step_seconds.json`: real learning curves and update timings.
- `adapter/`: LoRA weights and tokenizer. CPU smoke additionally saves `smoke_base/`.
- `validation_scores.json` if generation was requested: sampled count, parse rate,
  diagnosis accuracy and target exact match. A subset is not all-validation evidence.
- `run.failed.json` and partial loss history if a failure occurs during training.

Share a manually checked aggregate-only summary through the owned issue/PR. Never
publish a bundle, target, patient prompt, adapter or prediction file. Loss and target
exact match do not establish clinical adequacy or the 0.85 research endpoint.

Treatment-plan mode writes `validation_predictions.json` in the format the existing
`scripts/verify_model_plans.py --plans <file> --cohort validation` loader accepts.
The fixed-cohort scorer counts missing or malformed generations as failures. Use all
460 generations for a full validation estimate; a short pilot otherwise has missing
outputs. Diagnosis-only predictions are not complete treatment plans and must not be
presented as such. An HF adapter is not automatically loaded by the existing Ollama
generation CLI. Ollama conversion, formal test runs and clinical adjudication remain
separate work, after the team/professor decisions and existing freeze gates.

## Implementation references

- https://huggingface.co/docs/transformers/v4.57.3/en/main_classes/trainer
- https://huggingface.co/docs/transformers/v4.57.3/en/chat_templating
- https://huggingface.co/docs/peft/developer_guides/quantization
- https://huggingface.co/docs/bitsandbytes/v0.48.2/installation
- https://pytorch.org/get-started/previous-versions/
