"""Unit tests on tiny synthetic tables (no patient data)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data import splits as S  # noqa: E402

IDS = {"a": list(range(1, 61)), "b": list(range(61, 91)), "c": list(range(91, 111))}  # 110 cases


def tables():
    hadm = [h for v in IDS.values() for h in v]
    t = {n: pd.DataFrame({"hadm_id": hadm, "x": "text"}) for n in E.CASE_LEVEL}
    for n in E.EVENT_LEVEL:
        t[n] = pd.DataFrame({"hadm_id": hadm + hadm[:5], "x": "v"}).drop_duplicates()
    return t


def test_clean_removes_exact_duplicates_only():
    t = tables()
    t["icd_procedures"] = pd.concat([t["icd_procedures"], t["icd_procedures"].iloc[:4]])
    cleaned, rep = E.clean_tables(t)
    row = rep.set_index("table").loc["icd_procedures"]
    assert row["duplicate_rows"] == 4 and len(cleaned["icd_procedures"]) == row["rows_after"]


def test_validation_passes_on_good_data():
    assert E.validate_tables(tables(), IDS) == []


def test_validation_catches_unknown_id_and_duplicate_case():
    t = tables()
    t["microbiology"].loc[0, "hadm_id"] = -1
    t["history_of_present_illness"] = pd.concat([t["history_of_present_illness"], t["history_of_present_illness"].iloc[:2]])
    problems = " | ".join(E.validate_tables(t, IDS))
    assert "not in pathology_ids" in problems and "duplicated hadm_id" in problems


def test_validation_catches_missing_column():
    t = tables()
    t["laboratory_tests"] = t["laboratory_tests"].drop(columns=["hadm_id"])
    assert any("missing columns" in p for p in E.validate_tables(t, IDS))


def test_splits_are_disjoint_complete_stratified_and_reproducible():
    cases = E.case_table(IDS)
    a, b = S.make_splits(cases, seed=1), S.make_splits(cases, seed=1)
    assert a == b
    assert S.leakage_check(a, cases) == []
    assert len(a["test"]) == S.N_TEST
    share = cases["pathology"].value_counts(normalize=True)
    test_share = cases.set_index("hadm_id").loc[a["test"], "pathology"].value_counts(normalize=True)
    assert all(abs(test_share[k] - share[k]) < 0.05 for k in share.index)


def test_leakage_check_detects_overlap():
    cases = E.case_table(IDS)
    s = S.make_splits(cases, seed=1)
    s["test"][0] = s["train"][0]
    assert any("both train and test" in p for p in S.leakage_check(s, cases))


def test_transform_parses_lab_values_units_and_flags(tmp_path):
    t = tables()
    t["laboratory_tests"] = pd.DataFrame({
        "hadm_id": [1, 1, 1, 1], "itemid": [10, 10, 10, 10],
        "valuestr": ["2.5 mmol/L", "9.0 mmol/L", "NEG", ">100 mg/dL"],
        "ref_range_lower": [3.0, 3.0, 3.0, None], "ref_range_upper": [6.0, 6.0, 6.0, None]})
    pd.DataFrame({"itemid": [10.0], "label": ["X"], "fluid": ["Blood"], "category": ["c"],
                  "count": [1.0], "corresponding_ids": ["[]"]}).to_csv(tmp_path / "lab_test_mapping.csv", index=False)
    (tmp_path / "pathology_ids.json").write_text('{"a": [1]}')
    for n in E.TEXT_COLUMNS:
        col = E.TEXT_COLUMNS[n]
        t[n] = pd.DataFrame({"hadm_id": [1], col: ["  two   words "]})
    for n in ("microbiology", "icd_diagnosis"):
        t[n] = pd.DataFrame({"hadm_id": [1], "x": ["v"]})
    t["discharge_procedures"] = pd.DataFrame({"hadm_id": [1, 1], "discharge_procedure": ["p", None]})
    out = E.transform_tables(t, directory=tmp_path)
    labs = out["laboratory_tests"]
    assert labs["flag"].tolist() == ["low", "high", "unknown", "unknown"]
    assert labs["unit"].iloc[0] == "mmol/L" and labs["qualifier"].iloc[3] == ">"
    assert out["history_of_present_illness"]["hpi"].iloc[0] == "two words"
    assert len(out["discharge_procedures"]) == 1


def _grouped_fixture():
    cases = E.case_table(IDS)                      # 110 cases, 3 pathologies
    patients = {h: h for h in cases["hadm_id"]}   # one patient per admission ...
    for extra, owner in [(2, 1), (3, 1), (62, 61), (95, 91), (96, 91), (100, 99)]:
        patients[extra] = owner                    # ... except these shared patients (same pathology)
    return cases, pd.Series(patients)


def test_grouped_splits_keep_each_patient_in_one_split():
    cases, subject_of = _grouped_fixture()
    kw = dict(n_test=20, val_fraction=0.2)
    s = S.make_grouped_splits(cases, subject_of, seed=3, **kw)
    assert S.leakage_check(s, cases) == []
    assert S.patient_leakage_check(s, subject_of) == []
    assert len(s["test"]) == 20 and len(s["val"]) == 18 and len(s["train"]) == 72
    assert S.make_grouped_splits(cases, subject_of, seed=3, **kw) == s


def test_patient_leakage_check_flags_shared_patient():
    cases, subject_of = _grouped_fixture()
    s = {"train": [1, 5], "val": [2, 7], "test": [3, 9]}      # admissions 1, 2, 3 are the same patient
    assert S.patient_overlap(s, subject_of)["train+val"] == 1
    assert any("both train and val" in p for p in S.patient_leakage_check(s, subject_of))


def test_synthetic_dataset_runs_through_the_whole_pipeline(tmp_path):
    """A clean clone has no credentialed data: the synthetic stand-in must pass the same pipeline end to end."""
    from clinverify.data import synthetic
    root = synthetic.generate(tmp_path / "synth", n_cases=400, seed=5)
    ext, mimic = root / "mimic-iv-ext-cdm-1.1", root / "physionet.org/files/mimiciv/3.1"
    ids = E.load_pathology_ids(ext)
    cases = E.case_table(ids)
    assert len(cases) == 400
    cleaned, report = E.clean_tables(E.load_tables(ext))
    assert report["duplicate_rows"].sum() > 0                                  # the generator injects duplicates
    assert E.validate_tables(cleaned, ids) == []
    assert E.validate_tables(E.corrupt(cleaned), ids)                          # corrupted copy is caught
    transformed = E.transform_tables(cleaned, directory=ext)
    assert set(transformed["laboratory_tests"]["flag"]) <= {"low", "normal", "high", "unknown"}
    subject_of = E.subject_map(mimic)
    splits = S.make_grouped_splits(cases, subject_of, seed=5, n_test=60)
    assert S.leakage_check(splits, cases) == [] and S.patient_leakage_check(splits, subject_of) == []
    assert len(splits["test"]) == 60
