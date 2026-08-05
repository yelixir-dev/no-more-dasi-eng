#!/usr/bin/env python3
"""Run the deterministic benchmark over contract-v2 case directories."""

import argparse
import json
import sys
from pathlib import Path

try:
    from .benchmark_metrics import eap, fpr0, mp, swcr
except ImportError:
    from benchmark_metrics import eap, fpr0, mp, swcr

EXCLUDED = {"regressions", "candidates"}
REQUIRED_META = {"field", "error_class", "severity", "origin", "no_edit", "source_doc_id", "protected_names", "review"}
CLASSES = {"articles", "agreement/countability", "section-tense", "korean-translationese", "field-terminology", "claim-calibration", "none"}
SEVERITIES = {"minor", "major", "critical", "na"}
ORIGINS = {"natural", "synthetic"}
REVIEWS = {"pending", "approved"}


def enumerate_cases(dataset):
    dataset = Path(dataset)
    return sorted(
        p for p in dataset.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in EXCLUDED
    )


def _read_json(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def validate_case(case, taxonomy_ids):
    case = Path(case)
    required = [case / name for name in ("input.txt", "gold.txt", "edits.json", "meta.json")]
    missing = [p.name for p in required if not p.is_file()]
    if missing:
        raise ValueError(f"{case.name}: missing {', '.join(missing)}")
    edits = _read_json(case / "edits.json")
    meta = _read_json(case / "meta.json")
    if not isinstance(edits, list) or not isinstance(meta, dict):
        raise ValueError(f"{case.name}: edits.json must be a list and meta.json an object")
    missing_meta = REQUIRED_META - set(meta)
    if missing_meta:
        raise ValueError(f"{case.name}: meta missing {sorted(missing_meta)}")
    if meta["origin"] not in ORIGINS or meta["review"] not in REVIEWS:
        raise ValueError(f"{case.name}: invalid origin or review")
    if not isinstance(meta["no_edit"], bool) or not isinstance(meta["protected_names"], list):
        raise ValueError(f"{case.name}: no_edit/protected_names have invalid type")
    approved = meta["review"] == "approved"
    if approved and not meta["no_edit"] and (meta["error_class"] not in CLASSES - {"none"} or meta["severity"] not in SEVERITIES - {"na"}):
        raise ValueError(f"{case.name}: approved cases require error_class and severity")
    if not approved and (meta["error_class"] is not None or meta["severity"] is not None):
        raise ValueError(f"{case.name}: pending error_class and severity must be null")
    if meta["no_edit"]:
        if edits or meta["error_class"] != "none" or meta["severity"] != "na":
            raise ValueError(f"{case.name}: no-edit controls require empty edits, none, and na")
    elif not edits:
        raise ValueError(f"{case.name}: edited case requires edits")
    if approved and meta.get("approved_by") not in {"machine:synthetic", "machine:control"} and not str(meta.get("approved_by", "")).startswith("human:"):
        raise ValueError(f"{case.name}: invalid approved_by")
    if approved and "approved_by" not in meta:
        raise ValueError(f"{case.name}: approved cases require approved_by")
    source_len = len(_tokens(case / "input.txt"))
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict) or not {"span", "class", "severity", "accept"} <= set(edit):
            raise ValueError(f"{case.name}: edit {index} has invalid shape")
        span = edit["span"]
        if not isinstance(span, list) or len(span) != 2 or not all(isinstance(x, int) for x in span) or not 0 <= span[0] <= span[1] <= source_len:
            raise ValueError(f"{case.name}: edit {index} has invalid token span")
        if edit["severity"] not in SEVERITIES - {"na"} or not isinstance(edit["accept"], list) or not all(isinstance(x, list) for x in edit["accept"]):
            raise ValueError(f"{case.name}: edit {index} has invalid severity or accept")
        if approved and (edit["class"] is None or (taxonomy_ids and edit["class"] not in taxonomy_ids)):
            raise ValueError(f"{case.name}: edit {index} class is not a taxonomy id")
        if not approved and edit["class"] is not None and taxonomy_ids and edit["class"] not in taxonomy_ids:
            raise ValueError(f"{case.name}: pending edit {index} class is not a taxonomy id")
    return {"input": (case / "input.txt").read_text(encoding="utf-8"), "gold": (case / "gold.txt").read_text(encoding="utf-8"), "edits": edits, "meta": meta}


