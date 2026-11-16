#!/usr/bin/env bash
# One command for a cloud validation run: start the GPU VM, deploy main, run the DAG, let the DAG stop the VM.
#
#   bash scripts/cloud_run.sh                          # A0: rag=off, model=base
#   bash scripts/cloud_run.sh rag=on                   # A+RAG
#   bash scripts/cloud_run.sh rag=off rag=on           # both, back to back in one VM session
#   bash scripts/cloud_run.sh rag=on,model=ft          # A+RAG+FT
#
# Each argument is one DAG run (rag=on|off, model=base|ft; defaults rag=off, model=base). They run one after
# another with `airflow dags test`; only the last has auto_stop=on, so its stop_vm teardown stops the VM.
# Safety net: the VM also schedules its own shutdown after MAX_HOURS (default 4), in case a run hangs.
#
# Env: REF (git ref to deploy, default origin/main), MAX_HOURS, PROJECT, ZONE, VM.
# Needs gcloud logged in with access to the project. Nothing here reads or sends MIMIC data.
set -euo pipefail

PROJECT=${PROJECT:-clinverify-298a}
ZONE=${ZONE:-us-west1-a}
VM=${VM:-clinverify-airflow}
REF=${REF:-origin/main}
MAX_HOURS=${MAX_HOURS:-4}
REPO_DIR=/opt/clinverify

die() { echo "ERROR: $*" >&2; exit 1; }
say() { echo "==> $*"; }
g() { gcloud --project="$PROJECT" "$@"; }
vm_ssh() { g compute ssh "$VM" --zone="$ZONE" --tunnel-through-iap --quiet "$@"; }

# ---------------------------------------------------------------- variants -> DAG run confs (validated here)
[ $# -gt 0 ] || set -- "rag=off,model=base"
confs=()
for i in $(seq 1 $#); do
  spec=${!i}; rag=off; model=base
  IFS=, read -ra kvs <<< "$spec"
  for kv in "${kvs[@]}"; do
    case "$kv" in
      rag=on|rag=off) rag=${kv#rag=} ;;
      model=base|model=ft) model=${kv#model=} ;;
      *) die "unknown variant setting '$kv' (use rag=on|off, model=base|ft)" ;;
    esac
  done
  stop=off; [ "$i" -eq $# ] && stop=on
  confs+=("{\"rag\": \"$rag\", \"model\": \"$model\", \"auto_stop\": \"$stop\"}")
done
[[ "$MAX_HOURS" =~ ^[1-9][0-9]*$ ]] || die "MAX_HOURS must be a whole number of hours"

# ---------------------------------------------------------------- code to deploy
repo_root=$(git rev-parse --show-toplevel)
git -C "$repo_root" fetch -q origin
rev=$(git -C "$repo_root" rev-parse --verify "$REF^{commit}") || die "unknown ref $REF"
say "Deploying $REF ($(git -C "$repo_root" log -1 --format='%h %s' "$rev"))"

# ---------------------------------------------------------------- start the VM
status=$(g compute instances describe "$VM" --zone="$ZONE" --format='value(status)')
if [ "$status" != RUNNING ]; then
  say "Starting $VM in $ZONE (about \$0.70/hour while running)"
  if ! out=$(g compute instances start "$VM" --zone="$ZONE" --quiet 2>&1); then
    if grep -qiE 'STOCKOUT|RESOURCE_POOL_EXHAUSTED' <<< "$out"; then
      echo "No L4 capacity in $ZONE right now (stockout). Nothing is running or billed; try again later." >&2
      exit 2
    fi
    echo "$out" >&2; die "could not start $VM"
  fi
fi
say "Waiting for SSH"
for _ in $(seq 20); do vm_ssh --command=true >/dev/null 2>&1 && break; sleep 10; done
vm_ssh --command=true >/dev/null 2>&1 || die "no SSH to $VM after 200 s; it is running and billed: stop it by hand"

# ---------------------------------------------------------------- deploy and launch
say "Syncing code to $REPO_DIR"
git -C "$repo_root" archive "$rev" | vm_ssh --command="sudo tar -x -C $REPO_DIR && echo $rev | sudo tee $REPO_DIR/REVISION >/dev/null"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
runner=$(mktemp)
{
  echo "#!/usr/bin/env bash"
  echo "# Written by scripts/cloud_run.sh at $stamp; runs inside the airflow-scheduler container."
  for c in "${confs[@]}"; do
    printf "echo '=== run %s'; airflow dags test clinverify_pipeline -c '%s'; echo \"EXIT=\$?\"\n" "$c" "$c"
  done
  echo "echo ALL_DONE"
} > "$runner"
remote_dir=$REPO_DIR/results/cloud_run
g compute scp "$runner" "$VM:/tmp/cloud_run_$stamp.sh" --zone="$ZONE" --tunnel-through-iap --quiet >/dev/null
rm -f "$runner"

vm_ssh --command="set -e
sudo shutdown -h +$((MAX_HOURS * 60)) 'clinverify cloud_run safety stop' 2>/dev/null || true
if ! nvidia-smi >/dev/null 2>&1 || ! systemctl show ollama -p Environment | grep -q OLLAMA_MAX_LOADED_MODELS=1 \
   || ! ollama list | grep -q nomic-embed-text; then
  echo '==> GPU driver, Ollama setting or a model is missing; rerunning setup_gpu_vm.sh host'
  sudo bash $REPO_DIR/scripts/setup_gpu_vm.sh host
fi
nvidia-smi >/dev/null 2>&1 || { echo 'ERROR: GPU driver not working after setup (a reboot may be needed); stopping the VM' >&2; sudo shutdown -h now; exit 1; }
sudo install -d -o 50000 -g 0 $remote_dir
sudo install -o 50000 -g 0 -m 755 /tmp/cloud_run_$stamp.sh $remote_dir/run_$stamp.sh
cd $REPO_DIR && sudo docker compose up -d >/dev/null
for _ in \$(seq 30); do sudo docker compose exec -T airflow-scheduler airflow dags list >/dev/null 2>&1 && break; sleep 10; done
sudo docker compose exec -T airflow-scheduler airflow dags list 2>/dev/null | grep -q clinverify_pipeline
sudo docker compose exec -d -T airflow-scheduler bash -c 'bash $remote_dir/run_$stamp.sh > $remote_dir/run_$stamp.log 2>&1'
echo started"

cat <<EOF

Started ${#confs[@]} run(s) on $VM. The last one stops the VM when it finishes (safety stop after $MAX_HOURS h).
Follow progress:
  gcloud compute ssh $VM --project=$PROJECT --zone=$ZONE --tunnel-through-iap \\
    --command='grep -E "^===|EXIT=|ALL_DONE|Marking task as" $remote_dir/run_$stamp.log | tail'
Results: $REPO_DIR/results/model_runs/airflow_runs/<day>/rag-<on|off>_model-<base|ft>/
Check the VM is stopped afterwards: gcloud compute instances describe $VM --project=$PROJECT --zone=$ZONE --format='value(status)'
EOF
