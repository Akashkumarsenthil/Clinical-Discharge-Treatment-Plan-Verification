"""Fixed, reproducible, stratified splits of the 2,400 Ext-CDM cases, plus a leakage check.

Only case IDs (hadm_id) are written; no patient text. Split files are version controlled.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 298
N_TEST = 100            # held-out evaluation set (abstract: 100 held-out cases)
VAL_FRACTION = 0.20     # share of the remaining development cases used for validation


def _stratified_take(cases: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.Index:
    """Pick n rows, keeping each pathology's share (largest-remainder rounding)."""
    share = cases["pathology"].value_counts(normalize=True) * n
    base = share.astype(int)
    remainder = n - int(base.sum())
    for label in (share - base).sort_values(ascending=False).index[:remainder]:
        base[label] += 1
    picked = []
    for label, k in base.items():
        pool = cases.index[cases["pathology"] == label]
        picked.extend(rng.choice(pool, size=int(k), replace=False))
    return pd.Index(picked)


def make_splits(cases: pd.DataFrame, seed: int = SEED) -> dict[str, list[int]]:
    cases = cases.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    test_idx = _stratified_take(cases, N_TEST, rng)
    dev = cases.drop(index=test_idx)
    val_idx = _stratified_take(dev, int(round(len(dev) * VAL_FRACTION)), rng)
    train = dev.drop(index=val_idx)
    return {
        "train": sorted(int(x) for x in train["hadm_id"]),
        "val": sorted(int(x) for x in dev.loc[val_idx, "hadm_id"]),
        "test": sorted(int(x) for x in cases.loc[test_idx, "hadm_id"]),
    }


def leakage_check(splits: dict[str, list[int]], cases: pd.DataFrame) -> list[str]:
    """Return problems; empty list means no leakage and complete coverage."""
    problems = []
    names = list(splits)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = set(splits[a]) & set(splits[b])
            if both:
                problems.append(f"{len(both)} cases appear in both {a} and {b}")
    union = [h for s in splits.values() for h in s]
    if len(union) != len(set(union)):
        problems.append("duplicate case IDs inside the splits")
    if set(union) != set(cases["hadm_id"]):
        problems.append(f"splits do not cover exactly the {len(cases):,} cases")
    return problems


def split_summary(splits: dict[str, list[int]], cases: pd.DataFrame) -> pd.DataFrame:
    label = cases.set_index("hadm_id")["pathology"]
    rows = {name: label.loc[ids].value_counts() for name, ids in splits.items()}
    out = pd.DataFrame(rows).fillna(0).astype(int)
    out.loc["total"] = out.sum()
    return out


def save_splits(splits: dict[str, list[int]], directory: Path, seed: int = SEED,
                filename: str = "ext_cdm_splits_v2.json", grouped_by: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    meta = {"seed": seed, "n_test": N_TEST, "val_fraction": VAL_FRACTION}
    if grouped_by:
        meta["grouped_by"] = grouped_by
    path.write_text(json.dumps({**meta, "splits": splits}, indent=1))
    return path


# ------------------------------------------------------------------ patient-level splits (v2)
def patient_overlap(splits: dict[str, list[int]], subject_of: pd.Series) -> dict[str, int]:
    """Number of patients (subject_id) present in each pair of splits."""
    by_split = {name: set(subject_of.loc[ids]) for name, ids in splits.items()}
    names = list(by_split)
    return {f"{a}+{b}": len(by_split[a] & by_split[b])
            for i, a in enumerate(names) for b in names[i + 1:]}


def patient_leakage_check(splits: dict[str, list[int]], subject_of: pd.Series) -> list[str]:
    return [f"{n} patients appear in both {pair.replace('+', ' and ')}"
            for pair, n in patient_overlap(splits, subject_of).items() if n]


def _grouped_take(cases: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.Index:
    """Pick n cases keeping each pathology's share, taking whole patients (all their admissions) at once."""
    share = cases["pathology"].value_counts(normalize=True) * n
    quota = share.astype(int)
    for label in (share - quota).sort_values(ascending=False).index[: n - int(quota.sum())]:
        quota[label] += 1
    quota = quota.to_dict()
    groups = [idx for _, idx in cases.groupby("subject_id").groups.items()]
    order = rng.permutation(len(groups))
    picked: list = []
    for g in order:
        idx = groups[g]
        need = cases.loc[idx, "pathology"].value_counts()
        if all(need[k] <= quota.get(k, 0) for k in need.index):
            picked.extend(idx)
            for k, v in need.items():
                quota[k] -= v
        if sum(quota.values()) == 0:
            break
    if sum(quota.values()) != 0:
        raise ValueError(f"could not fill the quotas without splitting a patient: {quota}")
    return pd.Index(picked)


def make_grouped_splits(cases: pd.DataFrame, subject_of: pd.Series, seed: int = SEED,
                        n_test: int = N_TEST, val_fraction: float = VAL_FRACTION) -> dict[str, list[int]]:
    """Stratified train/val/test split in which no patient appears in more than one split."""
    cases = cases.reset_index(drop=True).copy()
    cases["subject_id"] = cases["hadm_id"].map(subject_of)
    rng = np.random.default_rng(seed)
    test_idx = _grouped_take(cases, n_test, rng)
    dev = cases.drop(index=test_idx)
    val_idx = _grouped_take(dev, int(round(len(dev) * val_fraction)), rng)
    train = dev.drop(index=val_idx)
    return {
        "train": sorted(int(x) for x in train["hadm_id"]),
        "val": sorted(int(x) for x in dev.loc[val_idx, "hadm_id"]),
        "test": sorted(int(x) for x in cases.loc[test_idx, "hadm_id"]),
    }
