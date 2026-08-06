"""Deterministic benchmark baseline identity and atomic persistence."""

import hashlib
import json
from pathlib import Path


def case_set_fingerprint(names):
    payload = json.dumps(
        sorted(names),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _metrics(data):
    if not isinstance(data, dict):
        raise ValueError("baseline must be a JSON object")
    fingerprint = data.get("case_set_fingerprint")
    swcr_value = data.get("swcr")
    controls = data.get("fpr0")
    rate = controls.get("rate") if isinstance(controls, dict) else None
    if (
        not isinstance(fingerprint, str)
        or not fingerprint
        or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in (swcr_value, rate)
        )
    ):
        raise ValueError("baseline metrics have invalid types")
    return fingerprint, float(swcr_value), float(rate)


def is_regression(report, baseline):
    fingerprint, baseline_swcr, baseline_fpr0 = _metrics(baseline)
    if fingerprint != report["case_set_fingerprint"]:
        raise ValueError("baseline case-set fingerprint mismatch")
    return (
        report["swcr"] < baseline_swcr - 0.005
        or report["fpr0"]["rate"] > baseline_fpr0 + 0.01
    )


def write_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"refusing to overwrite symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        if temporary.is_symlink():
            raise ValueError(f"refusing to write through temporary symlink: {temporary}")
        temporary.write_text(
            json.dumps(value, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
