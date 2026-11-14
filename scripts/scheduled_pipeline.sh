#!/bin/bash
# RETIRED (TA checklist §3). Do not schedule this script.
#
# The warehouse + Model A + Z3 + G-Eval chain is now the Airflow DAG
#   dags/clinverify_pipeline.dag.py
# Run locally with `airflow standalone` (see docs/airflow_setup.md) or on a GCP
# VM with Docker Compose (docker-compose.yml). Windows Task Scheduler /
# cron should point at Airflow, not this wrapper.
#
# Kept only so old Task Scheduler entries fail loudly instead of silently.
echo "scheduled_pipeline.sh is retired. Use Airflow DAG clinverify_pipeline." >&2
echo "See docs/airflow_setup.md and docker-compose.yml." >&2
exit 2
