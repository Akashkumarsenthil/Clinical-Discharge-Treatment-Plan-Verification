"""Summarize the manual audit of the derived case facts into agreement counts (no patient text).

Run after a reviewer has filled the column "reviewer_agrees (yes/no/unsure)" in results/audit_sample.csv:
    python scripts/summarize_audit.py
Writes docs/case_facts_validation.csv (counts only, safe to commit) and prints it. Rows without an answer are counted as pending. For "unknown" rows, "yes" means the unknown is right and "no" means the record does establish the fact.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANSWER = "reviewer_agrees (yes/no/unsure)"


def main() -> int:
    src = ROOT / "results" / "audit_sample.csv"
    df = pd.read_csv(src, keep_default_na=False)
    df["answer"] = df[ANSWER].str.strip().str.lower().replace({"": "pending", "y": "yes", "n": "no", "u": "unsure"})
    bad = sorted(set(df["answer"]) - {"yes", "no", "unsure", "pending"})
    if bad:
        print("unexpected answers (use yes / no / unsure):", bad)
        return 1
    keys = ["pathology", "fact", "derived_value", "evidence_source"]
    out = (df.groupby(keys + ["answer"]).size().unstack(fill_value=0).reindex(columns=["yes", "no", "unsure", "pending"], fill_value=0)
           .reset_index())
    out["reviewed"] = out[["yes", "no", "unsure"]].sum(axis=1)
    out["agreement"] = (out["yes"] / out["reviewed"]).round(2).where(out["reviewed"] > 0)
    out_path = ROOT / "docs" / "case_facts_validation.csv"
    out.to_csv(out_path, index=False)
    print(out.to_string(index=False))
    done = int(out["reviewed"].sum())
    print(f"\n{done} of {len(df)} sampled cases reviewed; overall agreement "
          f"{(out['yes'].sum() / done):.0%}" if done else "\nno rows reviewed yet")
    print("wrote", out_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
