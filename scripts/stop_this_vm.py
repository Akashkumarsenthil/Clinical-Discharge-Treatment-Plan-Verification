"""Stop the GCP VM this process runs on (the DAG's stop_vm teardown task).

Uses the VM's own service account through the metadata server: no keys, no gcloud. Does nothing, and exits 0, when
not on a GCE VM (local Airflow) or when the VM is not the expected one, so the DAG is safe to run anywhere.

    python scripts/stop_this_vm.py              # stop clinverify-airflow if this is it
    python scripts/stop_this_vm.py --dry-run    # print what it would do

The service account needs compute.instances.stop on the VM (for example roles/compute.instanceAdmin.v1).
GCE then shuts the VM down gracefully, so a task that has just finished still has its state recorded.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

METADATA = "http://169.254.169.254/computeMetadata/v1/"
COMPUTE = "https://compute.googleapis.com/compute/v1/"
DEFAULT_VM = "clinverify-airflow"


def metadata(path: str, opener=urllib.request.urlopen) -> str:
    req = urllib.request.Request(METADATA + path, headers={"Metadata-Flavor": "Google"})
    with opener(req, timeout=3) as resp:
        return resp.read().decode()


def this_vm(opener=urllib.request.urlopen) -> dict | None:
    """{project, zone, name} of this VM, or None when there is no GCE metadata server."""
    try:
        return {"project": metadata("project/project-id", opener),
                "zone": metadata("instance/zone", opener).rsplit("/", 1)[-1],
                "name": metadata("instance/name", opener)}
    except (urllib.error.URLError, OSError):
        return None


def stop(vm: dict, opener=urllib.request.urlopen) -> str:
    token = json.loads(metadata("instance/service-accounts/default/token", opener))["access_token"]
    url = f"{COMPUTE}projects/{vm['project']}/zones/{vm['zone']}/instances/{vm['name']}/stop"
    req = urllib.request.Request(url, data=b"", method="POST", headers={"Authorization": f"Bearer {token}"})
    with opener(req, timeout=30) as resp:
        return json.loads(resp.read()).get("name", "?")


def main(argv=None, opener=urllib.request.urlopen) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--expected-name", default=DEFAULT_VM, help=f"only stop a VM with this name (default {DEFAULT_VM})")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    vm = this_vm(opener)
    if vm is None:
        print("Not on a GCE VM (no metadata server); nothing to stop.")
        return 0
    if vm["name"] != args.expected_name:
        print(f"This VM is {vm['name']!r}, not {args.expected_name!r}; not stopping it.")
        return 0
    where = f"{vm['name']} ({vm['project']}, {vm['zone']})"
    if args.dry_run:
        print(f"[dry-run] would stop {where}")
        return 0
    try:
        op = stop(vm, opener)
    except urllib.error.HTTPError as err:
        hint = " The VM's service account needs compute.instances.stop." if err.code == 403 else ""
        print(f"ERROR: stopping {where} failed with HTTP {err.code}.{hint} Stop it by hand:\n"
              f"  gcloud compute instances stop {vm['name']} --project={vm['project']} --zone={vm['zone']}",
              file=sys.stderr)
        return 1
    print(f"Stop requested for {where} (operation {op}). The VM shuts down in about a minute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
