#!/usr/bin/env bash
# GPU (1x NVIDIA L4) + Ollama on the shared Airflow VM, for the model steps of the cloud DAG (T6-206).
#
#   From your laptop (gcloud, Compute Instance Admin):
#     bash scripts/setup_gpu_vm.sh preflight   # read-only: quota, VM state, disk, firewall
#     bash scripts/setup_gpu_vm.sh to-gpu      # stopped VM -> g2-standard-4 (1x L4), boot disk >= 100 GB
#     bash scripts/setup_gpu_vm.sh to-cpu      # stopped VM -> back to e2-medium (disk stays at its new size)
#   On the VM (needs sudo, i.e. roles/compute.osAdminLogin):
#     sudo bash /opt/clinverify/scripts/setup_gpu_vm.sh host    # NVIDIA driver, Ollama for Docker, models
#     bash /opt/clinverify/scripts/setup_gpu_vm.sh check        # GPU, Ollama, models, reachable from a container
#
# DRY_RUN=1 prints the commands that would change something instead of running them.
# Every step checks the one before it and stops with a reason; nothing here sends MIMIC data anywhere.
set -euo pipefail

PROJECT=${PROJECT:-clinverify-298a}
ZONE=${ZONE:-us-west1-a}
VM=${VM:-clinverify-airflow}
GPU_MACHINE=${GPU_MACHINE:-g2-standard-4}
CPU_MACHINE=${CPU_MACHINE:-e2-medium}
DISK_GB=${DISK_GB:-100}
MODELS=${MODELS:-"qwen2.5:14b llama3.1:8b"}
OLLAMA_PORT=11434

