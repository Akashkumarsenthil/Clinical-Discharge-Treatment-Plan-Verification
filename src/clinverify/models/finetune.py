"""Optional local Hugging Face LoRA backend; heavy dependencies imported only on use."""
from __future__ import annotations

import json
import math
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from clinverify.models.training_data import (
    TrainingError, digest, encode_row, json_digest, load_bundle, new_private_dir,
    plan_target, training_settings, write_json,
)
from clinverify.plan import DIAGNOSES


def offline_environment():
    import os
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def smoke_model():
    """Random tiny GPT-2 and tokenizer, constructed locally; no pretrained weights."""
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

    words = ["[PAD]", "[UNK]", "[EOS]", "system", "user", "assistant", "diagnosis",
             *DIAGNOSES, "treatments", "postop_antibiotic_days", "null", "{", "}", '"', ":", ",", "[", "]"]
    tok = Tokenizer(WordLevel({w: i for i, w in enumerate(words)}, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="[UNK]", pad_token="[PAD]", eos_token="[EOS]")
    tokenizer.chat_template = (
        "{% for m in messages %}{{ m['role'] + ' ' + m['content'] + ' [EOS] ' }}{% endfor %}"
        "{% if add_generation_prompt %}{{ 'assistant ' }}{% endif %}"
    )
    model = GPT2LMHeadModel(GPT2Config(vocab_size=len(words), n_positions=1024, n_ctx=1024,
                                      n_embd=32, n_layer=1, n_head=2,
                                      pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id))
    return model, tokenizer


def model_fingerprint(directory: Path) -> dict:
    # Weights must be local. Hash them rather than claiming a config hash identifies weights.
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in {".json", ".safetensors", ".bin", ".model"})
    if not any(p.suffix in {".safetensors", ".bin"} for p in files):
        raise TrainingError("model directory needs local Hugging Face weights, not an Ollama GGUF model")
    return {str(p.relative_to(directory)): digest(p) for p in files}


class CompletionCollator:
    def __init__(self, pad_id):
        self.pad_id = pad_id

    def __call__(self, features):
        import torch
        size = max(len(f["input_ids"]) for f in features)
        return {key: torch.tensor([f[key] + [pad] * (size - len(f[key])) for f in features], dtype=torch.long)
                for key, pad in [("input_ids", self.pad_id), ("attention_mask", 0), ("labels", -100)]}


def generate_validation(model, tokenizer, rows, task, count, max_new_tokens):
    import torch
    outputs, exact, correct, parseable = [], 0, 0, 0
    model.eval()
    device = model.get_input_embeddings().weight.device
    for row in rows[:count]:
        prefix = tokenizer.apply_chat_template([
            {"role": "system", "content": row["system"]},
            {"role": "user", "content": row["user"]}], tokenize=True, add_generation_prompt=True)
        x = torch.tensor([prefix], device=device)
        with torch.no_grad():
            y = model.generate(x, attention_mask=torch.ones_like(x), max_new_tokens=max_new_tokens,
                               do_sample=False, pad_token_id=tokenizer.pad_token_id,
                               eos_token_id=tokenizer.eos_token_id)
        text = tokenizer.decode(y[0, len(prefix):], skip_special_tokens=True)
        try:
            parsed = json.loads(text)
            if task == "treatment_plan":
                plan_target(parsed)
            elif (not isinstance(parsed, dict) or set(parsed) != {"diagnosis"}
                  or parsed["diagnosis"] not in DIAGNOSES):
                raise ValueError()
        except (ValueError, TypeError):
            continue
        target = json.loads(row["completion"])
        parseable += 1
        correct += parsed["diagnosis"] == target["diagnosis"]
        exact += parsed == target
        outputs.append({"case_id": row["case_id"], **parsed})
    return outputs, {"requested": count, "parseable": parseable, "diagnosis_correct": correct,
                     "diagnosis_accuracy": correct / count if count else None,
                     "target_exact_match": exact / count if count else None,
                     "clinical_adequacy": "not assessed; exact match and loss are not clinical validity"}


