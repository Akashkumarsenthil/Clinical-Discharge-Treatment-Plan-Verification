"""stop_this_vm.py with a fake metadata server and Compute API; no network."""
import importlib.util
import io
import json
from pathlib import Path
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stop_this_vm", ROOT / "scripts/stop_this_vm.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

META = {"project/project-id": "clinverify-298a", "instance/zone": "projects/105/zones/us-west1-a",
        "instance/name": "clinverify-airflow",
        "instance/service-accounts/default/token": json.dumps({"access_token": "TOKEN", "expires_in": 3599})}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_gce(meta=META, stop_status=200):
    calls = []

    def opener(req, timeout):
        url = req.full_url
        calls.append((req.get_method(), url, dict(req.header_items())))
        if url.startswith(S.METADATA):
            assert req.get_header("Metadata-flavor") == "Google"
            return _Resp(meta[url[len(S.METADATA):]].encode())
        if stop_status != 200:
            raise urllib.error.HTTPError(url, stop_status, "denied", {}, None)
        return _Resp(json.dumps({"name": "operation-123"}).encode())
    return opener, calls


def no_metadata(req, timeout):
    raise urllib.error.URLError(OSError("no route to host"))


def test_stops_the_expected_vm_with_its_own_token(capsys):
    opener, calls = fake_gce()
    assert S.main([], opener) == 0
    method, url, headers = calls[-1]
    assert method == "POST"
    assert url == ("https://compute.googleapis.com/compute/v1/projects/clinverify-298a/zones/us-west1-a/"
                   "instances/clinverify-airflow/stop")
    assert headers["Authorization"] == "Bearer TOKEN"
    out = capsys.readouterr().out
    assert "operation-123" in out and "TOKEN" not in out


def test_off_gce_does_nothing(capsys):
    assert S.main([], no_metadata) == 0
    assert "nothing to stop" in capsys.readouterr().out


def test_another_vm_is_not_stopped(capsys):
    opener, calls = fake_gce({**META, "instance/name": "someone-elses-vm"})
    assert S.main([], opener) == 0
    assert not any(m == "POST" for m, _, _ in calls)
    assert "not stopping" in capsys.readouterr().out


def test_dry_run_does_not_call_the_api(capsys):
    opener, calls = fake_gce()
    assert S.main(["--dry-run"], opener) == 0
    assert not any(m == "POST" for m, _, _ in calls)


def test_permission_denied_fails_with_a_hint(capsys):
    opener, _ = fake_gce(stop_status=403)
    assert S.main([], opener) == 1
    err = capsys.readouterr().err
    assert "compute.instances.stop" in err and "gcloud compute instances stop clinverify-airflow" in err
