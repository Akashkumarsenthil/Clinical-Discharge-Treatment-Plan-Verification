"""Score Hager-framework result pickles the way MIMIC-Clinical-Decision-Making-Analysis/evaluate_cdm.py does.

Usage (from ~/baseline/hager_fw, venv active):
    python ../score_hager.py appendicitis RESULTS.pkl [cholecystitis RESULTS.pkl ...]
Prints, per pathology, n and mean 'Diagnosis' / 'Gracious Diagnosis' score, and the mean over pathologies
(the paper's Fig. 3 'mean diagnostic accuracy' averages the four pathologies). Writes no patient text.
"""
import glob, json, pickle, sys
from collections import Counter
sys.path.insert(0, ".")
from run import load_evaluator
from utils.logging import read_from_pickle_file
from dataset.utils import load_hadm_from_file

BASE = "/home/akash/baseline/cdm_work"
out = {}
args = sys.argv[1:]
for patho, path in zip(args[0::2], args[1::2]):
    info = load_hadm_from_file(f"{patho}_hadm_info_first_diag", base_mimic=BASE)
    results = {}
    for f in sorted(glob.glob(path)):          # a glob merges resumed runs of the same pathology
        for r in read_from_pickle_file(f):
            results.update(r)
    scores = {"Diagnosis": [], "Gracious Diagnosis": []}
    n_skipped = 0
    for _id, res in results.items():
        try:
            ev = load_evaluator(patho)._evaluate_agent_trajectory(
                prediction=res["output"], input=res["input"],
                reference=(info[_id]["Discharge Diagnosis"], info[_id]["ICD Diagnosis"], info[_id].get("Procedures ICD9", []),
                           info[_id].get("Procedures ICD10", []), info[_id].get("Procedures Discharge", [])),   # converter omits the key when a patient has no procedures
                agent_trajectory=res["intermediate_steps"])
        except Exception as err:          # a case the evaluator cannot score counts as not scored, and is reported
            n_skipped += 1
            continue
        for k in scores:
            scores[k].append(ev["scores"][k])
    n = len(scores["Diagnosis"])
    out[patho] = {"n_scored": n, "n_skipped": n_skipped,
                  "Diagnosis": sum(scores["Diagnosis"]) / n if n else None,
                  "Gracious Diagnosis": sum(scores["Gracious Diagnosis"]) / n if n else None}
vals = [v["Diagnosis"] for v in out.values() if v["Diagnosis"] is not None]
out["mean_over_pathologies_Diagnosis"] = sum(vals) / len(vals) if vals else None
print(json.dumps(out, indent=1))