def run(args, root: Path) -> dict:
    training_settings(args)
    manifest, rows = load_bundle(args.bundle, root, allow_real=args.i_confirm_team_decision)
    if args.cpu_smoke and not manifest["synthetic"]:
        raise TrainingError("CPU smoke accepts synthetic fixtures only")
    if args.cpu_smoke and (args.model_dir is not None or args.preflight or args.load_in_4bit):
        raise TrainingError("CPU smoke cannot load a real model, use quantization or run preflight")
    if args.cpu_smoke and (args.max_steps < 1 or args.max_steps > 10):
        raise TrainingError("CPU smoke needs --max-steps between 1 and 10")
    if not args.cpu_smoke and args.model_dir is None:
        raise TrainingError("provide a local Hugging Face --model-dir; no automatic model downloads")
    # Keep both preflight and trained outputs outside the repo; never overwrite another run.
    from clinverify.models.training_data import private_location
    private_location(args.out, root)
    offline_environment()
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              Trainer, TrainerCallback, TrainingArguments, set_seed)

    set_seed(args.seed)
    if args.cpu_smoke:
        model, tokenizer = smoke_model()
        fingerprint = {"random_tiny_gpt2": "constructed locally; no pretrained model"}
    else:
        tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), local_files_only=True, trust_remote_code=False)
        model = None
        fingerprint = model_fingerprint(args.model_dir)
    if not tokenizer.chat_template or tokenizer.eos_token_id is None:
        raise TrainingError("tokenizer needs a chat template and EOS token")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded = {k: [encode_row(tokenizer, row, args.max_length) for row in v] for k, v in rows.items()}
    lengths = {k: {"examples": len(v), "max_tokens": max(len(r["input_ids"]) for r in v),
                    "completion_tokens": sum(sum(t != -100 for t in r["labels"]) for r in v)} for k, v in encoded.items()}
    if args.cpu_smoke and max(v["max_tokens"] for v in lengths.values()) + args.max_new_tokens > 1024:
        raise TrainingError("tiny smoke model supports at most 1024 context plus generated tokens")
    run = {"schema_version": 1, "task": manifest["task"], "synthetic": manifest["synthetic"],
           "started_at_utc": datetime.now(timezone.utc).isoformat(),
           "mode": "cpu_smoke" if args.cpu_smoke else "preflight" if args.preflight else "lora_training",
           "bundle_sha256": digest(args.bundle / "manifest.json"), "base_model_files_sha256": fingerprint,
           "decision": manifest["decision"], "lengths": lengths,
           "python": platform.python_version(),
           "packages": {p: version(p) for p in ["torch", "transformers", "peft", "accelerate", "tokenizers", "safetensors"]},
           "settings": {k: getattr(args, k) for k in ["seed", "epochs", "max_steps", "learning_rate", "max_length",
                        "batch_size", "gradient_accumulation", "lora_rank", "lora_alpha", "load_in_4bit",
                        "validation_generations", "max_new_tokens"]}}
    try:
        run["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        run["working_tree_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        run.update(git_commit="unknown", working_tree_dirty=None)
    if args.preflight:
        out = new_private_dir(args.out, root)
        write_json(out / "run.json", {**run, "status": "preflight_only_no_training"})
        return {"status": "preflight_only_no_training", "lengths": lengths}
    if not args.cpu_smoke:
        if not torch.cuda.is_available():
            raise TrainingError("real training requires CUDA; use synthetic CPU smoke on the Mac")
        precision = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                  bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=precision) if args.load_in_4bit else None
        model = AutoModelForCausalLM.from_pretrained(str(args.model_dir), local_files_only=True,
                    trust_remote_code=False, quantization_config=quant, torch_dtype=precision, device_map={"": 0})
        if args.load_in_4bit:
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                                    gradient_checkpointing_kwargs={"use_reentrant": False})
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        torch.cuda.reset_peak_memory_stats()
        run["gpu"] = {"name": torch.cuda.get_device_name(0), "cuda": torch.version.cuda,
                      "capability": list(torch.cuda.get_device_capability(0)),
                      "total_memory_bytes": torch.cuda.get_device_properties(0).total_memory}
    else:
        precision = torch.float32
        torch.set_num_threads(1)
    model.config.use_cache = False
    out = new_private_dir(args.out, root)
    if args.cpu_smoke:
        # Save the unwrapped random base before injecting LoRA layers.
        model.save_pretrained(out / "smoke_base", safe_serialization=True)
    config = LoraConfig(task_type="CAUSAL_LM", r=args.lora_rank, lora_alpha=args.lora_alpha,
                        lora_dropout=0.05, bias="none", target_modules=["c_attn"] if args.cpu_smoke else "all-linear")
    model = get_peft_model(model, config)
    run["trainable_parameters"], run["total_parameters"] = model.get_nb_trainable_parameters()
    write_json(out / "run.started.json", run)

    class Timing(TrainerCallback):
        def __init__(self):
            self.step_seconds = []
            self.start = None

        def on_step_begin(self, args, state, control, **kwargs):
            if torch.cuda.is_available() and not run["synthetic"]:
                torch.cuda.synchronize()
            self.start = time.perf_counter()

        def on_step_end(self, args, state, control, **kwargs):
            if torch.cuda.is_available() and not run["synthetic"]:
                torch.cuda.synchronize()
            self.step_seconds.append(time.perf_counter() - self.start)

        def on_log(self, args, state, control, logs=None, **kwargs):
            if any(isinstance(v, (int, float)) and not math.isfinite(v) for v in (logs or {}).values()):
                raise TrainingError("nonfinite training metric; run failed")

    timing = Timing()
    ta = TrainingArguments(output_dir=str(out / "checkpoints"), num_train_epochs=args.epochs,
             max_steps=args.max_steps, per_device_train_batch_size=args.batch_size,
             per_device_eval_batch_size=1, gradient_accumulation_steps=args.gradient_accumulation,
             learning_rate=args.learning_rate, logging_steps=1, eval_strategy="epoch", save_strategy="no",
             report_to="none", push_to_hub=False, disable_tqdm=True, dataloader_num_workers=0,
             dataloader_pin_memory=False, seed=args.seed, data_seed=args.seed,
             bf16=precision == torch.bfloat16, fp16=precision == torch.float16,
             use_cpu=args.cpu_smoke, optim="adamw_torch", remove_unused_columns=False, label_names=["labels"])
    trainer = Trainer(model=model, args=ta, train_dataset=encoded["train"], eval_dataset=encoded["val"],
                      data_collator=CompletionCollator(tokenizer.pad_token_id), callbacks=[timing])
    started = time.perf_counter()
    try:
        trained = trainer.train()
        last_eval = next((entry for entry in reversed(trainer.state.log_history)
                          if "eval_loss" in entry and entry.get("step") == trainer.state.global_step), None)
        metrics = ({k: v for k, v in last_eval.items() if k.startswith("eval_")} if last_eval else trainer.evaluate())
        if not math.isfinite(metrics["eval_loss"]):
            raise TrainingError("nonfinite validation loss")
        model.save_pretrained(out / "adapter", safe_serialization=True)
        tokenizer.save_pretrained(out / "adapter")
        write_json(out / "loss_history.json", trainer.state.log_history)
        write_json(out / "step_seconds.json", timing.step_seconds)
        steps_per_epoch = math.ceil(math.ceil(len(rows["train"]) / args.batch_size) / args.gradient_accumulation)
        planned_steps = math.ceil(args.epochs * steps_per_epoch)
        stable_times = timing.step_seconds[2:]
        run.update(status="completed", training_metrics=trained.metrics, validation_metrics=metrics,
                   elapsed_seconds=time.perf_counter() - started, global_step=trainer.state.global_step,
                   step_limited=args.max_steps > 0, full_schedule_update_steps=planned_steps,
                   estimated_full_update_seconds=(statistics.median(stable_times) * planned_steps if stable_times else None),
                   estimate_excludes="model loading, hashing, tokenization, evaluation, generation and checkpoint saving",
                   peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated() if not args.cpu_smoke else None)
        if args.validation_generations:
            count = min(args.validation_generations, len(rows["val"]))
            outputs, scores = generate_validation(model, tokenizer, rows["val"], manifest["task"], count, args.max_new_tokens)
            write_json(out / "validation_predictions.json", outputs)
            write_json(out / "validation_scores.json", scores)
            run["validation_generation"] = scores
            # A loader-compatible plan list is available only in treatment_plan mode.
            run["validation_plan_loader_compatible"] = manifest["task"] == "treatment_plan"
        run["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(out / "run.json", run)
    except Exception as e:
        if not (out / "loss_history.json").exists():
            write_json(out / "loss_history.json", trainer.state.log_history)
        write_json(out / "run.failed.json", {"status": "failed", "error_type": type(e).__name__,
                                            "global_step": trainer.state.global_step,
                                            "finished_at_utc": datetime.now(timezone.utc).isoformat()})
        raise
    return {"status": "completed", "mode": run["mode"], "task": run["task"],
            "synthetic": run["synthetic"], "global_step": run["global_step"],
            "eval_loss": metrics["eval_loss"], "estimated_full_update_seconds": run["estimated_full_update_seconds"]}
