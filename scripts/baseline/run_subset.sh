#!/bin/bash
# Hager baseline, local deviation: Llama 3.1 8B Instruct (4-bit), fixed 100-case subset per pathology (sampling seed 298).
# No time limit. Detached; log per pathology in ~/baseline/subset_<pathology>.log
cd ~/baseline/hager_fw && source ../.venv/bin/activate
for p in appendicitis cholecystitis diverticulitis pancreatitis; do
  python run.py paths=local model=Llama3.1Instruct8B pathology=$p \
    patient_list_path=/home/akash/baseline/cdm_work/subset100_$p.txt run_descr=_subset100 \
    > ~/baseline/subset_$p.log 2>&1
  echo "$p exit $?" >> ~/baseline/subset_status.txt
done
echo ALL_DONE >> ~/baseline/subset_status.txt