def _tokens(path):
    try:
        from .benchmark_metrics import tokenize
    except ImportError:
        from benchmark_metrics import tokenize
    return tokenize(Path(path).read_text(encoding="utf-8"))


def _taxonomy_ids(dataset):
    path = Path(dataset) / "taxonomy.json"
    if not path.exists():
        return set()
    data = _read_json(path)
    return {item["id"] for item in data if isinstance(item, dict) and "id" in item}


def _candidate_map(dataset, candidate_dir):
    if candidate_dir is None:
        return {case.name: case.joinpath("gold.txt").read_text(encoding="utf-8") for case in enumerate_cases(dataset)}, "gold-selfcheck", 0
    directory = Path(candidate_dir)
    if not directory.is_dir():
        raise ValueError(f"candidate directory does not exist: {directory}")
    known = {case.name for case in enumerate_cases(dataset)}
    files = {p.stem: p for p in directory.iterdir() if p.is_file() and p.suffix == ".txt"}
    unknown = sorted(set(files) - known)
    if unknown:
        raise ValueError(f"unknown case file(s): {', '.join(unknown)}")
    skipped = len(known - set(files))
    return {name: path.read_text(encoding="utf-8") for name, path in files.items()}, "candidates", skipped


def run_benchmark(dataset, candidates=None, baseline=None, update_baseline=None, out=None):
    dataset = Path(dataset)
    cases = enumerate_cases(dataset)
    if not cases:
        raise ValueError(f"no benchmark cases in {dataset}")
    taxonomy_ids = _taxonomy_ids(dataset)
    records = {case.name: validate_case(case, taxonomy_ids) for case in cases}
    candidate_map, mode, skipped = _candidate_map(dataset, candidates)
    pairs = []
    swcr_values, eap_values, mp_values = [], [], []
    by_grade, by_field, by_cell = {}, {}, {}
    for name, record in records.items():
        candidate = candidate_map.get(name)
        if candidate is None:
            continue
        meta = record["meta"]
        score = swcr(record["input"], candidate, record["edits"])
        swcr_values.append(score)
        eap_values.append(eap(record["input"], record["gold"], candidate))
        mp_values.append(mp(record["input"], candidate, meta["protected_names"]))
        grade = meta["error_class"]
        by_grade.setdefault(grade, []).append(score)
        by_field.setdefault(meta["field"], []).append(score)
        by_cell.setdefault(f"{grade}:{meta['severity']}", []).append(score)
        if meta["no_edit"]:
            pairs.append((record["input"], candidate))
    if not swcr_values:
        raise ValueError("no cases selected")
    controls = fpr0(pairs)
    report = {
        "mode": mode, "cases": len(records), "evaluated": len(swcr_values), "skipped": skipped,
        "swcr": sum(swcr_values) / len(swcr_values), "fpr0": controls,
        "eap": sum(eap_values) / len(eap_values),
        "mp": {"dice": sum(x["dice"] for x in mp_values) / len(mp_values), "strict": all(x["strict"] for x in mp_values)},
        "by_grade": {k: sum(v) / len(v) for k, v in sorted(by_grade.items())},
        "by_field": {k: sum(v) / len(v) for k, v in sorted(by_field.items())},
        "by_grade_severity": {k: sum(v) / len(v) for k, v in sorted(by_cell.items())},
    }
    baseline_data = _read_json(baseline) if baseline else None
    if baseline_data and (report["swcr"] < baseline_data["swcr"] - 0.005 or report["fpr0"]["rate"] > baseline_data["fpr0"]["rate"] + 0.01):
        report["regression"] = True
    else:
        report["regression"] = False
    if update_baseline:
        if not any(record["meta"]["review"] == "approved" for record in records.values()):
            raise ValueError("--update-baseline requires at least one approved case")
        Path(update_baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(update_baseline).write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with Path(out).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(report, sort_keys=True) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "benchmark"))
    parser.add_argument("--candidates")
    parser.add_argument("--baseline")
    parser.add_argument("--update-baseline")
    parser.add_argument("--out", default="logs/benchmark.jsonl")
    args = parser.parse_args(argv)
    try:
        report = run_benchmark(args.dataset, args.candidates, args.baseline, args.update_baseline, args.out)
    except ValueError as exc:
        print(f"run_benchmark: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 1 if report["regression"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
