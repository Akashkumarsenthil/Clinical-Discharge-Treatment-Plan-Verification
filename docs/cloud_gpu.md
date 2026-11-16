# GPU + Ollama on the cloud Airflow VM

Work item: [T6-206](https://linear.app/298a-team-6-neurosymbolic/issue/T6-206). Script: [`scripts/setup_gpu_vm.sh`](../scripts/setup_gpu_vm.sh).
Airflow itself (Compose, start/stop, UI) is in [`airflow_cloud.md`](airflow_cloud.md).

The data and warehouse tasks run on the e2-medium VM. `generate_plans` and `g_eval` need a local LLM, so the same VM
is switched to **g2-standard-4 (1x NVIDIA L4, 24 GB)** for model runs. Ollama runs on the VM host; Airflow containers
reach it through `host.docker.internal`. MIMIC text never leaves the VM: generation and G-Eval refuse any Ollama host
that is not local.

The VM lives in **us-west1-a**. It was moved from us-west1-b on 2026-11-15 because us-west1-b had no L4 capacity
(`ZONE_RESOURCE_POOL_EXHAUSTED`); the boot disk was snapshotted first, so data and models carried over. If a zone runs
out again, set `ZONE=...` for the script. If SSH on port 22 times out from your network, add `--tunnel-through-iap`.

## Prerequisites (project owner)

| Need | Why |
|---|---|
| Quota `GPUS_ALL_REGIONS` ≥ 1 (and `NVIDIA_L4_GPUS` ≥ 1 in us-west1) | No GPU VM can start at 0. Free-trial billing keeps it at 0. |
| `roles/compute.osAdminLogin` for whoever runs `host` | Installing the driver and Ollama needs sudo |
| A budget alert on the billing account | An L4 left running costs about $500 a month |
| No firewall rule exposing port 11434 | Ollama has no authentication |

`bash scripts/setup_gpu_vm.sh preflight` checks all of these except the role and the budget (read-only).

## Steps

```bash
# laptop
bash scripts/setup_gpu_vm.sh preflight
bash scripts/setup_gpu_vm.sh to-gpu            # VM must be stopped; DRY_RUN=1 to preview
gcloud compute instances start clinverify-airflow --project=clinverify-298a --zone=us-west1-a
gcloud compute ssh clinverify-airflow --project=clinverify-298a --zone=us-west1-a

# on the VM
sudo bash /opt/clinverify/scripts/setup_gpu_vm.sh host   # if the VM reboots for the driver, rerun
bash /opt/clinverify/scripts/setup_gpu_vm.sh check       # GPU, models, reachable from a container
```

Smoke test before a full DAG run (validation split, 5 cases):

```bash
cd /opt/clinverify && MIMIC_DIR=/data/mimic python scripts/generate_model_a_plans.py \
  --cohort validation --seed 298 --limit 5 --out /tmp/smoke
```

## Cost and stopping

| State | Cost (approximate) |
|---|---|
| g2-standard-4 running | about $0.70 per hour |
| Stopped | disk only, about $10 per month for 100 GB pd-balanced |
| One 460-case validation run | about 25 minutes of generation (about 3.3 s per case); the full DAG with G-Eval about 1 hour |

Stop the VM after every session (`docker compose down`, then `gcloud compute instances stop`).
To go back to the cheap machine: `bash scripts/setup_gpu_vm.sh to-cpu` (the disk keeps its new size).

If the zone has no L4 capacity (`ZONE_RESOURCE_POOL_EXHAUSTED`), `to-cpu` still lets you start the VM on e2-medium to
read results or logs; switch back with `to-gpu` when capacity returns.

## Memory: one model at a time

g2-standard-4 has 16 GB of host RAM. In the first full run (2026-11-15), qwen2.5:14b was still loaded from
`generate_plans` when the llama3.1:8b judge loaded for `g_eval`; with Airflow also running, the host ran out of memory
and the kernel OOM killer stopped Ollama after 61 plans. systemd restarted it within seconds, but every remaining
judge call had already failed, and G-Eval reported a mean over 61 of 460 plans.

Fixes: `host` now sets `OLLAMA_MAX_LOADED_MODELS=1`, so Ollama unloads one model before loading the next; G-Eval
retries a refused connection for about a minute; and `run_geval.py` exits non-zero when any plan is left unscored,
so the `g_eval` task fails instead of reporting a partial mean. On a VM set up before this change, rerun
`sudo bash /opt/clinverify/scripts/setup_gpu_vm.sh host`. To check after a run: `journalctl -u ollama | grep -i oom`.
