"""Train a local LoRA adapter or run an offline tiny-model software smoke test."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clinverify.models.training_data import TrainingError  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--model-dir", type=Path)
    p.add_argument("--cpu-smoke", action="store_true")
    p.add_argument("--preflight", action="store_true", help="tokenize and record sizes; no training")
    p.add_argument("--load-in-4bit", action="store_true")
    p.add_argument("--i-confirm-team-decision", action="store_true")
    p.add_argument("--seed", type=int, default=298)
    p.add_argument("--epochs", type=float, default=1)
    p.add_argument("--max-steps", type=int, default=-1)
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--max-length", type=int, default=8192)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--gradient-accumulation", type=int, default=8)
    p.add_argument("--lora-rank", type=int, default=8)
    p.add_argument("--lora-alpha", type=int, default=16)
    p.add_argument("--validation-generations", type=int, default=0)
    p.add_argument("--max-new-tokens", type=int, default=256)
    a = p.parse_args()
    try:
        from clinverify.models.finetune import run
        import json
        print(json.dumps(run(a, ROOT), allow_nan=False))
        return 0
    except TrainingError as e:
        print(str(e), file=sys.stderr)
    except Exception as e:
        print(f"Training failed ({type(e).__name__}); details and patient values are not printed", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