die() { echo "ERROR: $*" >&2; exit 1; }
say() { echo "==> $*"; }
run() { if [ "${DRY_RUN:-0}" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }
g() { gcloud --project="$PROJECT" "$@"; }

vm_status() { g compute instances describe "$VM" --zone="$ZONE" --format='value(status)'; }
require_stopped() {
  local s; s=$(vm_status)
  [ "$s" = TERMINATED ] || die "$VM is $s. Stop it first: docker compose down on the VM, then
  gcloud compute instances stop $VM --project=$PROJECT --zone=$ZONE"
}

gpu_quota() {
  g compute project-info describe --format=json | python3 -c '
import json, sys
q = [x["limit"] for x in json.load(sys.stdin)["quotas"] if x["metric"] == "GPUS_ALL_REGIONS"]
print(int(q[0]) if q else 0)'
}

preflight() {
  local quota machine disk dtype size open
  quota=$(gpu_quota)
  machine=$(g compute instances describe "$VM" --zone="$ZONE" --format='value(machineType.basename())')
  disk=$(g compute instances describe "$VM" --zone="$ZONE" --format='value(disks[0].source.basename())')
  read -r dtype size < <(g compute disks describe "$disk" --zone="$ZONE" --format='value(type.basename(),sizeGb)')
  echo "VM            $VM ($machine, $(vm_status)) in $ZONE"
  echo "Boot disk     $disk: $dtype, ${size} GB"
  echo "GPU quota     GPUS_ALL_REGIONS = $quota"
  g compute accelerator-types list --filter="name=nvidia-l4 AND zone:$ZONE" --format='value(zone)' 2>/dev/null \
    | grep -q . && echo "L4 in zone    yes" || echo "L4 in zone    NO"
  # Any ingress rule open to the internet that would reach Ollama's port.
  open=$(g compute firewall-rules list --format=json | python3 -c '
import json, sys
port = '"$OLLAMA_PORT"'
def hits(a):
    if a.get("IPProtocol") in ("all",): return True
    if a.get("IPProtocol") != "tcp": return False
    for p in a.get("ports", ["0-65535"]):
        lo, _, hi = p.partition("-")
        if int(lo) <= port <= int(hi or lo): return True
    return False
for r in json.load(sys.stdin):
    if r.get("direction") == "INGRESS" and not r.get("disabled") and "0.0.0.0/0" in r.get("sourceRanges", []) \
       and any(hits(a) for a in r.get("allowed", [])):
        print(r["name"])')
  if [ -n "$open" ]; then echo "Ollama port   EXPOSED by: $open  (remove before installing Ollama)"; else echo "Ollama port   not reachable from the internet"; fi
  [ "$quota" -ge 1 ] || echo "BLOCKER       GPU quota is 0: the project owner must request GPUs (all regions) = 1"
  [ "$dtype" != pd-standard ] || echo "BLOCKER       pd-standard boot disks are not supported on G2 machines"
}

# Machine type and maintenance policy must change together: E2 refuses TERMINATE and G2 (built-in GPU) refuses
# MIGRATE, so neither single-field command works. Export the instance, edit both fields, apply in one update.
switch_machine() {
  local type=$1 policy=$2 tmp; tmp=$(mktemp)
  g compute instances export "$VM" --zone="$ZONE" --destination="$tmp" >/dev/null 2>&1
  sed -i.bak -e "s|/machineTypes/[a-z0-9-]*|/machineTypes/$type|" -e "s|onHostMaintenance: [A-Z]*|onHostMaintenance: $policy|" "$tmp"
  if [ "$policy" = MIGRATE ]; then
    # A G2 export lists its built-in L4 under guestAccelerators; a CPU machine type refuses it, so drop the block.
    # G2 also attaches the boot disk over NVMe, which E2 does not support.
    awk '/^guestAccelerators:/{skip=1; next} skip && /^[- ] /{next} {skip=0; print}' "$tmp" \
      | sed -e 's|interface: NVME|interface: SCSI|' > "$tmp.cpu" && mv "$tmp.cpu" "$tmp"
    ! grep -q "^guestAccelerators:" "$tmp" || die "could not remove the GPU from the exported instance"
  fi
  grep -q "machineTypes/$type" "$tmp" && grep -q "onHostMaintenance: $policy" "$tmp" || die "could not edit the exported instance"
  run g compute instances update-from-file "$VM" --zone="$ZONE" --source="$tmp" --most-disruptive-allowed-action=RESTART
  rm -f "$tmp" "$tmp.bak"
}

to_gpu() {
  local quota disk dtype size
  quota=$(gpu_quota)
  [ "$quota" -ge 1 ] || die "GPUS_ALL_REGIONS quota is $quota; the project owner must raise it to 1 first"
  require_stopped
  disk=$(g compute instances describe "$VM" --zone="$ZONE" --format='value(disks[0].source.basename())')
  read -r dtype size < <(g compute disks describe "$disk" --zone="$ZONE" --format='value(type.basename(),sizeGb)')
  [ "$dtype" != pd-standard ] || die "boot disk $disk is pd-standard, which G2 machines do not support"
  if [ "$size" -lt "$DISK_GB" ]; then
    say "Resizing boot disk $disk from ${size} GB to ${DISK_GB} GB (cannot be shrunk later)"
    run g compute disks resize "$disk" --zone="$ZONE" --size="${DISK_GB}GB" --quiet --format=none
  fi
  say "Changing $VM to $GPU_MACHINE (1x NVIDIA L4, about \$0.70/hour while running), maintenance policy TERMINATE"
  switch_machine "$GPU_MACHINE" TERMINATE
  cat <<EOF

Done. Next:
  gcloud compute instances start $VM --project=$PROJECT --zone=$ZONE
  gcloud compute ssh $VM --project=$PROJECT --zone=$ZONE
  sudo bash /opt/clinverify/scripts/setup_gpu_vm.sh host
Stop the VM after every session.
EOF
}

to_cpu() {
  require_stopped
  say "Changing $VM back to $CPU_MACHINE"
  switch_machine "$CPU_MACHINE" MIGRATE
}

host() {
  [ "$(id -u)" -eq 0 ] || die "run with sudo on the VM"
  if ! nvidia-smi >/dev/null 2>&1; then
    say "Installing the NVIDIA driver (Google's installer; the VM may reboot: if so, SSH back in and rerun this step)"
    run curl -fsSL -o /tmp/install_gpu_driver.py \
      https://raw.githubusercontent.com/GoogleCloudPlatform/compute-gpu-installation/main/linux/install_gpu_driver.py
    run python3 /tmp/install_gpu_driver.py
  fi
  [ "${DRY_RUN:-0}" = 1 ] || nvidia-smi --query-gpu=name,memory.total --format=csv,noheader \
    || die "driver not working yet; reboot (sudo reboot), SSH back in and rerun"

  if ! command -v ollama >/dev/null 2>&1; then
    say "Installing Ollama"
    run sh -c 'curl -fsSL https://ollama.com/install.sh | sh'
  fi
  # Listen on all interfaces so Airflow containers reach it via host.docker.internal.
  # The GCP firewall has no rule for this port (checked by preflight), so it stays private to the VM.
  say "Configuring Ollama to accept connections from Docker containers"
  run mkdir -p /etc/systemd/system/ollama.service.d
  if [ "${DRY_RUN:-0}" = 1 ]; then
    echo "[dry-run] write /etc/systemd/system/ollama.service.d/override.conf (OLLAMA_HOST=0.0.0.0:$OLLAMA_PORT, OLLAMA_MAX_LOADED_MODELS=1)"
  else
    # One model in memory at a time: on 2026-11-15 qwen2.5:14b (kept alive after generate_plans) and the llama3.1:8b
    # G-Eval judge were both resident, the 16 GB host ran out of RAM and the OOM killer stopped Ollama mid-run.
    printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0:%s"\nEnvironment="OLLAMA_MAX_LOADED_MODELS=1"\n' "$OLLAMA_PORT" \
      > /etc/systemd/system/ollama.service.d/override.conf
  fi
  run systemctl daemon-reload
  run systemctl enable --now ollama
  run systemctl restart ollama
  if [ "${DRY_RUN:-0}" != 1 ]; then
    for _ in $(seq 30); do curl -fsS "http://127.0.0.1:$OLLAMA_PORT/api/version" >/dev/null 2>&1 && break; sleep 1; done
    curl -fsS "http://127.0.0.1:$OLLAMA_PORT/api/version" >/dev/null || die "Ollama did not start (journalctl -u ollama)"
  fi
  for m in $MODELS; do say "Pulling $m"; run ollama pull "$m"; done
  say "Host ready. Now run (without sudo): bash $0 check"
}

check() {
  local ok=1
  nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader || { echo "FAIL  no GPU driver"; ok=0; }
  curl -fsS "http://127.0.0.1:$OLLAMA_PORT/api/version" >/dev/null && echo "OK    Ollama answers on 127.0.0.1" \
    || { echo "FAIL  Ollama not answering"; ok=0; }
  for m in $MODELS; do
    ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$m" && echo "OK    model $m" || { echo "FAIL  model $m missing"; ok=0; }
  done
  set -- $MODELS
  if ollama run "$1" "Reply with the single word OK." >/dev/null 2>&1; then
    ollama ps | grep -q "GPU" && echo "OK    $1 runs on the GPU ($(ollama ps | grep -o '[0-9]*% GPU' | head -1))" \
      || { echo "FAIL  $1 is not on the GPU (ollama ps)"; ok=0; }
  else echo "FAIL  $1 did not answer"; ok=0; fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm --add-host=host.docker.internal:host-gateway curlimages/curl:8.11.1 -fsS \
      "http://host.docker.internal:$OLLAMA_PORT/api/version" >/dev/null 2>&1 \
      && echo "OK    reachable from a container via host.docker.internal" \
      || { echo "FAIL  containers cannot reach Ollama (Airflow tasks will fail)"; ok=0; }
  fi
  [ "$ok" = 1 ] && echo "All checks passed." || die "some checks failed"
}

case "${1:-}" in
  preflight) preflight ;;
  to-gpu) to_gpu ;;
  to-cpu) to_cpu ;;
  host) host ;;
  check) check ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
