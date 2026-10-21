"""Create a synthetic stand-in for the MIMIC datasets so the pipeline can be run without PhysioNet access.

    python scripts/make_synthetic_data.py --out ~/synthetic_mimic [--cases 600] [--seed 298]
    MIMIC_DIR=~/synthetic_mimic python scripts/data_demo.py all
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clinverify.data.synthetic import generate  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--out", required=True, type=Path)
ap.add_argument("--cases", type=int, default=600)
ap.add_argument("--seed", type=int, default=298)
args = ap.parse_args()
print("synthetic data written to", generate(args.out.expanduser(), args.cases, args.seed))
