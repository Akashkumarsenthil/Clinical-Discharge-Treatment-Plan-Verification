"""Prepare local train/validation SFT bundles. --synthetic never opens MIMIC files."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clinverify.models.training_data import prepare, TrainingError  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True, choices=["diagnosis", "treatment_plan"])
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--data-dir", type=Path, help="local mimic-iv-ext-cdm-1.1 directory")
    p.add_argument("--decision", type=Path)
    p.add_argument("--targets", type=Path)
    a = p.parse_args()
    try:
        m = prepare(ROOT, task=a.task, out=a.out, synthetic=a.synthetic,
                    data_dir=a.data_dir, decision=a.decision, targets=a.targets)
        print(f"Prepared {m['task']}: train={m['counts']['train']}, validation={m['counts']['val']}; synthetic={m['synthetic']}")
        return 0
    except TrainingError as e:
        print(str(e), file=sys.stderr)
    except Exception as e:
        print(f"Preparation failed ({type(e).__name__}); no patient values printed", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
