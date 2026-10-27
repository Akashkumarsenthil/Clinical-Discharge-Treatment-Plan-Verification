"""Independent human plan-label schema and scorer (research goal / escape rates).

Does not invent clinical labels. Without a complete eligibility manifest and
complete labels for every eligible case, adjudicated rates stay null.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ELIGIBILITY_SCHEMA_VERSION = 1
LABEL_SCHEMA_VERSION = 1


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_sha256(manifest: dict) -> str:
    """Stable hash of a loaded eligibility manifest (canonical JSON)."""
    return _sha256_bytes(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_eligibility_manifest(
    manifest: dict,
    *,
    covered_case_ids: set[int],
    catalog_version: str | None = None,
) -> dict:
    """Validate a pre-generation eligibility review over all covered cases.

    Every covered case_id must appear exactly once with eligible true/false and a reason when ineligible.
    """
    if manifest.get("schema_version") != ELIGIBILITY_SCHEMA_VERSION:
        raise ValueError(f"eligibility schema_version must be {ELIGIBILITY_SCHEMA_VERSION}")
    if catalog_version is not None and manifest.get("catalog_version") not in (None, catalog_version):
        raise ValueError("eligibility catalog_version differs from the evaluation protocol")
    if not isinstance(manifest.get("reviewer"), str) or not manifest["reviewer"].strip():
        raise ValueError("eligibility manifest requires reviewer")
    if not isinstance(manifest.get("review_date"), str) or not manifest["review_date"].strip():
        raise ValueError("eligibility manifest requires review_date")
    if manifest.get("blind_to_plans") is not True:
        raise ValueError("eligibility must declare blind_to_plans: true")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("eligibility manifest requires a non-empty cases list")
    seen: set[int] = set()
    eligible_ids: list[int] = []
    reasons: Counter = Counter()
    for row in cases:
        if not isinstance(row, dict):
            raise ValueError("each eligibility row must be an object")
        cid = row.get("case_id")
        if type(cid) is not int:
            raise ValueError("eligibility case_id must be an int")
        if cid in seen:
            raise ValueError(f"duplicate eligibility case_id {cid}")
        seen.add(cid)
        eligible = row.get("eligible")
        if eligible is not True and eligible is not False:
            raise ValueError(f"eligibility for {cid} must be boolean")
        reason = row.get("reason", "")
        if not isinstance(reason, str):
            raise ValueError(f"eligibility reason for {cid} must be a string")
        if eligible is False and not reason.strip():
            raise ValueError(f"ineligible case {cid} needs a reason")
        if eligible is True and reason.strip():
            # allowed but counted for reporting
            pass
        if eligible:
            eligible_ids.append(cid)
        else:
            reasons[reason.strip() or "unspecified"] += 1
    if seen != set(covered_case_ids):
        missing = sorted(set(covered_case_ids) - seen)
        extra = sorted(seen - set(covered_case_ids))
        raise ValueError(
            "eligibility must cover exactly the covered cohort cases"
            + (f"; missing={missing[:5]}" if missing else "")
            + (f"; extra={extra[:5]}" if extra else "")
        )
    return {
        "n_covered": len(covered_case_ids),
        "n_eligible": len(eligible_ids),
        "n_ineligible": len(covered_case_ids) - len(eligible_ids),
        "eligible_case_ids": sorted(eligible_ids),
        "ineligibility_reasons": dict(reasons),
        "manifest_sha256": manifest_sha256(manifest),
        "reviewer": manifest["reviewer"].strip(),
        "review_date": manifest["review_date"].strip(),
    }


def validate_plan_labels(
    labels_doc: dict,
    *,
    eligible_case_ids: set[int],
    expected_manifest_sha256: str | None = None,
) -> dict:
    """Validate independent plan labels for the eligible set.

    Every eligible case must have exactly one label. Unresolved
    clinically_adequate_and_valid (null) is allowed in the file but blocks a final rate.
    """
    if labels_doc.get("schema_version") != LABEL_SCHEMA_VERSION:
        raise ValueError(f"plan label schema_version must be {LABEL_SCHEMA_VERSION}")
    if not isinstance(labels_doc.get("reviewer"), str) or not labels_doc["reviewer"].strip():
        raise ValueError("plan labels require reviewer")
    if not isinstance(labels_doc.get("review_date"), str) or not labels_doc["review_date"].strip():
        raise ValueError("plan labels require review_date")
    pinned = labels_doc.get("eligibility_manifest_sha256")
    if expected_manifest_sha256 is not None:
        if not isinstance(pinned, str) or pinned != expected_manifest_sha256:
            raise ValueError("plan labels eligibility_manifest_sha256 does not match the loaded manifest")
    rows = labels_doc.get("labels")
    if not isinstance(rows, list) or not rows:
        raise ValueError("plan labels require a non-empty labels list")
    by_id: dict[int, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each plan label must be an object")
        cid = row.get("case_id")
        if type(cid) is not int:
            raise ValueError("plan label case_id must be an int")
        if cid in by_id:
            raise ValueError(f"duplicate plan label for case_id {cid}")
        adeq = row.get("clinically_adequate_and_valid")
        if adeq is not True and adeq is not False and adeq is not None:
            raise ValueError(f"clinically_adequate_and_valid for {cid} must be true, false, or null")
        diag = row.get("diagnosis_correct")
        if diag is not True and diag is not False and diag is not None:
            raise ValueError(f"diagnosis_correct for {cid} must be true, false, or null")
        blocking_invalid = row.get("blocking_invalid")
        if blocking_invalid is not True and blocking_invalid is not False and blocking_invalid is not None:
            raise ValueError(f"blocking_invalid for {cid} must be true, false, or null")
        rule_ids = row.get("blocking_rule_ids", [])
        if rule_ids is None:
            rule_ids = []
        if not isinstance(rule_ids, list) or any(not isinstance(x, str) for x in rule_ids):
            raise ValueError(f"blocking_rule_ids for {cid} must be a list of strings")
        notes = row.get("notes", "")
        if not isinstance(notes, str):
            raise ValueError(f"notes for {cid} must be a string")
        by_id[cid] = {
            "case_id": cid,
            "diagnosis_correct": diag,
            "clinically_adequate_and_valid": adeq,
            "blocking_invalid": blocking_invalid,
            "blocking_rule_ids": list(rule_ids),
            "notes": notes,
        }
    if set(by_id) != set(eligible_case_ids):
        missing = sorted(set(eligible_case_ids) - set(by_id))
        extra = sorted(set(by_id) - set(eligible_case_ids))
        raise ValueError(
            "plan labels must cover exactly the eligible cases"
            + (f"; missing={missing[:5]}" if missing else "")
            + (f"; extra={extra[:5]}" if extra else "")
        )
    unresolved = sorted(
        cid for cid, row in by_id.items()
        if row["clinically_adequate_and_valid"] is None or row["diagnosis_correct"] is None
    )
    return {
        "by_id": by_id,
        "n_labels": len(by_id),
        "n_unresolved": len(unresolved),
        "unresolved_case_ids": unresolved,
        "reviewer": labels_doc["reviewer"].strip(),
        "review_date": labels_doc["review_date"].strip(),
        "eligibility_manifest_sha256": pinned,
    }


def score_adjudicated_validity(eligible_case_ids: list[int], label_rows: dict[int, dict]) -> dict:
    """Rate = adequate+valid AND diagnosis_correct / E. Unresolved → null rate."""
    e = len(eligible_case_ids)
    if e == 0:
        return {
            "adjudicated_treatment_validity_rate": None,
            "adjudication_status": "unavailable_zero_eligible",
            "n_eligible": 0,
            "n_adjudicated_success": 0,
            "n_unresolved_labels": 0,
        }
    unresolved = [
        cid for cid in eligible_case_ids
        if label_rows[cid]["clinically_adequate_and_valid"] is None
        or label_rows[cid]["diagnosis_correct"] is None
    ]
    if unresolved:
        return {
            "adjudicated_treatment_validity_rate": None,
            "adjudication_status": "unavailable_unresolved_labels",
            "n_eligible": e,
            "n_adjudicated_success": 0,
            "n_unresolved_labels": len(unresolved),
            "unresolved_case_ids": unresolved,
        }
    successes = [
        cid for cid in eligible_case_ids
        if label_rows[cid]["diagnosis_correct"] is True
        and label_rows[cid]["clinically_adequate_and_valid"] is True
    ]
    return {
        "adjudicated_treatment_validity_rate": len(successes) / e,
        "adjudication_status": "scored_from_independent_labels",
        "n_eligible": e,
        "n_adjudicated_success": len(successes),
        "n_unresolved_labels": 0,
    }


def score_labelled_verifier_agreement(
    label_rows: dict[int, dict],
    per_case: list[dict],
) -> dict:
    """Escape / false-reject from independent blocking labels vs verifier outcomes.

    Cases without a boolean blocking_invalid label are skipped (not fabricated).
    """
    by_verifier = {row["case_id"]: row for row in per_case if type(row.get("case_id")) is int}
    escape_flags: list[bool] = []
    false_reject_flags: list[bool] = []
    for cid, lab in label_rows.items():
        bi = lab.get("blocking_invalid")
        if bi is not True and bi is not False:
            continue
        vrow = by_verifier.get(cid)
        accepted = bool(vrow and vrow.get("status") == "valid")
        if bi is True:
            escape_flags.append(accepted)
        else:
            false_reject_flags.append(not accepted)

    def _rate(flags: list[bool]) -> dict:
        if not flags:
            return {"rate": None, "n": 0}
        return {"rate": sum(flags) / len(flags), "n": len(flags)}

    return {
        "labelled_escape_rate": _rate(escape_flags),
        "labelled_false_reject_rate": _rate(false_reject_flags),
    }


def apply_adjudication(
    summary: dict,
    *,
    eligibility_manifest: dict | None,
    plan_labels: dict | None,
    covered_case_ids: set[int],
    catalog_version: str | None = None,
) -> dict:
    """Attach adjudicated metrics to a verify_model_plans summary. Mutates and returns summary."""
    if eligibility_manifest is None and plan_labels is None:
        summary.setdefault("adjudicated_treatment_validity_rate", None)
        summary.setdefault("adjudication_status", "unavailable_no_independent_plan_labels_loaded")
        return summary
    if eligibility_manifest is None or plan_labels is None:
        summary["adjudicated_treatment_validity_rate"] = None
        summary["adjudication_status"] = "unavailable_incomplete_adjudication_inputs"
        return summary

    elig = validate_eligibility_manifest(
        eligibility_manifest, covered_case_ids=covered_case_ids, catalog_version=catalog_version
    )
    labs = validate_plan_labels(
        plan_labels,
        eligible_case_ids=set(elig["eligible_case_ids"]),
        expected_manifest_sha256=elig["manifest_sha256"],
    )
    scored = score_adjudicated_validity(elig["eligible_case_ids"], labs["by_id"])
    agreement = score_labelled_verifier_agreement(labs["by_id"], summary.get("per_case") or [])
    summary.update(scored)
    summary["adjudication"] = {
        "eligibility": {k: v for k, v in elig.items() if k != "eligible_case_ids"},
        "eligible_case_ids": elig["eligible_case_ids"],
        "labels": {
            "reviewer": labs["reviewer"],
            "review_date": labs["review_date"],
            "n_labels": labs["n_labels"],
            "n_unresolved": labs["n_unresolved"],
            "eligibility_manifest_sha256": labs["eligibility_manifest_sha256"],
        },
        **agreement,
    }
    return summary


def example_eligibility_template(covered_case_ids: list[int], *, catalog_version: str = "2.1") -> dict[str, Any]:
    """Empty template for humans; eligible left null so it cannot be scored by accident."""
    return {
        "schema_version": ELIGIBILITY_SCHEMA_VERSION,
        "catalog_version": catalog_version,
        "reviewer": "",
        "review_date": "",
        "blind_to_plans": True,
        "cases": [{"case_id": cid, "eligible": None, "reason": ""} for cid in sorted(covered_case_ids)],
        "_instructions": "Set eligible true/false for every covered case before Model A generation. Fill reviewer/date. Do not view plans.",
    }


def example_labels_template(eligible_case_ids: list[int], manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": LABEL_SCHEMA_VERSION,
        "eligibility_manifest_sha256": manifest_hash,
        "reviewer": "",
        "review_date": "",
        "labels": [
            {
                "case_id": cid,
                "diagnosis_correct": None,
                "clinically_adequate_and_valid": None,
                "blocking_invalid": None,
                "blocking_rule_ids": [],
                "notes": "",
            }
            for cid in sorted(eligible_case_ids)
        ],
        "_instructions": "Fill after generation. Do not copy verifier verdicts. Unresolved nulls block the 0.85 research rate.",
    }
