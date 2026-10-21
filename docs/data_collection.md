# Data collection steps (how the data was obtained and checked)

Datasets: MIMIC-IV v3.1 (about 9.9 GB uncompressed) and MIMIC-IV-Ext-CDM v1.1 (17 MB, 2,400 cases).
Licence: PhysioNet Credentialed Health Data License 1.5.0 (no sharing, research use only, no re-identification).

1. Complete the CITI training and get PhysioNet credentialed access (per person).
2. Sign the data use agreement on each dataset page (MIMIC-IV, MIMIC-IV-Ext-CDM). Access is per person; data is not shared.
3. Download to a folder outside the repository, `~/data/mimic/` (set `MIMIC_DIR` to change it):
   - MIMIC-IV: `wget -r -N -c -np --user <username> --ask-password https://physionet.org/files/mimiciv/3.1/` (resumable)
   - Ext-CDM: download from its PhysioNet page.
4. Verify integrity: compare every file with `SHA256SUMS.txt` shipped with the dataset (`python scripts/data_demo.py manifest`).
   Result: MIMIC-IV 33 of 33 files match; Ext-CDM 12 of 12 files match.
5. Link check: all 2,400 Ext-CDM `hadm_id` values exist in MIMIC-IV `admissions` (546,028 admissions).
6. Only code, configuration, split ID lists and manifests go in the repository. `.gitignore` blocks the data folders.
7. No MIMIC text is sent to hosted LLM APIs.
8. The pipeline demo uses the 17 MB Ext-CDM extract. It does not load the rest of MIMIC-IV.

Reproduce the demo: run `notebooks/data_pipeline_demo.ipynb`, or `python scripts/data_demo.py all`.
