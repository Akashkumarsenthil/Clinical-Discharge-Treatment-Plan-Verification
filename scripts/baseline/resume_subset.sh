#!/bin/bash
# Resume the Hager baseline subset after an interruption (shutdown, sleep, WSL restart).
# For each pathology it reads every earlier *_subset100_results.pkl, removes the cases already finished, and runs only the rest.
# Safe to run repeatedly. An interrupted case is not saved and is simply redone.
cd ~/baseline/hager_fw && source ../.venv/bin/activate
for p in appendicitis cholecystitis diverticulitis pancreatitis; do
  python - "$p" <<'PY'
import sys, glob, pickle
sys.path.insert(0, ".")
from utils.logging import read_from_pickle_file
p = sys.argv[1]
want = [int(x) for x in open(f"/home/akash/baseline/cdm_work/subset100_{p}.txt").read().split()]
done = set()
for f in glob.glob(f"/home/akash/baseline/logs/{p}_ZeroShot_*_subset100/*_results.pkl"):
    for r in read_from_pickle_file(f):
        done |= {int(k) for k in r}
left = [i for i in want if i not in done]
open(f"/home/akash/baseline/cdm_work/remaining_{p}.txt", "w").write("\n".join(map(str, left)) + ("\n" if left else ""))
print(f"{p}: {len(done & set(want))} done, {len(left)} left")
PY
  if [ -s ~/baseline/cdm_work/remaining_$p.txt ]; then
    python run.py paths=local model=Llama3.1Instruct8B pathology=$p \
      patient_list_path=/home/akash/baseline/cdm_work/remaining_$p.txt run_descr=_subset100 \
      > ~/baseline/subset_${p}_resume_$(date +%H%M).log 2>&1
    echo "$p resumed, exit $?" >> ~/baseline/subset_status.txt
  fi
done
echo ALL_DONE >> ~/baseline/subset_status.txt
