# Cloud Airflow (GCP VM)

TA checklist §3: Airflow on a GCP VM via Docker Compose — not Cloud Composer.

## Shared team URL + login (UI)

One Airflow for the whole team — **same VM, same URL pattern, same password**. There is no per-person UI.

| Field | Value |
|-------|--------|
| GCP project | `clinverify-298a` |
| VM name | `clinverify-airflow` (zone `us-west1-b`) |
| URL | `http://localhost:8080` through an IAP tunnel (port 8080 is **not** open to the internet) |
| Username | `admin` (shared) |
| Password | `admin` (shared) |

```bash
# Open the shared UI (needs roles/iap.tunnelResourceAccessor; keep this terminal open):
gcloud compute start-iap-tunnel clinverify-airflow 8080 \
  --local-host-port=localhost:8080 \
  --project=clinverify-298a --zone=us-west1-b
# Then open http://localhost:8080
```

The firewall rule `allow-airflow-8080` admits only Google's IAP range (`35.235.240.0/20`), so the UI is reachable
only through the tunnel by project members. The VM holds MIMIC data; do not reopen 8080 to `0.0.0.0/0`.

Airflow 3 Simple auth: `SIMPLE_AUTH_MANAGER_USERS=admin:admin` means user **admin** with role **admin** (the second `admin` is the *role*, not the password). The password is fixed in [`config/simple_auth_manager_passwords.json`](../config/simple_auth_manager_passwords.json) as `{"admin": "admin"}`.

**Stop the VM** when you are done (cost, and nothing left running with MIMIC data on it).

## One-time layout on the VM

- Repo: `/opt/clinverify` (dags, scripts, src, results)
- MIMIC working set: `/data/mimic` with
  - `mimic-iv-ext-cdm-1.1/`
  - `physionet.org/files/mimiciv/3.1/hosp/admissions.csv.gz` (+ `SHA256SUMS.txt`)
  - `warehouse/` writable (DuckDB file; compose mounts `MIMIC_DIR` read-write)
- Compose file: `/opt/clinverify/docker-compose.yml`
- Env file `/opt/clinverify/.env`:

```
AIRFLOW_UID=50000
MIMIC_DIR=/data/mimic
```

## Start (after VM was stopped)

```bash
gcloud compute instances start clinverify-airflow \
  --project=clinverify-298a --zone=us-west1-b

gcloud compute ssh clinverify-airflow \
  --project=clinverify-298a --zone=us-west1-b \
  --command='cd /opt/clinverify && docker compose up -d'
```

Open the IAP tunnel (above), then `http://localhost:8080`, and sign in with the **shared** team login above (`admin` / `admin`).

Unpause and trigger:

```bash
docker compose exec airflow-scheduler airflow dags unpause clinverify_pipeline
docker compose exec airflow-scheduler airflow dags trigger clinverify_pipeline
```

## Stop (save budget)

```bash
gcloud compute ssh clinverify-airflow \
  --project=clinverify-298a --zone=us-west1-b \
  --command='cd /opt/clinverify && docker compose down'

gcloud compute instances stop clinverify-airflow \
  --project=clinverify-298a --zone=us-west1-b
```

## Ollama (model / G-Eval tasks only)

Data → warehouse tasks do **not** need Ollama. `generate_plans` and `g_eval` do.

On the VM host:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve   # or enable the systemd service
ollama pull qwen2.5:14b
ollama pull llama3.1:8b
```

Compose maps `host.docker.internal` → the VM host so containers reach Ollama on port 11434.
Prefer a larger machine (or GPU) for 14B; e2-medium is for UI / data-half only.
