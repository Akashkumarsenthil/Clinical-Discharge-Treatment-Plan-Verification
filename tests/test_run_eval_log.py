"""run_eval.py keeps one log per run, even for runs started in the same second (README Quickstart runs two back to back)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_eval(plans: str, rules: str, out: Path) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_eval.py"), "--plans", plans, "--rules", rules,
                    "--out", str(out)], cwd=ROOT, check=True, capture_output=True)


def test_back_to_back_runs_keep_separate_logs(tmp_path):
    run_eval("tests/data/toy_labeled_plans.json", "tests.toy_rules", tmp_path)
    run_eval("tests/data/catalog_labeled_plans.json", "clinverify.rules.catalog", tmp_path)
    run_eval("tests/data/catalog_labeled_plans.json", "clinverify.rules.catalog", tmp_path)
    names = sorted(p.name for p in tmp_path.glob("run_*.json"))
    assert len(names) == 3
    assert sum("toy_labeled_plans" in n for n in names) == 1
    assert sum("catalog_labeled_plans" in n for n in names) == 2
