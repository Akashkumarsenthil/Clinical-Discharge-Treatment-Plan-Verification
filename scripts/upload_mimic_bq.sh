#!/bin/bash
# Upload MIMIC-IV data to BigQuery project clinverify-298a (sjsu.edu account).
# Requires: gcloud auth login (sneha.singh@sjsu.edu) + bq CLI installed.
# MIMIC data files must be on the local machine (PhysioNet DUA — no cloud transfer).
#
# Usage:
#   bash scripts/upload_mimic_bq.sh
#
# Data paths (default):
#   CDM:  ~/data/mimic/mimic-iv-ext-cdm-1.1/*.csv
#   Hosp: ~/data/mimic/mimiciv-3.1/hosp/admissions.csv.gz

PROJECT="clinverify-298a"
DATASET="mimic"
REGION="US"
CDM_DIR="${MIMIC_CDM_DIR:-$HOME/data/mimic/mimic-iv-ext-cdm-1.1}"
HOSP_DIR="${MIMIC_HOSP_DIR:-$HOME/data/mimic/mimiciv-3.1/hosp}"

echo "=== Creating dataset $DATASET in $PROJECT ==="
bq --project_id="$PROJECT" mk --dataset --location="$REGION" "$PROJECT:$DATASET" 2>/dev/null \
  || echo "Dataset already exists, continuing."

echo "=== Uploading admissions.csv.gz ==="
bq load --source_format=CSV --autodetect --replace \
  --allow_quoted_newlines \
  "$PROJECT:$DATASET.admissions" \
  "$HOSP_DIR/admissions.csv.gz"

echo "=== Uploading CDM tables ==="
for f in "$CDM_DIR"/*.csv; do
  tbl=$(basename "$f" .csv)
  echo "  -> $tbl"
  bq load --source_format=CSV --autodetect --replace \
    --allow_quoted_newlines --max_bad_records=1000 \
    "$PROJECT:$DATASET.$tbl" "$f" \
    || echo "  WARN: $tbl had errors — check BQ console"
done

echo "=== Done. Tables in $PROJECT:$DATASET ==="
bq ls "$PROJECT:$DATASET"
